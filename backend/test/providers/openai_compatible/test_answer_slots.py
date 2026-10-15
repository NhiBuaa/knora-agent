import copy

import pytest

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence
from knora.providers.openai_compatible.answer_blocks import compose_answer

EVIDENCE = (GenerationEvidence("E1", "Suggested: Alpha; Beta. Merging allowed."),)
ANSWER = {
    "decision": "ANSWER",
    "before": [{"text": "Suggested: 2 parts.", "support": ["E1"], "bold": "2 parts"}],
    "items": [{"text": "Alpha", "support": ["E1"]}, {"text": "Beta", "support": ["E1"]}],
    "after": [{"text": "Merging is allowed.", "support": ["E1"]}],
    "refusal_reason": None,
}


def test_fixed_slots_render_one_list_between_supported_paragraphs():
    assert compose_answer(ANSWER, EVIDENCE, presentation="count_list") == (
        "Suggested: **2 parts**.\n\n- Alpha\n- Beta\n\nMerging is allowed. [[E1]]",
        ("E1",),
    )


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
        "after": [{"text": "Merging is allowed.", "support": ["E1"]}],
        "refusal_reason": None,
    }
    assert compose_answer(payload, EVIDENCE, presentation="prose") == (
        "Merging is allowed. [[E1]]",
        ("E1",),
    )
