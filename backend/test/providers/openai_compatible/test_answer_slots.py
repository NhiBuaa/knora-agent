import copy
import json

import pytest

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence
from knora.providers.openai_compatible.answer_blocks import ANSWER_BLOCK_SCHEMA, compose_answer

EVIDENCE = (GenerationEvidence("E1", "Suggested: Alpha; Beta. Merging allowed."),)
ANSWER = {
    "decision": "ANSWER",
    "before": [{"text": "Suggested: 2 parts.", "support": ["E1"], "bold": "2 parts"}],
    "items": [{"text": "Alpha", "support": ["E1"]}, {"text": "Beta", "support": ["E1"]}],
    "after": [{"text": "Merging is allowed.", "support": ["E1"], "bold": None}],
    "refusal_reason": None,
}


def test_fixed_slots_render_one_list_between_supported_paragraphs():
    assert compose_answer(ANSWER, EVIDENCE, presentation="count_list") == (
        "Suggested: **2 parts**.\n\n- Alpha\n- Beta\n\nMerging is allowed. [[E1]]",
        ("E1",),
    )


def test_supplied_member_and_shared_conditions_keep_aliases_and_input():
    evidence = (
        GenerationEvidence("E1", "Suggested two parts. The parts may be merged for a short work."),
        GenerationEvidence("E2", "Part Beta applies when needed. Parts may be split for clarity."),
    )
    payload = {
        "decision": "ANSWER",
        "before": [{"text": "Suggested: 2 parts.", "support": ["E1"], "bold": "2 parts"}],
        "items": [
            {"text": "Alpha", "support": ["E1"]},
            {"text": "Beta, when needed", "support": ["E2"]},
        ],
        "after": [
            {
                "text": (
                    "For short work the parts may be merged; split them for clarity when needed."
                ),
                "support": ["E1", "E2"],
                "bold": None,
            }
        ],
        "refusal_reason": None,
    }
    original = copy.deepcopy(payload)
    assert compose_answer(payload, evidence, presentation="count_list") == (
        "Suggested: **2 parts**.\n\n- Alpha\n- Beta, when needed\n\n"
        "For short work the parts may be merged; split them for clarity when needed. "
        "[[E1]] [[E2]]",
        ("E1", "E2"),
    )
    assert payload == original


@pytest.mark.parametrize("slot", ["before", "items", "after"])
def test_refusal_cannot_hide_content_in_any_slot(slot):
    payload = {
        "decision": "REFUSAL",
        "before": [],
        "items": [],
        "after": [],
        "refusal_reason": "INSUFFICIENT_EVIDENCE",
    }
    assert compose_answer(payload, (), presentation="count_list") == (None, ())
    payload[slot] = ANSWER[slot]
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        compose_answer(payload, EVIDENCE, presentation="count_list")


@pytest.mark.parametrize(
    "fault",
    ["empty", "singleton", "no_lead", "missing_bold", "unknown_after", "nested_list", "legacy"],
)
def test_invalid_slots_are_rejected_without_reconstructing_content(fault):
    payload = copy.deepcopy(ANSWER)
    if fault == "empty":
        payload["items"] = []
    elif fault == "singleton":
        payload["items"].pop()
    elif fault == "no_lead":
        payload["before"] = []
    elif fault == "missing_bold":
        del payload["before"][0]["bold"]
    elif fault == "unknown_after":
        payload["after"][0]["support"] = ["E99"]
    elif fault == "nested_list":
        payload["after"] = [{"kind": "list", "items": payload["items"]}]
    else:
        payload = {"decision": "ANSWER", "blocks": [], "refusal_reason": None}
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        compose_answer(payload, EVIDENCE, presentation="count_list")


def test_short_answer_uses_prose_slots_without_bullets():
    payload = {
        "decision": "ANSWER",
        "before": [],
        "items": [],
        "after": [{"text": "Merging is allowed.", "support": ["E1"], "bold": None}],
        "refusal_reason": None,
    }
    assert compose_answer(payload, EVIDENCE, presentation="prose") == (
        "Merging is allowed. [[E1]]",
        ("E1",),
    )


@pytest.mark.parametrize("slot", ["before", "after"])
def test_paragraph_wire_schema_requires_explicit_nullable_bold(slot):
    reference = ANSWER_BLOCK_SCHEMA["properties"][slot]["items"]["$ref"]
    paragraph = ANSWER_BLOCK_SCHEMA["$defs"][reference.rsplit("/", 1)[1]]
    assert set(paragraph["required"]) == {"text", "support", "bold"}
    assert paragraph["properties"]["bold"]["anyOf"] == [
        {"minLength": 1, "type": "string"},
        {"type": "null"},
    ]


@pytest.mark.parametrize("slot", ["before", "after"])
@pytest.mark.parametrize("presentation", [None, "prose", "count_prose"])
def test_missing_bold_is_rejected_for_every_paragraph(slot, presentation):
    payload = {
        "decision": "ANSWER",
        "before": [],
        "items": [],
        "after": [],
        "refusal_reason": None,
    }
    payload["before"] = [{"text": "Total unknown.", "support": ["E1"], "bold": None}]
    payload[slot].append({"text": "Alpha.", "support": ["E1"]})
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        compose_answer(payload, EVIDENCE, presentation=presentation)


def test_q18_missing_bold_payload_is_rejected_without_mutation():
    payload = {
        "decision": "ANSWER",
        "before": [{"text": "Báo cáo được gợi ý gồm **7 chương**.", "support": ["E2"]}],
        "items": [
            {"text": "Chương 1 – Giới thiệu (Introduction)", "support": ["E2"]},
            {"text": "Chương 2 – Cơ sở lý thuyết (Literature Review)", "support": ["E2"]},
            {"text": "Chương 3 – Phân tích yêu cầu (Requirements Analysis)", "support": ["E2"]},
            {"text": "Chương 4 – Thiết kế hệ thống (System Design)", "support": ["E2"]},
            {
                "text": "Chương 5 – Phát triển và Kiểm thử (Development and Testing)",
                "support": ["E2"],
            },
            {
                "text": "Chương 6 – Triển khai và Đánh giá (Deployment and Evaluation)",
                "support": ["E2"],
            },
            {"text": "Chương 7 – Kết luận (Conclusion)", "support": ["E2"]},
        ],
        "after": [],
        "refusal_reason": None,
    }
    original = json.dumps(payload, ensure_ascii=False)
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        compose_answer(payload, (GenerationEvidence("E2", "Outline."),), presentation="count_list")
    assert json.dumps(payload, ensure_ascii=False) == original


@pytest.mark.parametrize("presentation", ["prose", "count_prose"])
def test_null_bold_preserves_markdown_stars_as_literal_text(presentation):
    payload = {
        "decision": "ANSWER",
        "before": [{"text": "Total **unknown**.", "support": ["E1"], "bold": None}],
        "items": [],
        "after": [],
        "refusal_reason": None,
    }
    original = copy.deepcopy(payload)
    assert compose_answer(payload, EVIDENCE, presentation=presentation) == (
        r"Total \*\*unknown\*\*. [[E1]]",
        ("E1",),
    )
    assert payload == original
