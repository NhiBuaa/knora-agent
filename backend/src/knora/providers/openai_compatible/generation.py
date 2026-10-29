import json
from decimal import Decimal

import httpx

from knora.domain.errors import KnoraError
from knora.providers.generation import (
    GenerationEvidence,
    GenerationResult,
)
from knora.providers.openai_compatible.answer_blocks import (
    compose_answer_projection,
    compose_grounded_answer,
)
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
        grounded_answers: bool = False,
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
        self._grounded_answers = grounded_answers

    async def generate(
        self,
        *,
        question: str,
        evidence: tuple[GenerationEvidence, ...],
    ) -> GenerationResult:
        return await self._generate(question=question, evidence=evidence, repair=False)

    async def repair_generation(
        self,
        *,
        question: str,
        evidence: tuple[GenerationEvidence, ...],
    ) -> GenerationResult:
        if self._provider_identity != "cloudflare-workers-ai":
            raise KnoraError("GENERATION_OUTPUT_INVALID")
        return await self._generate(question=question, evidence=evidence, repair=True)

    async def _generate(
        self, *, question: str, evidence: tuple[GenerationEvidence, ...], repair: bool
    ) -> GenerationResult:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            cloudflare = self._provider_identity == "cloudflare-workers-ai"
            prompt = build_prompt(
                "cloudflare-answer-repair"
                if repair
                else (
                    "cloudflare-grounded-answer"
                    if cloudflare and self._grounded_answers
                    else ("cloudflare-answer" if cloudflare else "generic")
                ),
                question=question,
                evidence=evidence,
            )
            prompt = self._prepare_prompt(prompt)
            version = prompt.definition.version
            response = await self._complete(prompt)
            payload, choice, structured = self._decode(response)
            projection = None
            if cloudflare:
                composer = (
                    compose_grounded_answer
                    if self._grounded_answers and not repair
                    else compose_answer_projection
                )
                answer, cited_ids, projection = composer(structured, evidence)
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
                answer_projection=projection,
            )
        except httpx.HTTPError:
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise KnoraError("GENERATION_OUTPUT_INVALID") from None

    def _prepare_prompt(self, prompt: BuiltPrompt) -> BuiltPrompt:
        if self._model != "@cf/openai/gpt-oss-120b" or prompt.definition.version not in {
            "cloudflare-gpt-oss-cited-answer-v23",
            "cloudflare-gpt-oss-answer-support-v3",
        }:
            return prompt
        from knora.providers.prompts.versioning import PromptDefinition

        # 120B's schema decoder can emit Harmony tokens; validate JSON locally instead.
        system = prompt.definition.system_prompt + (
            "\nRequired JSON Schema (return a matching JSON object, no extra fields):\n"
            + json.dumps(prompt.definition.schema, ensure_ascii=False)
        )
        return BuiltPrompt(
            PromptDefinition(
                prompt.definition.version + ":json-object-v1",
                system,
                prompt.definition.schema,
                prompt.definition.serializer_id,
            ),
            [{"role": "system", "content": system}, *prompt.messages[1:]],
        )

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
        if prompt.definition.version.endswith(":json-object-v1"):
            request_body["response_format"] = {"type": "json_object"}
        if self._max_tokens is not None:
            request_body["max_tokens"] = self._max_tokens
        if prompt.definition.version.removesuffix(":json-object-v1") in {
            "cloudflare-gpt-oss-answer-support-v3",
            "cloudflare-gpt-oss-cited-answer-v23",
        }:
            request_body["reasoning_effort"] = "low"
            request_body["temperature"] = 0
        response = await self._client.post(
            self._url, headers={"Authorization": f"Bearer {self._api_key}"}, json=request_body
        )
        response.raise_for_status()
        return response

    def build_answer_support_verifier(self):
        from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

        if self._provider_identity != "cloudflare-workers-ai" or self._model not in {
            "@cf/openai/gpt-oss-20b",
            "@cf/openai/gpt-oss-120b",
        }:
            return None
        return CloudflareAnswerSupportVerifier(self.complete_answer_support)

    async def complete_answer_support(self, prompt: BuiltPrompt) -> tuple[object, dict]:
        if self._provider_identity != "cloudflare-workers-ai" or self._model not in {
            "@cf/openai/gpt-oss-20b",
            "@cf/openai/gpt-oss-120b",
        }:
            raise KnoraError("PROVIDER_REQUEST_FAILED")
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout_seconds)
        prompt = self._prepare_prompt(prompt)
        response = await self._complete(prompt)
        metadata = {"provider": self._provider_identity, "model": self._model}
        try:
            payload = response.json()
            choice = payload["choices"][0]
            metadata = self._metadata(response, payload, choice, prompt.definition.version)
            _, _, structured = self._decode(response)
        except (KnoraError, IndexError, KeyError, TypeError, ValueError):
            from knora.answering.answer_support import AnswerSupportFailure

            raise AnswerSupportFailure(
                "GENERATION_OUTPUT_INVALID",
                {"failure": "invalid_verifier_completion", "provider": metadata},
            ) from None
        return structured, metadata

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
