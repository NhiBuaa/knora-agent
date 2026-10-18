import json
from decimal import Decimal

import httpx

from knora.domain.errors import KnoraError
from knora.providers.generation import (
    GenerationEvidence,
    GenerationResult,
)
from knora.providers.openai_compatible.answer_blocks import (
    ANSWER_BLOCK_SCHEMA,
    compose_answer,
)
from knora.providers.structured_generation import (
    PROMPT_VERSION,
    STRUCTURED_RESULT_SCHEMA,
    SYSTEM_PROMPT,
    user_message,
)

CLOUDFLARE_PROMPT_VERSION = "cloudflare-gpt-oss-cited-answer-v21"
CLOUDFLARE_SYSTEM_PROMPT = (
    "Return only JSON matching the supplied schema. Answer only from supplied evidence in the "
    "question's language; preserve quoted titles and technical terms. Return before "
    "(introductory paragraphs), items (one main list), and after (concluding paragraphs), in "
    "that order. Each statement has text and a nonempty support array of supplied Evidence "
    "Aliases. Paragraphs also require bold: a literal phrase occurring exactly once in text, or "
    "null. Each text field is one line without Markdown or citation markers; the server adds "
    "bullets, emphasis and citations. Use items for two or more distinct members you state, "
    "rather than embedding an enumeration in paragraph text. Keep single facts and zero or one "
    "known member as paragraphs with items=[]. Preserve clear source order; otherwise arrange "
    "multiple sources without changing meaning. Keep relevant qualifications with the item or "
    "paragraph they govern; do not invent content or infer unsupported members. Use all aliases "
    "needed to support the full statement. For a question asking how many, start before with a "
    "natural lead stating the proven total and set bold to its number-and-unit phrase. If two or "
    "more members are evidenced, put them in items even when listing is not explicitly "
    "requested. A selected subset does not prove a total: disclose incomplete member evidence; "
    "if the total is unproven, state the limit without asserting it and use bold=null. ANSWER "
    "requires content and null refusal_reason. When evidence cannot support an answer, REFUSAL "
    "requires empty before/items/after and refusal_reason=INSUFFICIENT_EVIDENCE. Do not expand a "
    "short single-fact answer with unrelated background."
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
            cloudflare = self._provider_identity == "cloudflare-workers-ai"
            content = user_message(question, evidence)
            version = CLOUDFLARE_PROMPT_VERSION if cloudflare else PROMPT_VERSION
            response = await self._complete(
                CLOUDFLARE_SYSTEM_PROMPT if cloudflare else SYSTEM_PROMPT,
                content,
                ANSWER_BLOCK_SCHEMA if cloudflare else STRUCTURED_RESULT_SCHEMA,
            )
            payload, choice, structured = self._decode(response)
            if cloudflare:
                answer, cited_ids = compose_answer(structured, evidence)
            else:
                answer = structured["answer"]
                cited_ids = tuple(structured["cited_evidence_ids"])
            metadata = self._metadata(response, payload, choice, version)
            usage = metadata["usage"]
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
                prompt_version=version,
                finish_reason=choice.get("finish_reason"),
                provider_request_id=response.headers.get("x-request-id") or payload.get("id"),
                usage=usage,
                cost=cost,
            )
        except httpx.HTTPError:
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise KnoraError("GENERATION_OUTPUT_INVALID") from None

    async def _complete(self, system: str, content: str, schema: dict) -> httpx.Response:
        request_body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
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
            self._url, headers={"Authorization": f"Bearer {self._api_key}"}, json=request_body
        )
        response.raise_for_status()
        return response

    def _decode(self, response: httpx.Response) -> tuple[dict, dict, object]:
        payload = response.json()
        choice = payload["choices"][0]
        if (
            self._provider_identity == "cloudflare-workers-ai"
            and choice.get("finish_reason") == "length"
        ):
            raise KnoraError("GENERATION_OUTPUT_INVALID")
        return payload, choice, json.loads(choice["message"]["content"])

    def _metadata(
        self, response: httpx.Response, payload: dict, choice: dict, version: str
    ) -> dict:
        return {
            "provider": self._provider_identity,
            "model": str(payload.get("model", self._model)),
            "prompt_version": version,
            "finish_reason": choice.get("finish_reason"),
            "provider_request_id": response.headers.get("x-request-id") or payload.get("id"),
            "usage": {
                key: value
                for key, value in payload.get("usage", {}).items()
                if isinstance(value, int)
            },
        }

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
