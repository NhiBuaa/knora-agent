import json
import re

import httpx

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence, GenerationResult
from knora.providers.structured_generation import (
    STRUCTURED_RESULT_SCHEMA,
    SYSTEM_PROMPT,
    user_message,
)

OLLAMA_PROMPT_VERSION = "ollama-qwen3-cited-answer-v2"
OLLAMA_SYSTEM_PROMPT = (
    SYSTEM_PROMPT
    + " Include qualifications and exceptions in the evidence that directly change the answer; "
    "do not omit a relevant caveat when stating a rule or count."
    + " For ANSWER, refusal_reason MUST be null. For REFUSAL, answer MUST be null, "
    "cited_evidence_ids MUST be empty, and refusal_reason MUST be INSUFFICIENT_EVIDENCE."
)


class OllamaGenerationProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str = "qwen3:8b",
        expected_digest: str,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        if re.fullmatch(r"sha256:[0-9a-fA-F]{64}", expected_digest) is None:
            raise ValueError("invalid generation model digest")
        self._url = f"{base_url.rstrip('/')}/api/chat"
        self._tags_url = f"{base_url.rstrip('/')}/api/tags"
        self._model = model
        self._expected_digest = expected_digest.lower()
        self._client = client
        self._owns_client = client is None
        self._timeout_seconds = timeout_seconds

    async def generate(
        self, *, question: str, evidence: tuple[GenerationEvidence, ...]
    ) -> GenerationResult:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            tags_response = await self._client.get(self._tags_url)
            tags_response.raise_for_status()
            models = tags_response.json()["models"]
            matches = [item for item in models if item.get("name") == self._model]
            if len(matches) != 1:
                raise KnoraError("GENERATION_MODEL_MISMATCH")
            current_digest = matches[0]["digest"]
            if not isinstance(current_digest, str):
                raise KnoraError("GENERATION_MODEL_MISMATCH")
            current_hex = current_digest.removeprefix("sha256:")
            if (
                re.fullmatch(r"[0-9a-fA-F]{64}", current_hex) is None
                or f"sha256:{current_hex.lower()}" != self._expected_digest
            ):
                raise KnoraError("GENERATION_MODEL_MISMATCH")
            response = await self._client.post(
                self._url,
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": OLLAMA_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message(question, evidence)},
                    ],
                    "format": STRUCTURED_RESULT_SCHEMA,
                    "stream": False,
                    "think": "low" if self._model == "gpt-oss:20b" else False,
                    "options": (
                        {"num_ctx": 8192, "num_predict": 2048, "temperature": 0}
                        if self._model == "gpt-oss:20b"
                        else {"num_predict": 1024, "temperature": 0}
                    ),
                },
            )
            response.raise_for_status()
            payload = response.json()
            structured = json.loads(payload["message"]["content"])
            if not isinstance(structured, dict) or set(structured) != set(
                STRUCTURED_RESULT_SCHEMA["required"]
            ):
                raise ValueError("invalid structured result")
            aliases = structured["cited_evidence_ids"]
            if not isinstance(aliases, list) or not all(isinstance(item, str) for item in aliases):
                raise ValueError("invalid aliases")
            usage = {}
            for source, target in (
                ("prompt_eval_count", "prompt_tokens"),
                ("eval_count", "completion_tokens"),
            ):
                value = payload.get(source)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    usage[target] = value
            return GenerationResult(
                decision=structured["decision"],
                answer=structured["answer"],
                cited_evidence_ids=tuple(aliases),
                refusal_reason=structured["refusal_reason"],
                provider="ollama",
                model=str(payload.get("model", self._model)),
                prompt_version=(
                    f"ollama-gpt-oss-low-v1:{OLLAMA_PROMPT_VERSION}"
                    if self._model == "gpt-oss:20b"
                    else OLLAMA_PROMPT_VERSION
                ),
                finish_reason=payload.get("done_reason"),
                usage=usage,
            )
        except KnoraError:
            raise
        except httpx.HTTPError:
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise KnoraError("GENERATION_OUTPUT_INVALID") from None

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
