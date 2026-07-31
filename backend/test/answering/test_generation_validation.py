import pytest

from knora.answering.generation_validation import validate_generation
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationResult


def test_answer_marker_order_must_match_cited_evidence_ids() -> None:
    result = GenerationResult(
        decision="ANSWER",
        answer="The second rule applies. [[E2]] The first adds context. [[E1]]",
        cited_evidence_ids=("E1", "E2"),
        refusal_reason=None,
    )

    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(result, available_evidence_ids=("E1", "E2"))


@pytest.mark.parametrize(
    ("answer", "cited_ids"),
    [
        ("Unknown. [[E9]]", ("E9",)),
        ("Duplicate. [[E1]] Again. [[E1]]", ("E1",)),
        ("Missing marker.", ("E1",)),
    ],
)
def test_answer_rejects_unknown_duplicate_or_missing_markers(answer, cited_ids) -> None:
    result = GenerationResult(
        decision="ANSWER",
        answer=answer,
        cited_evidence_ids=cited_ids,
        refusal_reason=None,
    )

    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(result, available_evidence_ids=("E1", "E2"))


def test_structured_refusal_requires_empty_answer_and_citations() -> None:
    valid = GenerationResult(
        decision="REFUSAL",
        answer=None,
        cited_evidence_ids=(),
        refusal_reason="INSUFFICIENT_EVIDENCE",
    )
    invalid = GenerationResult(
        decision="REFUSAL",
        answer="provider-owned refusal",
        cited_evidence_ids=(),
        refusal_reason="INSUFFICIENT_EVIDENCE",
    )

    assert validate_generation(valid, available_evidence_ids=("E1",)).parsed_markers == ()
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(invalid, available_evidence_ids=("E1",))
