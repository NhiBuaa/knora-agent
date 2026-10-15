import copy

import pytest

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence
from knora.providers.openai_compatible.answer_blocks import compose_answer


def item(text: str, *aliases: str) -> dict:
    return {"text": text, "support": list(aliases)}


def paragraph(text: str, *aliases: str) -> dict:
    return item(text, *aliases)


def answer(*blocks: dict) -> dict:
    before, items, after = [], [], []
    for block in blocks:
        if block.get("kind") == "list":
            items = block["items"]
        else:
            block.pop("kind", None)
            (after if items else before).append(block)
    return {
        "decision": "ANSWER",
        "before": before,
        "items": items,
        "after": after,
        "refusal_reason": None,
    }


EVIDENCE = (
    GenerationEvidence("E1", "Suggested outline: Alpha; Beta. Small projects may merge them."),
    GenerationEvidence("E2", "Create a figure index only when figures exist. Include references."),
)


def test_lists_are_composed_from_items_with_all_sources_and_conditions() -> None:
    payload = answer(
        {
            "kind": "list",
            "items": [item("Alpha", "E1"), item("Mục lục hình nếu có hình", "E2")],
        }
    )
    assert compose_answer(payload, EVIDENCE) == (
        "- Alpha\n- Mục lục hình nếu có hình\n\n[[E1]] [[E2]]",
        ("E1", "E2"),
    )


def test_single_fact_stays_prose_and_refusal_stays_empty() -> None:
    assert compose_answer(answer(paragraph("Có tài liệu tham khảo.", "E2")), EVIDENCE) == (
        "Có tài liệu tham khảo. [[E2]]",
        ("E2",),
    )
    assert compose_answer(
        {
            "decision": "REFUSAL",
            "before": [],
            "items": [],
            "after": [],
            "refusal_reason": "INSUFFICIENT_EVIDENCE",
        },
        (),
    ) == (None, ())


def outline_blocks() -> tuple[dict, dict]:
    return (
        {
            "kind": "paragraph",
            "text": "Dàn ý gợi ý gồm 2 phần. Dự án nhỏ có thể gộp các phần.",
            "bold": "2 phần",
            "support": ["E1"],
        },
        {"kind": "list", "items": [item("Alpha", "E1"), item("Beta", "E1")]},
    )


def test_count_is_general_bold_value_and_unit_with_member_order() -> None:
    assert compose_answer(answer(*outline_blocks()), EVIDENCE) == (
        "Dàn ý gợi ý gồm **2 phần**. Dự án nhỏ có thể gộp các phần.\n\n- Alpha\n- Beta\n\n[[E1]]",
        ("E1",),
    )


def test_independently_supported_total_can_exceed_members_with_disclosure() -> None:
    lead, members = outline_blocks()
    disclosure = "Nguồn hiện có chỉ nêu hai phần; chưa đủ tên ba phần còn lại."
    lead.update(text="Có 5 phần. " + disclosure, bold="5 phần")
    evidence = (GenerationEvidence("E1", "Five parts: Alpha; Beta."),)
    result, aliases = compose_answer(answer(lead, members), evidence)
    assert "**5 phần**" in result
    assert disclosure in result
    assert result.count("\n- ") == 2
    assert aliases == ("E1",)


def test_repeated_source_uses_receive_a_complete_enclosing_citation_group() -> None:
    payload = answer(
        paragraph("Alpha.", "E1"),
        paragraph("References.", "E2"),
        paragraph("Beta.", "E1"),
    )
    assert compose_answer(payload, EVIDENCE) == (
        "Alpha.\n\nReferences.\n\nBeta. [[E1]] [[E2]]",
        ("E1", "E2"),
    )


def test_separate_contiguous_source_groups_keep_their_citations_nearby() -> None:
    result, aliases = compose_answer(
        answer(paragraph("Alpha.", "E1"), paragraph("References.", "E2")), EVIDENCE
    )
    assert result == "Alpha. [[E1]]\n\nReferences. [[E2]]"
    assert aliases == ("E1", "E2")


def test_each_item_keeps_all_required_sources_without_duplicate_markers() -> None:
    payload = answer(
        {
            "kind": "list",
            "items": [
                item("Alpha et références.", "E2", "E1", "E2"),
                item("Beta.", "E1"),
            ],
        }
    )
    assert compose_answer(payload, EVIDENCE) == (
        "- Alpha et références.\n- Beta.\n\n[[E2]] [[E1]]",
        ("E2", "E1"),
    )


def test_model_markdown_is_literal_inside_server_owned_blocks() -> None:
    result, _ = compose_answer(
        answer(
            paragraph("```", "E1"),
            {"kind": "list", "items": [item("---", "E1"), item("1. Beta", "E1")]},
        ),
        EVIDENCE,
    )
    assert result == "\\`\\`\\`\n\n- \\-\\-\\-\n- 1\\. Beta\n\n[[E1]]"


