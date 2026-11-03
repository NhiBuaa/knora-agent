"""Tests for LangChain Query Planner adapter and structured output validation."""

from __future__ import annotations

import json
from typing import Any

import pytest

from knora.adapters.langchain.query_planning import KnoraLangChainQueryPlanner


class MockAIMessage:
    def __init__(self, content: str | dict[str, Any]) -> None:
        self.content = content


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
async def test_langchain_query_planner_successful_decomposition() -> None:
    plan_json = {
        "subquestions": [
            {
                "id": "sub_1",
                "text": "Quy định về thời gian thử việc theo AUTH_403",
                "required": True,
                "depends_on": [],
            },
            {
                "id": "sub_2",
                "text": "Mức lương thử việc theo AUTH_403",
                "required": True,
                "depends_on": ["sub_1"],
            },
        ],
        "variants": [
            {
                "query": "Quy định AUTH_403 về thời gian và lương thử việc",
                "reason": "clarified_standalone",
                "variant_kind": "rewrite",
            }
        ],
    }

    model = FakeLangChainChatModel(return_value=MockAIMessage(content=json.dumps(plan_json)))
    planner = KnoraLangChainQueryPlanner(model=model)

    plan = await planner.aplan("So sánh thời gian và lương thử việc theo AUTH_403")

    assert plan.is_fast_path is False
    assert len(plan.subquestions) == 2
    assert plan.subquestions[0].id == "sub_1"
    assert plan.subquestions[1].depends_on == ("sub_1",)

    # Original query is always preserved as primary variant
    assert plan.variants[0].variant_kind == "original"
    assert len(plan.variants) == 2
    assert plan.variants[1].query == "Quy định AUTH_403 về thời gian và lương thử việc"


@pytest.mark.asyncio
async def test_langchain_query_planner_filters_tampered_protected_spans() -> None:
    # LLM returns one valid variant and one tampered variant (mutating AUTH_403 -> AUTH_999)
    plan_json = {
        "subquestions": [
            {"id": "sub_1", "text": "Quy định AUTH_403", "required": True, "depends_on": []}
        ],
        "variants": [
            {
                "query": "Quy định hợp lệ AUTH_403",
                "reason": "valid",
                "variant_kind": "rewrite",
            },
            {
                "query": "Quy định bị sửa thành AUTH_999",
                "reason": "hallucinated",
                "variant_kind": "rewrite",
            },
        ],
    }

    model = FakeLangChainChatModel(return_value=MockAIMessage(content=json.dumps(plan_json)))
    planner = KnoraLangChainQueryPlanner(model=model)

    plan = await planner.aplan("Nội dung điều khoản AUTH_403")

    # The tampered variant (AUTH_999) must be rejected
    variant_texts = [v.query for v in plan.variants]
    assert "Quy định hợp lệ AUTH_403" in variant_texts
    assert "Quy định bị sửa thành AUTH_999" not in variant_texts


@pytest.mark.asyncio
async def test_langchain_query_planner_fallback_on_model_timeout_or_error() -> None:
    model = FakeLangChainChatModel(raises=TimeoutError("Workers AI timeout"))
    planner = KnoraLangChainQueryPlanner(model=model)

    # Must gracefully fall back to fast-path original plan
    plan = await planner.aplan("Câu hỏi bất kỳ khi model timeout")

    assert plan.is_fast_path is True
    assert plan.original_query == "Câu hỏi bất kỳ khi model timeout"
    assert len(plan.subquestions) == 1
    assert plan.subquestions[0].text == "Câu hỏi bất kỳ khi model timeout"


@pytest.mark.asyncio
async def test_langchain_query_planner_detects_cycles_and_falls_back() -> None:
    # Circular dependency: sub_1 -> sub_2 -> sub_1
    plan_json = {
        "subquestions": [
            {"id": "sub_1", "text": "Câu 1", "required": True, "depends_on": ["sub_2"]},
            {"id": "sub_2", "text": "Câu 2", "required": True, "depends_on": ["sub_1"]},
        ],
        "variants": [],
    }

    model = FakeLangChainChatModel(return_value=MockAIMessage(content=json.dumps(plan_json)))
    planner = KnoraLangChainQueryPlanner(model=model)

    plan = await planner.aplan("Câu hỏi có cycle")
    # Caught cycle -> safely falls back to fast path
    assert plan.is_fast_path is True
    assert len(plan.subquestions) == 1
