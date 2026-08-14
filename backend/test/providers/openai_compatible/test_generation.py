from decimal import Decimal

import httpx
import pytest

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence
from knora.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider


@pytest.mark.asyncio
async def test_openai_compatible_generation_returns_structured_result_and_safe_metadata() -> None:
    observed: dict[str, object] = {}

    async def endpoint(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["authorization"] = request.headers["Authorization"]
        observed["payload"] = __import__("json").loads(request.content)
        return httpx.Response(
            200,
            headers={"x-request-id": "generation-request-1"},
            json={
                "id": "completion-1",
                "model": "compatible-chat-model",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"decision":"ANSWER","answer":"Refunds last thirty days. '
                                '[[E1]]","cited_evidence_ids":["E1"],'
                                '"refusal_reason":null}'
                            )
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )

    provider = OpenAICompatibleGenerationProvider(
        base_url="https://provider.example/v1/",
        api_key="runtime-secret",
        model="compatible-chat-model",
        input_cost_per_million_tokens=Decimal("1"),
        output_cost_per_million_tokens=Decimal("2"),
        pricing_version="test-pricing-v1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )

    result = await provider.generate(
        question="What is the refund policy?",
        evidence=(GenerationEvidence(evidence_id="E1", content="Refunds last thirty days."),),
    )

    payload = observed["payload"]
    assert isinstance(payload, dict)
    assert observed["url"] == "https://provider.example/v1/chat/completions"
    assert observed["authorization"] == "Bearer runtime-secret"
    assert payload["model"] == "compatible-chat-model"
    assert payload["response_format"]["type"] == "json_schema"
    assert "E1" in payload["messages"][1]["content"]
    assert "Refunds last thirty days." in payload["messages"][1]["content"]
    assert result.decision == "ANSWER"
    assert result.answer == "Refunds last thirty days. [[E1]]"
    assert result.cited_evidence_ids == ("E1",)
    assert result.refusal_reason is None
    assert result.provider == "openai-compatible"
    assert result.model == "compatible-chat-model"
    assert result.prompt_version == "m1-cited-answer-v1"
    assert result.finish_reason == "stop"
    assert result.provider_request_id == "generation-request-1"
    assert result.usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert result.cost == {
        "amount_usd": "0.00002",
        "currency": "USD",
        "pricing_version": "test-pricing-v1",
    }


@pytest.mark.asyncio
async def test_generation_prompt_requires_citation_ids_to_follow_first_marker_order() -> None:
    observed: dict[str, object] = {}

    async def endpoint(request: httpx.Request) -> httpx.Response:
        observed["payload"] = __import__("json").loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "compatible-chat-model",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"decision":"ANSWER","answer":"Refunds. [[E1]]",'
                                '"cited_evidence_ids":["E1"],"refusal_reason":null}'
                            )
                        },
                    }
                ],
            },
        )

    provider = OpenAICompatibleGenerationProvider(
        base_url="https://provider.example/v1",
        api_key="runtime-secret",
        model="compatible-chat-model",
        input_cost_per_million_tokens=Decimal("0"),
        output_cost_per_million_tokens=Decimal("0"),
        pricing_version="test-pricing-v1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )

    await provider.generate(
        question="What is the refund policy?",
        evidence=(GenerationEvidence(evidence_id="E1", content="Refunds."),),
    )

    payload = observed["payload"]
    assert isinstance(payload, dict)
    system_prompt = payload["messages"][0]["content"]
    assert "cited_evidence_ids" in system_prompt
    assert "same order that their markers first appear" in system_prompt
    assert "use each inline marker at most once" in system_prompt
    assert "Fact A [[E1]]; fact B [[E1]]" in system_prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["malformed", "http", "timeout"])
async def test_openai_compatible_generation_normalizes_failures_without_retry(
    failure: str,
) -> None:
    calls = 0

    async def endpoint(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if failure == "timeout":
            raise httpx.ReadTimeout("secret-canary-timeout", request=request)
        if failure == "http":
            return httpx.Response(500, text="secret-canary-body")
        return httpx.Response(
            200,
            json={
                "model": "compatible-chat-model",
                "choices": [
                    {"finish_reason": "stop", "message": {"content": "not-json"}}
                ],
            },
        )

    provider = OpenAICompatibleGenerationProvider(
        base_url="https://provider.example/v1",
        api_key="secret-canary-key",
        model="compatible-chat-model",
        input_cost_per_million_tokens=Decimal("1"),
        output_cost_per_million_tokens=Decimal("2"),
        pricing_version="test-pricing-v1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )

    with pytest.raises(KnoraError) as captured:
        await provider.generate(
            question="What is the refund policy?",
            evidence=(
                GenerationEvidence(evidence_id="E1", content="Refunds last thirty days."),
            ),
        )

    expected = (
        "GENERATION_OUTPUT_INVALID" if failure == "malformed" else "PROVIDER_REQUEST_FAILED"
    )
    assert captured.value.code == expected
    assert str(captured.value) == expected
    assert "secret-canary" not in str(captured.value)
    assert calls == 1
