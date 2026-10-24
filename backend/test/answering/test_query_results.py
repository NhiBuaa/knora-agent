"""Tests for cross-query candidate merging, group provenance, and fairness."""

from __future__ import annotations

from knora.answering.query_results import merge_cross_query_candidates
from knora.answering.stores import RetrievalCandidate


def _make_candidate(chunk_id: str, fusion_score: float) -> RetrievalCandidate:
    return RetrievalCandidate(
        document_id="doc-1",
        document_version_id="ver-1",
        source_key="policy",
        source_name="policy.pdf",
        chunk_set_id="cset-1",
        embedding_set_id=None,
        embedding_configuration_id=None,
        chunk_id=chunk_id,
        chunk_ordinal=0,
        heading_path=(),
        start_line=1,
        end_line=1,
        content=f"Content of {chunk_id}",
        content_checksum=f"chk-{chunk_id}",
        token_count=10,
        cosine_distance=None,
        similarity=None,
        fusion_score=fusion_score,
        index_generation_id="gen-1",
    )


def test_merge_cross_query_deduplication_and_provenance():
    # chunk-shared appears in both sub_1 and sub_2
    c_shared = _make_candidate("chunk-shared", fusion_score=0.85)
    c_sub1 = _make_candidate("chunk-sub1", fusion_score=0.90)
    c_sub2 = _make_candidate("chunk-sub2", fusion_score=0.80)

    results = {
        "query_1": [c_sub1, c_shared],
        "query_2": [c_shared, c_sub2],
    }
    mapping = {"query_1": "sub_1", "query_2": "sub_2"}

    merged = merge_cross_query_candidates(results, subquestion_mapping=mapping)

    # Total 3 unique chunks
    assert merged.total_candidates == 3
    chunk_ids = [c.chunk_id for c in merged.candidates]
    assert len(chunk_ids) == len(set(chunk_ids))

    # chunk-shared recorded provenance for both sub_1 and sub_2
    assert merged.coverage_mapping["chunk-shared"] == ("sub_1", "sub_2")
    assert merged.coverage_mapping["chunk-sub1"] == ("sub_1",)
    assert merged.coverage_mapping["chunk-sub2"] == ("sub_2",)


def test_merge_cross_query_group_fairness():
    # sub_1 has 10 candidates, sub_2 has 2 candidates
    # Round-robin selection ensures sub_2 gets early ranks
    cands_1 = [_make_candidate(f"chunk-1-{i}", fusion_score=0.9 - i * 0.05) for i in range(10)]
    cands_2 = [_make_candidate(f"chunk-2-{i}", fusion_score=0.7 - i * 0.05) for i in range(2)]

    results = {"q1": cands_1, "q2": cands_2}
    mapping = {"q1": "sub_1", "q2": "sub_2"}

    merged = merge_cross_query_candidates(results, subquestion_mapping=mapping)

    # First rank from sub_1, second rank from sub_2
    assert merged.candidates[0].chunk_id == "chunk-1-0"
    assert merged.candidates[1].chunk_id == "chunk-2-0"


def test_merge_cross_query_max_cap():
    cands = [_make_candidate(f"chunk-{i}", fusion_score=0.5) for i in range(150)]
    results = {"q1": cands}

    merged = merge_cross_query_candidates(results, max_total_candidates=100)
    assert merged.total_candidates == 100
    assert len(merged.candidates) == 100


def test_cap_is_enforced_inside_round_robin():
    result = merge_cross_query_candidates(
        {f"q{i}": [_make_candidate(f"c{i}", 0.5)] for i in range(3)},
        max_total_candidates=2,
    )
    assert result.total_candidates == 2
    assert len(result.candidates) == 2


def test_merge_cross_query_rejects_non_positive_cap():
    import pytest

    with pytest.raises(ValueError, match="max_total_candidates must be positive"):
        merge_cross_query_candidates(
            {"q1": [_make_candidate("c1", 0.5)]},
            max_total_candidates=0,
        )
