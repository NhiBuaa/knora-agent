"""LangChain Chat Models and Structured Output generation adapter for Knora."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence, GenerationProvider, GenerationResult
from knora.providers.openai_compatible.generation import (
    CLOUDFLARE_PROMPT_VERSION,
    CLOUDFLARE_SYSTEM_PROMPT,
)
from knora.providers.structured_generation import (
    SYSTEM_PROMPT,
    user_message,
)


@runtime_checkable
class LangChainChatModel(Protocol):
    """Protocol matching LangChain Runnable / BaseChatModel interface."""

    async def ainvoke(self, input: Any, config: dict[str, Any] | None = None) -> Any: ...


@dataclass(frozen=True, slots=True)
class KnoraLangChainGenerationAdapter:
    """Adapts a LangChain Chat Model or Structured Output Runnable to Knora GenerationProvider.

    Preserves Knora structured JSON schemas, prompt versions, citation alias integrity,
    and KnoraError fail-closed semantics without invoking external telemetry or agent loops.
    Supports S7 forward-compatible parameters (required_groups).
    """

    model: Any
    provider_name: str = "cloudflare-workers-ai"
    model_name: str = "@cf/openai/gpt-oss-20b"
    prompt_version: str = CLOUDFLARE_PROMPT_VERSION

    async def generate(
        self,
        *,
        question: str,
        evidence: tuple[GenerationEvidence, ...] | Sequence[GenerationEvidence],
        required_groups: tuple[str, ...] | None = None,
    ) -> GenerationResult:
        if not isinstance(question, str) or not question.strip():
            raise KnoraError("GENERATION_INPUT_INVALID")

        evidence_tuple = tuple(evidence)
        system_content = (
            CLOUDFLARE_SYSTEM_PROMPT
            if self.provider_name == "cloudflare-workers-ai"
            else SYSTEM_PROMPT
        )
        user_content = user_message(question, evidence_tuple)

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        try:
            # LangChain Runnable / Model invocation
            if hasattr(self.model, "ainvoke"):
                raw_output = await self.model.ainvoke(messages)
            elif hasattr(self.model, "invoke"):
                raw_output = self.model.invoke(messages)
            else:
                raise KnoraError("GENERATION_PROVIDER_UNAVAILABLE")
        except KnoraError:
            raise
        except Exception as exc:
            raise KnoraError("GENERATION_PROVIDER_FAILED") from exc

        # Extract structured content
        data = self._extract_data(raw_output)

        # Validate schema structure
        decision = data.get("decision")
        if decision not in {"ANSWER", "REFUSAL"}:
            raise KnoraError("GENERATION_OUTPUT_INVALID")

        answer = data.get("answer")
        cited = data.get("cited_evidence_ids", ())
        if not isinstance(cited, (list, tuple)):
            raise KnoraError("GENERATION_OUTPUT_INVALID")
        cited_tuple = tuple(str(x) for x in cited)

        refusal_reason = data.get("refusal_reason")

        usage = {}
        if hasattr(raw_output, "response_metadata") and isinstance(
            raw_output.response_metadata, dict
        ):
            usage = raw_output.response_metadata.get("token_usage", {})

        return GenerationResult(
            decision=decision,
            answer=answer,
            cited_evidence_ids=cited_tuple,
            refusal_reason=refusal_reason,
            provider=self.provider_name,
            model=self.model_name,
            prompt_version=self.prompt_version,
            finish_reason="stop",
            usage=usage if isinstance(usage, dict) else {},
        )

    def _extract_data(self, raw_output: Any) -> dict[str, Any]:
        """Extract structured dictionary from AIMessage, BaseModel, or dict."""
        if isinstance(raw_output, dict):
            return raw_output

        # Pydantic BaseModel support
        if hasattr(raw_output, "model_dump"):
            return raw_output.model_dump()
        if hasattr(raw_output, "dict"):
            return raw_output.dict()

        # AIMessage or similar object with .content
        content = getattr(raw_output, "content", None)
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        elif isinstance(content, dict):
            return content

        raise KnoraError("GENERATION_OUTPUT_INVALID")


class KnoraGenerationLangChainRunnable:
    """Adapts a Knora GenerationProvider to a LangChain Runnable interface."""

    def __init__(self, provider: GenerationProvider) -> None:
        if provider is None:
            raise ValueError("provider is required")
        self._provider = provider

    async def ainvoke(
        self, input: dict[str, Any], config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if not isinstance(input, dict):
            raise TypeError("input must be a dict with 'question' and 'evidence'")

        question = input.get("question", "")
        raw_evidence = input.get("evidence", ())
        evidence_list: list[GenerationEvidence] = []
        for item in raw_evidence:
            if isinstance(item, GenerationEvidence):
                evidence_list.append(item)
            elif isinstance(item, dict):
                evidence_list.append(
                    GenerationEvidence(
                        evidence_id=item["evidence_id"],
                        content=item["content"],
                    )
                )
            else:
                raise TypeError("evidence items must be GenerationEvidence or dict")

        result = await self._provider.generate(
            question=question,
            evidence=tuple(evidence_list),
        )
        return {
            "decision": result.decision,
            "answer": result.answer,
            "cited_evidence_ids": list(result.cited_evidence_ids),
            "refusal_reason": result.refusal_reason,
            "provider": result.provider,
            "model": result.model,
            "usage": result.usage,
        }
