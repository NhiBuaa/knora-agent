import json
from decimal import Decimal

import httpx

from knora.domain.errors import KnoraError
from knora.providers.generation import (
    GenerationEvidence,
    GenerationResult,
)

_STRUCTURED_RESULT_SCHEMA = {
    "name": "knora_structured_generation_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": ["ANSWER", "REFUSAL"]},
            "answer": {"type": ["string", "null"]},
            "cited_evidence_ids": {
                "type": "array",
                "items": {"type": "string"},
            },
            "refusal_reason": {
                "type": ["string", "null"],
                "enum": ["INSUFFICIENT_EVIDENCE", None],
            },
        },
        "required": [
            "decision",
            "answer",
            "cited_evidence_ids",
            "refusal_reason",
        ],
        "additionalProperties": False,
    },
}
MILESTONE_ONE_PROMPT_VERSION = "m1-cited-answer-v1"
MILESTONE_ONE_SYSTEM_PROMPT = (
    "Return only the requested JSON. Answer only from the supplied evidence and cite its opaque "
    "aliases as inline markers such as [[E1]]. Refuse when the evidence is insufficient."
)


class OpenAICompatibleGenerationProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        input_cost_per_million_tokens: Decimal,
        output_cost_per_million_tokens: Decimal,
        pricing_version: str,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 60.0,
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

    async def generate(
        self,
        *,
        question: str,
        evidence: tuple[GenerationEvidence, ...],
    ) -> GenerationResult:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            response = await self._client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": MILESTONE_ONE_SYSTEM_PROMPT,
                        },
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "question": question,
                                    "evidence": [
                                        {
                                            "evidence_id": item.evidence_id,
                                            "content": item.content,
                                        }
                                        for item in evidence
                                    ],
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": _STRUCTURED_RESULT_SCHEMA,
                    },
                },
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
            amount = (
                Decimal(usage.get("prompt_tokens", 0))
                * self._input_cost_per_million_tokens
                + Decimal(usage.get("completion_tokens", 0))
                * self._output_cost_per_million_tokens
            ) / Decimal(1_000_000)
            return GenerationResult(
                decision=structured["decision"],
                answer=structured["answer"],
                cited_evidence_ids=tuple(structured["cited_evidence_ids"]),
                refusal_reason=structured["refusal_reason"],
                provider="openai-compatible",
                model=str(payload.get("model", self._model)),
                prompt_version=MILESTONE_ONE_PROMPT_VERSION,
                finish_reason=choice.get("finish_reason"),
                provider_request_id=response.headers.get("x-request-id") or payload.get("id"),
                usage=usage,
                cost={
                    "amount_usd": format(amount, "f"),
                    "currency": "USD",
                    "pricing_version": self._pricing_version,
                },
            )
        except httpx.HTTPError:
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise KnoraError("GENERATION_OUTPUT_INVALID") from None

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
