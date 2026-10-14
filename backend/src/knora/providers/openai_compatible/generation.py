import json
from decimal import Decimal

import httpx

from knora.domain.errors import KnoraError
from knora.providers.generation import (
    GenerationEvidence,
    GenerationResult,
)
from knora.providers.structured_generation import (
    PROMPT_VERSION,
    STRUCTURED_RESULT_SCHEMA,
    SYSTEM_PROMPT,
    user_message,
)

CLOUDFLARE_PROMPT_VERSION = "cloudflare-gpt-oss-cited-answer-v8"
CLOUDFLARE_SYSTEM_PROMPT = (
    SYSTEM_PROMPT + " For ANSWER, refusal_reason MUST be null. For REFUSAL, answer MUST be null, "
    "cited_evidence_ids MUST be empty, and refusal_reason MUST be INSUFFICIENT_EVIDENCE. "
    "Every ANSWER answer MUST contain the exact cited aliases in double brackets, such as [[E1]], "
    "and cited_evidence_ids MUST list those same aliases. If no alias can support the answer, "
    "return REFUSAL instead. Format the answer with Markdown paragraphs, headings and lists. "
    "An enumeration of two or more distinct items MUST use a Markdown bulleted list, with "
    "each item on its own line starting with '- ', not a comma-separated paragraph. "
    "Preserve the items' meaning and source order; "
    "do not invent members or details absent from the evidence. "
    "Keep short answers about a single fact as prose. "
    "For a list supported by one alias, put one marker after the complete "
    "list. Use the current question's language for all answer prose. "
    "If the question is Vietnamese, introductions, headings and explanations MUST be Vietnamese. "
    "Preserve quoted source titles and technical terms as written. "
    "REQUIRED count-answer layout when the evidence names a collection's members, "
    "including when the question asks only how many: one complete introductory sentence containing "
    "**count unit**, then a blank line and a '- ' line for each named member. "
    "Replace count, unit and members with the actual supported values in the question's language. "
    "The count and its unit belong inside the same bold span. A count-only sentence is incomplete "
    "when the evidence supplies the members."
)


class OpenAICompatibleGenerationProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        input_cost_per_million_tokens: Decimal | None,
        output_cost_per_million_tokens: Decimal | None,
        pricing_version: str | None,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 60.0,
        provider_identity: str = "openai-compatible",
        max_tokens: int | None = None,
        direct_json_schema: bool = False,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._input_cost_per_million_tokens = input_cost_per_million_tokens
        self._output_cost_per_million_tokens = output_cost_per_million_tokens
        self._pricing_version = pricing_version
        self._client = client
        self._owns_client = client is None
        self._timeout_seconds = timeout_seconds
        self._provider_identity = provider_identity
        self._max_tokens = max_tokens
        self._direct_json_schema = direct_json_schema

    async def generate(
        self,
        *,
        question: str,
        evidence: tuple[GenerationEvidence, ...],
    ) -> GenerationResult:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            request_body = {
                "model": self._model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            CLOUDFLARE_SYSTEM_PROMPT
                            if self._provider_identity == "cloudflare-workers-ai"
                            else SYSTEM_PROMPT
                        ),
                    },
                    {"role": "user", "content": user_message(question, evidence)},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": (
                        STRUCTURED_RESULT_SCHEMA
                        if self._direct_json_schema
                        else {
                            "name": "knora_structured_generation_result",
                            "strict": True,
                            "schema": STRUCTURED_RESULT_SCHEMA,
                        }
                    ),
                },
            }
            if self._max_tokens is not None:
                request_body["max_tokens"] = self._max_tokens
            response = await self._client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=request_body,
            )
            response.raise_for_status()
            payload = response.json()
            choice = payload["choices"][0]
            structured = json.loads(choice["message"]["content"])
            usage = {
                key: int(value)
                for key, value in payload.get("usage", {}).items()
                if isinstance(value, int)
            }
            cost = {}
            if (
                "prompt_tokens" in usage
                and "completion_tokens" in usage
                and self._input_cost_per_million_tokens is not None
                and self._output_cost_per_million_tokens is not None
                and self._pricing_version is not None
            ):
                amount = (
                    Decimal(usage["prompt_tokens"]) * self._input_cost_per_million_tokens
                    + Decimal(usage["completion_tokens"]) * self._output_cost_per_million_tokens
                ) / Decimal(1_000_000)
                cost = {
                    "amount_usd": format(amount, "f"),
                    "currency": "USD",
                    "pricing_version": self._pricing_version,
                }
            return GenerationResult(
                decision=structured["decision"],
                answer=structured["answer"],
                cited_evidence_ids=tuple(structured["cited_evidence_ids"]),
                refusal_reason=structured["refusal_reason"],
                provider=self._provider_identity,
                model=str(payload.get("model", self._model)),
                prompt_version=(
                    CLOUDFLARE_PROMPT_VERSION
                    if self._provider_identity == "cloudflare-workers-ai"
                    else PROMPT_VERSION
                ),
                finish_reason=choice.get("finish_reason"),
                provider_request_id=response.headers.get("x-request-id") or payload.get("id"),
                usage=usage,
                cost=cost,
            )
        except httpx.HTTPError:
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise KnoraError("GENERATION_OUTPUT_INVALID") from None

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
