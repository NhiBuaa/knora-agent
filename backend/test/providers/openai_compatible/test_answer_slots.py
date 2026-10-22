import copy

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


def test_fixed_slots_preserve_order_and_aliases_without_mutating_payload():
    payload = copy.deepcopy(ANSWER)
    assert compose_answer(payload, EVIDENCE) == (
        "Suggested: **2 parts**.\n\n- Alpha\n- Beta\n\nMerging is allowed. [[E1]]",
        ("E1",),
    )
    assert payload == ANSWER


def test_fixed_slots_preserve_repeated_unicode_markdown_text_and_mixed_aliases():
    evidence = (
        GenerationEvidence("E1", "Có thể gộp nếu ngắn."),
        GenerationEvidence("E2", "Gợi ý hai phần: Mục *A* [giữ] & B."),
    )
    repeated = "Mục *A* [giữ] & B"
    payload = {
        "decision": "ANSWER",
        "before": [{"text": "Gợi ý: 2 phần.", "support": ["E2", "E2"], "bold": "2 phần"}],
        "items": [
            {"text": repeated, "support": ["E2", "E1", "E2"]},
            {"text": repeated, "support": ["E2"]},
        ],
        "after": [{"text": "Có thể gộp nếu ngắn.", "support": ["E1"], "bold": None}],
        "refusal_reason": None,
    }
    original = copy.deepcopy(payload)

    assert compose_answer(payload, evidence) == (
        "Gợi ý: **2 phần**.\n\n"
        "- Mục \\*A\\* \\[giữ\\] \\& B\n"
        "- Mục \\*A\\* \\[giữ\\] \\& B\n\n"
        "Có thể gộp nếu ngắn. [[E2]] [[E1]]",
        ("E2", "E1"),
    )
    assert payload == original


def test_refusal_cannot_hide_content_in_any_slot():
    payload = {
        "decision": "REFUSAL",
        "before": [],
        "items": [],
        "after": [],
        "refusal_reason": "INSUFFICIENT_EVIDENCE",
    }
    assert compose_answer(payload, ()) == (None, ())
    payload["after"] = ANSWER["after"]
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        compose_answer(payload, EVIDENCE)


@pytest.mark.parametrize("fault", ["singleton", "missing_bold", "unknown_after", "legacy"])
def test_invalid_slots_are_rejected_without_reconstructing_content(fault):
    payload = copy.deepcopy(ANSWER)
    if fault == "singleton":
        payload["items"].pop()
    elif fault == "missing_bold":
        del payload["before"][0]["bold"]
    elif fault == "unknown_after":
        payload["after"][0]["support"] = ["E99"]
    else:
        payload = {"decision": "ANSWER", "blocks": [], "refusal_reason": None}
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        compose_answer(payload, EVIDENCE)


def test_short_answer_uses_prose_slots_without_bullets():
    payload = {
        "decision": "ANSWER",
        "before": [],
        "items": [],
        "after": [{"text": "Merging is allowed.", "support": ["E1"], "bold": None}],
        "refusal_reason": None,
    }
    assert compose_answer(payload, EVIDENCE) == ("Merging is allowed. [[E1]]", ("E1",))


@pytest.mark.parametrize("slot", ["before", "after"])
def test_paragraph_wire_schema_requires_explicit_nullable_bold(slot):
    reference = ANSWER_BLOCK_SCHEMA["properties"][slot]["items"]["$ref"]
    paragraph = ANSWER_BLOCK_SCHEMA["$defs"][reference.rsplit("/", 1)[1]]
    assert set(paragraph["required"]) == {"text", "support", "bold"}
    assert paragraph["properties"]["bold"]["anyOf"] == [
        {"minLength": 1, "type": "string"},
        {"type": "null"},
    ]


def test_missing_bold_is_rejected_for_every_paragraph():
    payload = copy.deepcopy(ANSWER)
    del payload["after"][0]["bold"]
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        compose_answer(payload, EVIDENCE)


def test_null_bold_preserves_markdown_stars_as_literal_text():
    payload = {
        "decision": "ANSWER",
        "before": [{"text": "Total **unknown**.", "support": ["E1"], "bold": None}],
        "items": [],
        "after": [],
        "refusal_reason": None,
    }
    original = copy.deepcopy(payload)
    assert compose_answer(payload, EVIDENCE) == (r"Total \*\*unknown\*\*. [[E1]]", ("E1",))
    assert payload == original
