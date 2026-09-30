from dataclasses import replace

import pytest

from knora.answering.evidence import select_evidence
from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration


def containment_configuration():
    return replace(
        RetrievalConfiguration.milestone_one(),
        id="retrieval-evidence-containment-v1",
        overlap_policy="adjacent-content-containment-v1",
    )


@pytest.mark.parametrize(
    ("selected_text", "next_text", "expected"),
    [
        ("Report has seven sections", "Updated 2031-02-03. Report has seven sections", "SELECTED"),
        ("Report has seven sections", "Report has seven sections", "REDUNDANT_OVERLAP"),
        ("The report has seven sections today", "report has seven sections", "REDUNDANT_OVERLAP"),
        ("Report has seven sections", "Report has eight sections", "SELECTED"),
        ("Refunds are allowed", "Refunds are not allowed", "SELECTED"),
        ("Alice pays Bob", "Bob pays Alice", "SELECTED"),
        ("A B A", "A A B", "SELECTED"),
        ("ABC is required", "abc is required", "SELECTED"),
        ("Value 1.5", "Value 15", "SELECTED"),
        ("Refunds are allowed", "", "SELECTED"),
    ],
)
def test_containment_preserves_information(selected_text, next_text, expected):
    result = select_evidence(
        (
            candidate(chunk_id="first", ordinal=1, content=selected_text),
            candidate(chunk_id="next", ordinal=0, content=next_text),
        ),
        containment_configuration(),
    )
    assert result.decisions[1].outcome == expected


@pytest.mark.parametrize("other_set", [False, True])
def test_containment_is_limited_to_adjacent_same_set(other_set):
    first = candidate(chunk_id="first", ordinal=0, content="same text")
    second = replace(
        candidate(chunk_id="next", ordinal=1 if other_set else 2, content="same text"),
        chunk_set_id="other" if other_set else first.chunk_set_id,
    )
    assert len(select_evidence((first, second), containment_configuration()).selected) == 2


@pytest.mark.parametrize(
    ("limits", "expected"),
    [
        ({"max_evidence_tokens": 100}, "TOKEN_BUDGET_EXCEEDED"),
        ({"max_evidence_chunks": 1}, "CHUNK_COUNT_LIMIT"),
    ],
)
def test_unique_information_still_obeys_budget(limits, expected):
    result = select_evidence(
        (
            candidate(chunk_id="first", ordinal=0, content="shared words here"),
            candidate(chunk_id="next", ordinal=1, content="shared words here plus a date"),
        ),
        replace(containment_configuration(), **limits),
    )
    assert result.decisions[1].outcome == expected


def test_unknown_overlap_policy_is_rejected_even_without_candidates():
    with pytest.raises(ValueError, match="overlap policy"):
        select_evidence((), replace(containment_configuration(), overlap_policy="unknown"))


def test_empty_evidence_remains_empty():
    assert select_evidence((), containment_configuration()).selected == ()


def candidate(
    *,
    chunk_id: str,
    ordinal: int,
    content: str,
    similarity: float = 0.9,
    token_count: int = 100,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        document_id="document-1",
        document_version_id="version-1",
        source_key="support/refunds",
        source_name="refunds.md",
        chunk_set_id="chunk-set-1",
        embedding_set_id="embedding-set-1",
        embedding_configuration_id="embedding-local-m1-v2",
        chunk_id=chunk_id,
        chunk_ordinal=ordinal,
        heading_path=("Refunds",),
        start_line=ordinal + 1,
        end_line=ordinal + 3,
        content=content,
        content_checksum=f"checksum-{chunk_id}",
        token_count=token_count,
        cosine_distance=1.0 - similarity,
        similarity=similarity,
    )


def test_adjacent_strongly_overlapping_chunk_is_redundant() -> None:
    candidates = (
        candidate(
            chunk_id="chunk-1",
            ordinal=0,
            content="refund requests are accepted within thirty days of purchase",
        ),
        candidate(
            chunk_id="chunk-2",
            ordinal=1,
            content="within thirty days of purchase refund requests are accepted online",
        ),
    )

    result = select_evidence(candidates, RetrievalConfiguration.milestone_one())

    assert [item.candidate.chunk_id for item in result.selected] == ["chunk-1"]
    assert [item.outcome for item in result.decisions] == [
        "SELECTED",
        "REDUNDANT_OVERLAP",
    ]


def test_selection_applies_token_budget_without_post_fusion_similarity_threshold() -> None:
    configuration = RetrievalConfiguration.milestone_one()
    candidates = (
        candidate(chunk_id="below", ordinal=0, content="below", similarity=0.649, token_count=1),
        candidate(chunk_id="one", ordinal=2, content="one unique", token_count=1000),
        candidate(chunk_id="two", ordinal=4, content="two unique", token_count=1000),
        candidate(chunk_id="three", ordinal=6, content="three unique", token_count=1000),
        candidate(chunk_id="over-budget", ordinal=8, content="four unique", token_count=1),
    )

    result = select_evidence(candidates, configuration)

    assert [item.outcome for item in result.decisions] == [
        "SELECTED",
        "SELECTED",
        "SELECTED",
        "TOKEN_BUDGET_EXCEEDED",
        "SELECTED",
    ]
    assert sum(item.candidate.token_count for item in result.selected) == 2002


def test_evidence_count_limit_has_distinct_outcome() -> None:
    candidates = tuple(
        candidate(
            chunk_id=f"chunk-{index}",
            ordinal=index * 2,
            content=f"unique evidence {index}",
            similarity=0.65,
            token_count=1,
        )
        for index in range(6)
    )

    result = select_evidence(candidates, RetrievalConfiguration.milestone_one())

    assert len(result.selected) == 5
    assert [item.outcome for item in result.decisions] == [
        "SELECTED",
        "SELECTED",
        "SELECTED",
        "SELECTED",
        "SELECTED",
        "CHUNK_COUNT_LIMIT",
    ]
