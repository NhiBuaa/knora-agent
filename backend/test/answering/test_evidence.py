from knora.answering.evidence import select_evidence
from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration


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


def test_threshold_count_and_token_budget_assign_one_outcome_per_candidate() -> None:
    configuration = RetrievalConfiguration.milestone_one()
    candidates = (
        candidate(chunk_id="below", ordinal=0, content="below", similarity=0.649),
        candidate(chunk_id="one", ordinal=2, content="one unique", token_count=1000),
        candidate(chunk_id="two", ordinal=4, content="two unique", token_count=1000),
        candidate(chunk_id="three", ordinal=6, content="three unique", token_count=1000),
        candidate(chunk_id="over-budget", ordinal=8, content="four unique", token_count=1),
    )

    result = select_evidence(candidates, configuration)

    assert [item.outcome for item in result.decisions] == [
        "BELOW_THRESHOLD",
        "SELECTED",
        "SELECTED",
        "SELECTED",
        "TOKEN_BUDGET_EXCEEDED",
    ]
    assert sum(item.candidate.token_count for item in result.selected) == 3000


def test_similarity_boundary_qualifies_and_evidence_count_stops_at_five() -> None:
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
        "TOKEN_BUDGET_EXCEEDED",
    ]
