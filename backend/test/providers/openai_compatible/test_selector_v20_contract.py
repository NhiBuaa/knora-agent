import json
from decimal import Decimal

import httpx
import pytest

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence
from knora.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider

EVIDENCE = (GenerationEvidence("E1", "Alpha; Beta; short reports may merge parts."),)


def _answer(*, before=None, items=None):
    return {
        "decision": "ANSWER",
        "before": before or [],
        "items": items or [],
        "after": [],
        "refusal_reason": None,
    }


def _provider(replies, requests):
    async def endpoint(request):
        requests.append(json.loads(request.content))
        reply = replies[len(requests) - 1]
        return httpx.Response(
            200,
            headers={"x-request-id": f"stage-{len(requests)}"},
            json={
                "model": "@cf/openai/gpt-oss-20b",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(reply)},
                    }
                ],
            },
        )

    return OpenAICompatibleGenerationProvider(
        base_url="https://provider.example/ai/v1",
        api_key="secret-canary",
        model="@cf/openai/gpt-oss-20b",
        provider_identity="cloudflare-workers-ai",
        max_tokens=1024,
        direct_json_schema=True,
        input_cost_per_million_tokens=Decimal("1"),
        output_cost_per_million_tokens=Decimal("2"),
        pricing_version="test-v1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )


@pytest.mark.asyncio
async def test_count_intent_does_not_forbid_answer_list_and_records_v20_metadata():
    requests = []
    selection = {"count_question": True, "conditions": []}
    lead = {"text": "There are 2 parts.", "bold": "2 parts", "support": ["E1"]}
    answer = _answer(
        before=[lead],
        items=[{"text": "Alpha", "support": ["E1"]}, {"text": "Beta", "support": ["E1"]}],
    )
    provider = _provider([selection, answer], requests)

    result = await provider.generate(question="How many parts?", evidence=EVIDENCE)

    assert result.prompt_version == "cloudflare-gpt-oss-cited-answer-v20"
    assert result.stages[0]["prompt_version"] == "cloudflare-count-conditions-v3"
    assert result.stages[0]["count_question"] is True
    assert "presentation" not in result.stages[0]
    assert "- Alpha" in result.answer
    assert json.loads(requests[1]["messages"][1]["content"])["retained_conditions"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("count_question", [False, True])
async def test_shared_conditions_are_retained_for_prose_answers(count_question):
    requests = []
    selection = {
        "count_question": count_question,
        "conditions": [{"text": "Short reports may merge parts.", "support": ["E1"]}],
    }
    answer = _answer(
        before=[{"text": "The report has two parts.", "bold": None, "support": ["E1"]}]
    )
    provider = _provider([selection, answer], requests)

    result = await provider.generate(question="What is the structure?", evidence=EVIDENCE)

    assert result.answer.endswith("Short reports may merge parts. [[E1]]")
    assert json.loads(requests[1]["messages"][1]["content"])["retained_conditions"] == [
        {"text": "Short reports may merge parts.", "support": ["E1"], "bold": None}
    ]


@pytest.mark.asyncio
async def test_legacy_presentation_selector_is_rejected_before_answer_request():
    requests = []
    provider = _provider([{"presentation": "list", "conditions": []}], requests)

    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        await provider.generate(question="Which parts?", evidence=EVIDENCE)

    assert len(requests) == 1
