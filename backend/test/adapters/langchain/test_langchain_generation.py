"""Tests for Knora LangChain Generation adapter."""

from __future__ import annotations

import json
from typing import Any

import pytest

from knora.adapters.langchain.generation import (
    KnoraGenerationLangChainRunnable,
    KnoraLangChainGenerationAdapter,
    LangChainChatModel,
)
from knora.answering.generation_validation import validate_generation
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence, GenerationResult


class MockAIMessage:
    def __init__(
        self, content: str | dict[str, Any], token_usage: dict[str, int] | None = None
    ) -> None:
        self.content = content
        self.response_metadata = {"token_usage": token_usage or {"total_tokens": 42}}


class FakeLangChainChatModel:
    def __init__(self, return_value: Any = None, raises: Exception | None = None) -> None:
        self.return_value = return_value
        self.raises = raises
        self.invocations: list[Any] = []

    async def ainvoke(self, messages: Any, config: dict[str, Any] | None = None) -> Any:
        self.invocations.append(messages)
        if self.raises:
            raise self.raises
        return self.return_value


@pytest.mark.asyncio
async def test_generation_adapter_satisfies_protocol() -> None:
    model = FakeLangChainChatModel()
    assert isinstance(model, LangChainChatModel)


@pytest.mark.asyncio
async def test_generation_adapter_successful_answer() -> None:
    content = json.dumps(
        {
            "decision": "ANSWER",
            "answer": "This fact is supported [[E1]].",
            "cited_evidence_ids": ["E1"],
            "refusal_reason": None,
        }
    )
    model = FakeLangChainChatModel(return_value=MockAIMessage(content=content))
    adapter = KnoraLangChainGenerationAdapter(model=model)

    evidence = (GenerationEvidence(evidence_id="E1", content="Fact context"),)
    result = await adapter.generate(
        question="What is the fact?",
        evidence=evidence,
        required_groups=("g1",),
    )

    assert result.decision == "ANSWER"
    assert result.answer == "This fact is supported [[E1]]."
    assert result.cited_evidence_ids == ("E1",)
    assert result.refusal_reason is None
    assert result.usage == {"total_tokens": 42}

    # Verify Knora strict validation passes
    validated = validate_generation(result, available_evidence_ids=("E1",))
    assert validated.parsed_markers == ("E1",)


@pytest.mark.asyncio
async def test_generation_adapter_refusal() -> None:
    content = json.dumps(
        {
            "decision": "REFUSAL",
            "answer": None,
            "cited_evidence_ids": [],
            "refusal_reason": "INSUFFICIENT_EVIDENCE",
        }
    )
    model = FakeLangChainChatModel(return_value=MockAIMessage(content=content))
    adapter = KnoraLangChainGenerationAdapter(model=model)

    result = await adapter.generate(
        question="Unknown fact?",
        evidence=(),
    )

    assert result.decision == "REFUSAL"
    assert result.answer is None
    assert result.cited_evidence_ids == ()
    assert result.refusal_reason == "INSUFFICIENT_EVIDENCE"

    validated = validate_generation(result, available_evidence_ids=())
    assert validated.parsed_markers == ()


@pytest.mark.asyncio
async def test_generation_adapter_malformed_json_raises_knora_error() -> None:
    model = FakeLangChainChatModel(return_value=MockAIMessage(content="Not a valid JSON"))
    adapter = KnoraLangChainGenerationAdapter(model=model)

    with pytest.raises(KnoraError) as exc_info:
        await adapter.generate(
            question="What is this?",
            evidence=(),
        )
    assert exc_info.value.code == "GENERATION_OUTPUT_INVALID"


@pytest.mark.asyncio
async def test_generation_adapter_missing_required_keys_raises_knora_error() -> None:
    content = json.dumps({"foo": "bar"})
    model = FakeLangChainChatModel(return_value=MockAIMessage(content=content))
    adapter = KnoraLangChainGenerationAdapter(model=model)

    with pytest.raises(KnoraError) as exc_info:
        await adapter.generate(
            question="What is this?",
            evidence=(),
        )
    assert exc_info.value.code == "GENERATION_OUTPUT_INVALID"


@pytest.mark.asyncio
async def test_generation_adapter_provider_failure_raises_knora_error() -> None:
    model = FakeLangChainChatModel(raises=RuntimeError("Connection reset"))
    adapter = KnoraLangChainGenerationAdapter(model=model)

    with pytest.raises(KnoraError) as exc_info:
        await adapter.generate(
            question="What is this?",
            evidence=(),
        )
    assert exc_info.value.code == "GENERATION_PROVIDER_FAILED"


@pytest.mark.asyncio
async def test_knora_generation_langchain_runnable() -> None:
    class MockProvider:
        async def generate(
            self, *, question: str, evidence: tuple[GenerationEvidence, ...]
        ) -> GenerationResult:
            return GenerationResult(
                decision="ANSWER",
                answer=f"Answer to '{question}' using [[E1]].",
                cited_evidence_ids=("E1",),
                refusal_reason=None,
                provider="mock-provider",
                model="mock-model",
            )

    runnable = KnoraGenerationLangChainRunnable(MockProvider())  # type: ignore
    output = await runnable.ainvoke(
        {
            "question": "Testing runnable?",
            "evidence": [{"evidence_id": "E1", "content": "Context E1"}],
        }
    )

    assert output["decision"] == "ANSWER"
    assert output["answer"] == "Answer to 'Testing runnable?' using [[E1]]."
    assert output["cited_evidence_ids"] == ["E1"]
    assert output["provider"] == "mock-provider"