def test_tab_after_number_does_not_create_a_model_owned_list() -> None:
    payload = answer(
        paragraph("1.\tAlpha", "E1"),
        {"kind": "list", "items": [item("2.\tAlpha", "E1"), item("Beta", "E1")]},
    )
    assert compose_answer(payload, EVIDENCE)[0] == (
        "1\\.\tAlpha\n\n- 2\\.\tAlpha\n- Beta\n\n[[E1]]"
    )


def test_single_member_count_keeps_member_as_prose() -> None:
    lead = paragraph("Dàn ý gợi ý có 1 phần: Alpha.", "E1")
    lead["bold"] = "1 phần"
    result, _ = compose_answer(
        answer(lead), (GenerationEvidence("E1", "Suggested outline: Alpha."),)
    )
    assert "**1 phần**" in result
    assert "\n- " not in result


def test_explicit_zero_count_does_not_require_missing_members() -> None:
    lead = paragraph("Có 0 phần.", "E1")
    lead["bold"] = "0 phần"
    result, _ = compose_answer(answer(lead), (GenerationEvidence("E1", "No parts."),))
    assert "**0 phần**" in result


def test_natural_paraphrase_references_source_without_copying_a_quote() -> None:
    source = "Tuy nhiên, mục tiêu chung là trình bày toàn diện đề tài."
    result, aliases = compose_answer(
        answer(paragraph("Mục tiêu chung là trình bày toàn diện đề tài.", "E1")),
        (GenerationEvidence("E1", source),),
    )
    assert result == "Mục tiêu chung là trình bày toàn diện đề tài. [[E1]]"
    assert aliases == ("E1",)
    assert source == "Tuy nhiên, mục tiêu chung là trình bày toàn diện đề tài."


def test_emphasis_preserves_literal_sentence_spacing_and_punctuation() -> None:
    lead, members = outline_blocks()
    lead.update(text="There are 2 parts in the suggested outline.", bold="2 parts")
    result, _ = compose_answer(answer(lead, members), EVIDENCE)
    assert "There are **2 parts** in the suggested outline." in result


def test_emphasis_escapes_model_markdown_as_literal_text() -> None:
    lead = paragraph("Có 2 *phần*.", "E1")
    lead["bold"] = "2 *phần*"
    result, _ = compose_answer(answer(lead), EVIDENCE)
    assert result == "Có **2 \\*phần\\***. [[E1]]"


def test_null_emphasis_stays_prose() -> None:
    lead = paragraph("Alpha.", "E1")
    lead["bold"] = None
    assert compose_answer(answer(lead), EVIDENCE) == ("Alpha. [[E1]]", ("E1",))


@pytest.mark.parametrize(
    "fault",
    [
        "unknown",
        "unknown_paragraph_source",
        "legacy_quote",
        "empty_support",
        "non_string_support",
        "empty_alias",
        "missing_support",
        "raw_marker",
        "multiline",
        "single_item",
        "unknown_bold",
        "repeated_bold",
        "empty_bold",
        "count_field",
        "count_block",
        "extra_field",
        "bad_refusal",
    ],
)
def test_invalid_blocks_fail_closed(fault: str) -> None:
    lead, members = copy.deepcopy(outline_blocks())
    payload = answer(lead, members)
    if fault == "unknown":
        members["items"][0]["support"] = ["E1", "E9"]
    elif fault == "unknown_paragraph_source":
        lead["support"] = ["E9"]
    elif fault == "legacy_quote":
        members["items"][0]["support"] = [{"evidence_id": "E1", "quote": "Alpha"}]
    elif fault == "empty_support":
        members["items"][0]["support"] = []
    elif fault == "non_string_support":
        members["items"][0]["support"] = [1]
    elif fault == "empty_alias":
        members["items"][0]["support"] = [""]
    elif fault == "missing_support":
        del members["items"][0]["support"]
    elif fault == "raw_marker":
        members["items"][0]["text"] = "Alpha [[E2]]"
    elif fault == "multiline":
        members["items"][0]["text"] = "Alpha\n- invented"
    elif fault == "single_item":
        members["items"].pop()
    elif fault == "unknown_bold":
        lead["bold"] = "5 phần"
    elif fault == "repeated_bold":
        lead.update(text="2 phần và 2 phần", bold="2 phần")
    elif fault == "empty_bold":
        lead["bold"] = ""
    elif fault == "count_field":
        lead["basis"] = "members"
    elif fault == "count_block":
        lead["kind"] = "count"
    elif fault == "extra_field":
        payload["extra"] = True
    else:
        payload.update(decision="REFUSAL", refusal_reason="INSUFFICIENT_EVIDENCE")
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        compose_answer(payload, EVIDENCE)
