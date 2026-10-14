import json
from decimal import Decimal

import httpx

from knora.domain.errors import KnoraError
from knora.providers.generation import (
    GenerationEvidence,
    GenerationResult,
)
from knora.providers.openai_compatible.answer_blocks import ANSWER_BLOCK_SCHEMA, compose_answer
from knora.providers.structured_generation import (
    PROMPT_VERSION,
    STRUCTURED_RESULT_SCHEMA,
    SYSTEM_PROMPT,
    user_message,
)

CLOUDFLARE_PROMPT_VERSION = "cloudflare-gpt-oss-cited-answer-v13"
CLOUDFLARE_SYSTEM_PROMPT = (
    "Return only JSON matching the supplied schema. Answer only from supplied evidence. "
    "ANSWER requires nonempty blocks and null refusal_reason. REFUSAL requires empty blocks and "
    "INSUFFICIENT_EVIDENCE when evidence cannot support an answer. Each statement has support: "
    "an evidence_id and an exact quote from that evidence (whitespace may be collapsed). "
    "Use all sources needed to support each statement, not one convenient source for the answer. "
    "Quotes must support the full statement and its important qualifications. Do not invent, "
    "omit important conditions, or infer unsupported members. Retain conditional context. "
    "Answer only the question's scope. Do not expand a single-fact answer with related background, "
    "report parts or outlines. For a requested collection, retain its conditional members and "
    "qualifications from all relevant evidence. Never paraphrase words inside a quote. "
    "Write natural prose in the question's language; preserve quoted titles/technical terms. "
    "Each text field is one line without citation markers; the server adds bullets and citations. "
    "Keep a short single-fact answer as a paragraph. Any enumeration of two or more distinct items "
    "must be a list block, never embedded in paragraph text. Set ordered=true when the source "
    "defines a clear sequence; preserve it. Otherwise ordered=false and arrange multiple "
    "sources sensibly without changing meaning. Each item has its own supporting quotes. "
    "For count questions, even when only how many is asked, lead with a natural paragraph "
    "stating the proven total, then list the evidenced members. One member stays in prose; "
    "zero needs no member list. Set paragraph bold to the literal number-and-unit phrase "
    "occurring exactly once in its text; otherwise omit bold or use null. "
    "The server adds emphasis. "
    "A total needs explicit source proof or a complete source collection; a selected subset "
    "does not prove it. A proven total with incomplete member evidence must disclose the missing "
    "portion in prose. If the total is unproven, explain the evidence limit without asserting it. "
    "Keep suggested-outline context and merging/splitting qualifications when the source makes "
    "the outline conditional. Keep conditional indexes conditional."
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
            schema = (
                ANSWER_BLOCK_SCHEMA
                if self._provider_identity == "cloudflare-workers-ai"
                else STRUCTURED_RESULT_SCHEMA
            )
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
                        schema
                        if self._direct_json_schema
                        else {
                            "name": "knora_structured_generation_result",
                            "strict": True,
                            "schema": schema,
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
            if self._provider_identity == "cloudflare-workers-ai":
                answer, cited_ids = compose_answer(structured, evidence)
            else:
                answer = structured["answer"]
                cited_ids = tuple(structured["cited_evidence_ids"])
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
                answer=answer,
                cited_evidence_ids=cited_ids,
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
