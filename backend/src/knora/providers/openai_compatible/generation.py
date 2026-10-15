import json
from decimal import Decimal

import httpx

from knora.domain.errors import KnoraError
from knora.providers.generation import (
    GenerationEvidence,
    GenerationResult,
)
from knora.providers.openai_compatible.answer_blocks import compose_answer
from knora.providers.openai_compatible.presentation import PresentationChoice
from knora.providers.prompts.builder import BuiltPrompt, build_prompt
from knora.providers.prompts.policy import (
    CLOUDFLARE_PROMPT_VERSION as CLOUDFLARE_PROMPT_VERSION,
)
from knora.providers.prompts.policy import (
    CLOUDFLARE_SYSTEM_PROMPT as CLOUDFLARE_SYSTEM_PROMPT,
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
            presentation = None
            stages = []
            if cloudflare:
                selection_prompt = build_prompt(
                    "cloudflare-selector", question=question, evidence=evidence
                )
                response = await self._complete(selection_prompt)
                payload, choice, structured = self._decode(response)
                presentation = PresentationChoice.model_validate(structured).presentation
                stages.append(
                    self._metadata(response, payload, choice, selection_prompt.definition.version)
                )
                stages[0]["presentation"] = presentation
            prompt = build_prompt(
                "cloudflare-answer" if cloudflare else "generic",
                question=question,
                evidence=evidence,
                presentation=presentation,
            )
            version = prompt.definition.version
            response = await self._complete(prompt)
            payload, choice, structured = self._decode(response)
            if cloudflare:
                answer, cited_ids = compose_answer(structured, evidence, presentation=presentation)
            else:
                answer = structured["answer"]
                cited_ids = tuple(structured["cited_evidence_ids"])
            metadata = self._metadata(response, payload, choice, version)
            usage = metadata["usage"]
            if cloudflare:
                stages.append(metadata)
                usage = {
                    key: stages[0]["usage"][key] + value
                    for key, value in usage.items()
                    if key in stages[0]["usage"]
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
                prompt_version=version,
                finish_reason=choice.get("finish_reason"),
                provider_request_id=response.headers.get("x-request-id") or payload.get("id"),
                usage=usage,
                cost=cost,
                stages=tuple(stages),
            )
        except httpx.HTTPError:
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise KnoraError("GENERATION_OUTPUT_INVALID") from None

    async def _complete(self, prompt: BuiltPrompt) -> httpx.Response:
        request_body = {
            "model": self._model,
            "messages": prompt.messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": (
                    prompt.definition.schema
                    if self._direct_json_schema
                    else {
                        "name": "knora_structured_generation_result",
                        "strict": True,
                        "schema": prompt.definition.schema,
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
