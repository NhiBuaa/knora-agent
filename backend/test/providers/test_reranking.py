"""Unit tests for reranking provider core structures and deterministic fake provider."""

from __future__ import annotations

from knora.providers.reranking import (
    DeterministicRerankingProvider,
    RerankingCandidate,
    RerankingResult,
    ScoredRerankingCandidate,
)


def _make_candidate(chunk_id: str, content: str, checksum: str = "abcd1234") -> RerankingCandidate:
    return RerankingCandidate(
        chunk_id=chunk_id,
        document_version_id="ver-1",
        content=content,
        content_checksum=checksum,
    )


def test_reranking_candidate_and_result_structures() -> None:
    c = _make_candidate("c1", "test content")
    assert c.chunk_id == "c1"
    assert c.content == "test content"

    sc = ScoredRerankingCandidate(candidate=c, rerank_score=0.95, rerank_rank=1)
    assert sc.rerank_score == 0.95
    assert sc.rerank_rank == 1

    res = RerankingResult(
        model="test-model",
        scored_candidates=(sc,),
        request_id="req-123",
        duration_ms=5.0,
    )
    assert res.model == "test-model"
    assert len(res.scored_candidates) == 1


def test_deterministic_provider_empty_candidates() -> None:
    provider = DeterministicRerankingProvider()
    res = provider.rerank("query text", [])
    assert res.scored_candidates == ()
    assert res.duration_ms == 0.0


def test_deterministic_provider_ranks_by_overlap_and_tie_breaks() -> None:
    provider = DeterministicRerankingProvider()
    c_exact = _make_candidate("c-exact", "hợp đồng lao động tiền lương", "1000aaaa")
    c_partial = _make_candidate("c-partial", "hợp đồng thuê nhà ở", "1000bbbb")
    c_unrelated = _make_candidate("c-unrelated", "thời tiết hôm nay rất đẹp", "1000cccc")

    res = provider.rerank("hợp đồng lao động", [c_unrelated, c_exact, c_partial])
    assert len(res.scored_candidates) == 3

    # c_exact has overlap 2, c_partial has overlap 1, c_unrelated has overlap 0
    assert res.scored_candidates[0].candidate.chunk_id == "c-exact"
    assert res.scored_candidates[0].rerank_rank == 1
    assert res.scored_candidates[1].candidate.chunk_id == "c-partial"
    assert res.scored_candidates[1].rerank_rank == 2
    assert res.scored_candidates[2].candidate.chunk_id == "c-unrelated"
    assert res.scored_candidates[2].rerank_rank == 3
