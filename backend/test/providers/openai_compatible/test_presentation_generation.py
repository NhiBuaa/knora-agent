import copy
import json
from decimal import Decimal

import httpx
import pytest

from knora.answering.generation_validation import validate_generation
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence
from knora.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider

EVIDENCE = (GenerationEvidence("E1", "Suggested: Alpha; Beta. Parts may be merged."),)
LEAD = {
    "kind": "paragraph",
    "text": "Suggested: 2 parts; merging is allowed.",
    "bold": "2 parts",
    "support": ["E1"],
}
LIST = {
    "kind": "list",
    "items": [{"text": "Alpha", "support": ["E1"]}, {"text": "Beta", "support": ["E1"]}],
}
PROSE = {"kind": "paragraph", "text": "Merging is allowed.", "support": ["E1"], "bold": None}


def _answer(blocks):
    before, items, after = [], [], []
    for block in blocks:
        if block.get("kind") == "list":
            items = block["items"]
        else:
            paragraph = {key: value for key, value in block.items() if key != "kind"}
            (after if items else before).append(paragraph)
    return {
        "decision": "ANSWER",
        "before": before,
        "items": items,
        "after": after,
        "refusal_reason": None,
    }


def _provider(replies, requests):
    async def endpoint(request):
        requests.append(json.loads(request.content))
        reply = replies[len(requests) - 1]
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, httpx.Response):
            return reply
        content, finish, usage = reply
        return httpx.Response(
            200,
            headers={"x-request-id": f"stage-{len(requests)}"},
            json={
                "model": "@cf/openai/gpt-oss-20b",
                "usage": usage,
                "choices": [{"finish_reason": finish, "message": {"content": json.dumps(content)}}],
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
@pytest.mark.parametrize(
    ("presentation", "blocks", "expected"),
    [
        ("prose", [PROSE], "Merging is allowed. [[E1]]"),
        ("list", [LIST], "- Alpha\n- Beta\n\n[[E1]]"),
        (
            "count_list",
            [LEAD, LIST],
            "Suggested: **2 parts**; merging is allowed.\n\n- Alpha\n- Beta\n\n[[E1]]",
        ),
        (
            "count_prose",
            [
                {
                    "kind": "paragraph",
                    "text": "Only Alpha is evidenced; total unknown.",
                    "bold": None,
                    "support": ["E1"],
                }
            ],
            "Only Alpha is evidenced; total unknown. [[E1]]",
        ),
    ],
)
async def test_selected_contract_composes_answer_and_records_both_stages(
    presentation, blocks, expected
):
    requests = []
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    provider = _provider(
        [
            ({"presentation": presentation, "conditions": []}, "stop", usage),
            (_answer(blocks), "stop", usage),
        ],
        requests,
    )
    result = await provider.generate(
        question="What does the supplied material say?", evidence=EVIDENCE
    )
    assert result.answer == expected
    assert validate_generation(result, available_evidence_ids=("E1",)).parsed_markers == ("E1",)
    assert len(requests) == 2
    assert [request["max_tokens"] for request in requests] == [1024, 1024]
    assert all(request["model"] == "@cf/openai/gpt-oss-20b" for request in requests)
    first_user = json.loads(requests[0]["messages"][1]["content"])
    second_user = json.loads(requests[1]["messages"][1]["content"])
    assert second_user == {**first_user, "retained_conditions": []}
    answer_policy = requests[1]["messages"][0]["content"]
    assert "conditions on an individual member in that item's text" in answer_policy
    assert "conditions not already covered by retained_conditions" in answer_policy
    assert "Use after=[] when no additional relevant shared conditions remain" in answer_policy
    assert "conditions that govern the total, member inclusion or applicability" in answer_policy
    selection_schema = requests[0]["response_format"]["json_schema"]
    assert selection_schema["additionalProperties"] is False
    assert selection_schema["required"] == ["presentation", "conditions"]
    note_schema = selection_schema["$defs"]["SourceCondition"]
    assert note_schema["required"] == ["text", "support"]
    assert note_schema["additionalProperties"] is False
    assert note_schema["properties"]["support"]["minItems"] == 1
    answer_schema = requests[1]["response_format"]["json_schema"]
    assert set(answer_schema["required"]) == {
        "decision",
        "before",
        "items",
        "after",
        "refusal_reason",
    }
    assert answer_schema["properties"]["items"]["type"] == "array"
    assert answer_schema["properties"]["before"]["items"] == {"$ref": "#/$defs/_Paragraph"}
    assert answer_schema["additionalProperties"] is False
    assert not any(
        key in json.dumps(answer_schema)
        for key in ('"oneOf"', '"contains"', '"prefixItems"', '"discriminator"')
    )
    assert result.prompt_version == "cloudflare-gpt-oss-cited-answer-v19"
    assert result.usage == {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}
    assert result.cost["amount_usd"] == "0.00004"
    assert [stage["provider_request_id"] for stage in result.stages] == ["stage-1", "stage-2"]
    assert result.stages[0]["prompt_version"] == "cloudflare-presentation-conditions-v2"
    assert result.stages[1]["prompt_version"] == "cloudflare-gpt-oss-cited-answer-v19"
    assert result.stages[0]["presentation"] == presentation
    assert result.stages[1]["usage"] == usage
    assert all("messages" not in stage for stage in result.stages)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model_after", [[], [{"text": "Additional limit.", "support": ["E1"], "bold": None}]]
)
async def test_selected_conditions_survive_final_after_and_preserve_payloads(model_after):
    requests = []
    selection = {
        "presentation": "list",
        "conditions": [{"text": "Grouping may vary for short work.", "support": ["E1"]}],
    }
    answer = _answer([LIST])
    answer["after"] = model_after
    original_selection, original_answer = copy.deepcopy(selection), copy.deepcopy(answer)
    provider = _provider([(selection, "stop", {}), (answer, "stop", {})], requests)

    result = await provider.generate(question="Which parts?", evidence=EVIDENCE)

    assert result.answer == (
        "- Alpha\n- Beta\n\n"
        + ("Additional limit.\n\n" if model_after else "")
        + "Grouping may vary for short work. [[E1]]"
    )
    assert result.cited_evidence_ids == ("E1",)
    assert validate_generation(result, available_evidence_ids=("E1",)).parsed_markers == ("E1",)
    assert len(requests) == 2
    first = json.loads(requests[0]["messages"][1]["content"])
    second = json.loads(requests[1]["messages"][1]["content"])
    assert second == {
        **first,
        "retained_conditions": [
            {"text": "Grouping may vary for short work.", "support": ["E1"], "bold": None}
        ],
    }
    assert "Grouping may vary for short work." not in requests[1]["messages"][0]["content"]
    assert "Grouping may vary for short work." not in json.dumps(result.stages)
    assert selection == original_selection
    assert answer == original_answer


@pytest.mark.asyncio
@pytest.mark.parametrize("presentation", ["list", "count_list"])
async def test_selected_conditions_do_not_override_valid_refusal(presentation):
    requests = []
    refusal = {
        "decision": "REFUSAL",
        "before": [],
        "items": [],
        "after": [],
        "refusal_reason": "INSUFFICIENT_EVIDENCE",
    }
    selection = {
        "presentation": presentation,
        "conditions": [{"text": "Parts may be merged.", "support": ["E1"]}],
    }
    provider = _provider([(selection, "stop", {}), (refusal, "stop", {})], requests)
    result = await provider.generate(question="Which parts?", evidence=EVIDENCE)
    assert (result.answer, result.cited_evidence_ids) == (None, ())
    assert len(requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selection",
    [
        {"presentation": "list"},
        {"presentation": "list", "conditions": None},
        {"presentation": "list", "conditions": {}},
        {"presentation": "list", "conditions": [{}]},
        {"presentation": "list", "conditions": [{"text": "Condition.", "support": []}]},
        {"presentation": "list", "conditions": [{"text": "Condition.", "support": [1]}]},
        {
            "presentation": "list",
            "conditions": [{"text": "Condition.", "support": ["E1"], "extra": 1}],
        },
        {"presentation": "list", "conditions": [{"text": " ", "support": ["E1"]}]},
        {"presentation": "list", "conditions": [{"text": "First\nsecond", "support": ["E1"]}]},
        {"presentation": "list", "conditions": [{"text": "First\rsecond", "support": ["E1"]}]},
        {"presentation": "list", "conditions": [{"text": "[[E1]]", "support": ["E1"]}]},
        {"presentation": "list", "conditions": [{"text": "bad ]] marker", "support": ["E1"]}]},
        {"presentation": "list", "conditions": [{"text": "Condition.", "support": ["E99"]}]},
        {"presentation": "prose", "conditions": [{"text": "Condition.", "support": ["E1"]}]},
        {"presentation": "count_prose", "conditions": [{"text": "Condition.", "support": ["E1"]}]},
    ],
)
async def test_invalid_selected_conditions_stop_before_final_request(selection):
    requests = []
    provider = _provider([(selection, "stop", {})], requests)
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        await provider.generate(question="Which parts?", evidence=EVIDENCE)
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("presentation", ["prose", "list", "count_prose", "count_list"])
async def test_every_selected_contract_allows_evidence_refusal(presentation):
    requests = []
    refusal = {
        "decision": "REFUSAL",
        "before": [],
        "items": [],
        "after": [],
        "refusal_reason": "INSUFFICIENT_EVIDENCE",
    }
    provider = _provider(
        [({"presentation": presentation, "conditions": []}, "stop", {}), (refusal, "stop", {})],
        requests,
    )
    result = await provider.generate(question="Unknown?", evidence=EVIDENCE)
    assert result.answer is None
    assert result.cited_evidence_ids == ()
    assert result.refusal_reason == "INSUFFICIENT_EVIDENCE"
    assert len(requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("presentation", "blocks"),
    [
        ("list", [PROSE]),
        ("count_list", [LEAD]),
        ("count_list", [LIST, LEAD]),
        ("count_list", [{key: value for key, value in LEAD.items() if key != "bold"}, LIST]),
        ("prose", [LIST]),
        ("count_prose", [LEAD, LIST]),
        ("count_prose", [{key: value for key, value in PROSE.items() if key != "bold"}]),
        ("list", [{"kind": "list", "items": [LIST["items"][0]]}]),
        (
            "list",
            [{"kind": "list", "items": [{"text": "Alpha", "support": ["E99"]}, LIST["items"][1]]}],
        ),
    ],
)
async def test_wrong_selected_shape_or_alias_is_an_error_without_repair(presentation, blocks):
    requests = []
    provider = _provider(
        [
            ({"presentation": presentation, "conditions": []}, "stop", {}),
            (_answer(blocks), "stop", {}),
        ],
        requests,
    )
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        await provider.generate(question="Any collection?", evidence=EVIDENCE)
    assert len(requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selection",
    [
        {"presentation": "invented", "conditions": []},
        {"presentation": "list", "conditions": [], "members": ["Alpha"]},
        {},
        {"presentation": None, "conditions": []},
        {"presentation": "list"},
        ["list"],
    ],
)
async def test_invalid_selection_stops_before_generation(selection):
    requests = []
    provider = _provider([(selection, "stop", {})], requests)
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        await provider.generate(question="Any collection?", evidence=EVIDENCE)
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", [1, 2])
@pytest.mark.parametrize("failure", ["http", "timeout", "length"])
async def test_either_stage_failure_stops_without_retry(stage, failure):
    requests = []
    content = {"presentation": "prose", "conditions": []} if stage == 1 else _answer([PROSE])
    failed = (
        (content, "length", {})
        if failure == "length"
        else httpx.Response(503, text="secret-canary")
        if failure == "http"
        else httpx.ReadTimeout("secret-canary")
    )
    replies = [({"presentation": "prose", "conditions": []}, "stop", {})] * (stage - 1) + [failed]
    provider = _provider(replies, requests)
    code = "GENERATION_OUTPUT_INVALID" if failure == "length" else "PROVIDER_REQUEST_FAILED"
    with pytest.raises(KnoraError, match=code) as captured:
        await provider.generate(question="Any fact?", evidence=EVIDENCE)
    assert str(captured.value) == code
    assert len(requests) == stage


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_stage", [0, 1])
async def test_missing_stage_usage_is_unknown_not_partial_turn_cost(missing_stage):
    requests = []
    usage = [{"prompt_tokens": 10, "completion_tokens": 5}] * 2
    usage[missing_stage] = {}
    provider = _provider(
        [
            ({"presentation": "prose", "conditions": []}, "stop", usage[0]),
            (_answer([PROSE]), "stop", usage[1]),
        ],
        requests,
    )
    result = await provider.generate(question="Any fact?", evidence=EVIDENCE)
    assert result.usage == {}
    assert result.cost == {}
    assert result.stages[missing_stage]["usage"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("members", [[], ["Alpha"]])
async def test_proven_total_with_zero_or_one_known_member_stays_prose(members):
    requests = []
    lead = {
        "kind": "paragraph",
        "text": "There are 5 parts; remaining titles are unavailable.",
        "bold": "5 parts",
        "support": ["E1"],
    }
    blocks = [lead] + (
        [{"kind": "paragraph", "text": members[0], "support": ["E1"], "bold": None}]
        if members
        else []
    )
    provider = _provider(
        [
            ({"presentation": "count_prose", "conditions": []}, "stop", {}),
            (_answer(blocks), "stop", {}),
        ],
        requests,
    )
    result = await provider.generate(
        question="How many parts?",
        evidence=(GenerationEvidence("E1", "5 parts. " + "; ".join(members)),),
    )
    assert "**5 parts**" in result.answer
    assert "remaining titles are unavailable" in result.answer
    assert "\n- " not in result.answer
