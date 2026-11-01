"""Unit tests and hand-computed reference tests for BM25 + Phrase Boost comparator."""

from __future__ import annotations

import pytest
from evals.runners.phrase_boost import (
    PhraseBoostComparator,
    PhraseBoostConfig,
)

from knora.answering.stores import RetrievalCandidate


def _make_candidate(
    chunk_id: str,
    content: str,
    *,
    bm25_score: float = 1.0,
) -> RetrievalCandidate:
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
        content=content,
        content_checksum="chk-" + chunk_id,
        token_count=len(content.split()),
        cosine_distance=None,
        similarity=None,
        bm25_score=bm25_score,
        fusion_score=bm25_score,
    )


def test_hand_computed_reference_case():
    """Verify exact hand-computed values: query [a,b,c], X(bm25=2) vs Y(bm25=4)."""
    # Query has 3 tokens -> 2 adjacent pairs: (a, b) and (b, c)
    # X: content "a b c", bm25 = 2.0 -> matches both pairs -> p(X) = 1.0
    # Y: content "c b a", bm25 = 4.0 -> matches neither pair -> p(Y) = 0.0
    # u(X) = (2 - 2) / (4 - 2) = 0.0
    # u(Y) = (4 - 2) / (4 - 2) = 1.0
    # At lambda = 0.75:
    # score(X) = 0.25 * 0.0 + 0.75 * 1.0 = 0.75
    # score(Y) = 0.25 * 1.0 + 0.75 * 0.0 = 0.25
    cand_x = _make_candidate("X", "a b c", bm25_score=2.0)
    cand_y = _make_candidate("Y", "c b a", bm25_score=4.0)

    config = PhraseBoostConfig(lambda_param=0.75)
    comparator = PhraseBoostComparator(config=config)
    results = comparator.rerank("a b c", [cand_x, cand_y])

    assert len(results) == 2
    res_x = next(r for r in results if r.candidate.chunk_id == "X")
    res_y = next(r for r in results if r.candidate.chunk_id == "Y")

    assert res_x.normalized_bm25 == 0.0
    assert res_x.phrase_ratio == 1.0
    assert pytest.approx(res_x.combined_score, rel=1e-5) == 0.75
    assert res_x.matched_pairs == 2

    assert res_y.normalized_bm25 == 1.0
    assert res_y.phrase_ratio == 0.0
    assert pytest.approx(res_y.combined_score, rel=1e-5) == 0.25
    assert res_y.matched_pairs == 0

    # Reranked order: X is first, Y is second
    assert results[0].candidate.chunk_id == "X"
    assert results[1].candidate.chunk_id == "Y"


def test_lambda_zero_preserves_pure_bm25_order():
    """At lambda = 0.0, order is determined purely by BM25."""
    cand_x = _make_candidate("X", "a b c", bm25_score=2.0)
    cand_y = _make_candidate("Y", "c b a", bm25_score=4.0)

    comparator = PhraseBoostComparator(config=PhraseBoostConfig(lambda_param=0.0))
    results = comparator.rerank("a b c", [cand_x, cand_y])

    assert results[0].candidate.chunk_id == "Y"
    assert results[1].candidate.chunk_id == "X"


def test_repeated_pairs_in_query():
    """Query with repeated pairs counts each query pair index."""
    # Query: "a b a b" -> 3 pairs: (a, b) at index 0, (b, a) at index 1, (a, b) at index 2
    cand = _make_candidate("C1", "a b only once", bm25_score=5.0)

    comparator = PhraseBoostComparator()
    results = comparator.rerank("a b a b", [cand])
    assert len(results) == 1
    # Pair (a, b) matches at query index 0 and 2 -> 2 matched query pairs out of 3
    assert results[0].matched_pairs == 2
    assert pytest.approx(results[0].phrase_ratio, rel=1e-5) == 2.0 / 3.0


def test_equal_or_zero_bm25_scores():
    """When all BM25 scores are identical, normalized_bm25 is 0.0."""
    cand1 = _make_candidate("C1", "first sentence a b", bm25_score=3.0)
    cand2 = _make_candidate("C2", "second sentence b a", bm25_score=3.0)

    comparator = PhraseBoostComparator(config=PhraseBoostConfig(lambda_param=0.5))
    results = comparator.rerank("a b", [cand1, cand2])

    assert results[0].candidate.chunk_id == "C1"
    assert results[0].normalized_bm25 == 0.0
    assert results[1].normalized_bm25 == 0.0
    assert results[0].phrase_ratio == 1.0
    assert results[1].phrase_ratio == 0.0


def test_single_token_or_empty_query():
    """Single token or empty query has phrase_ratio = 0.0 and preserves BM25 order."""
    cand1 = _make_candidate("C1", "token1 content", bm25_score=10.0)
    cand2 = _make_candidate("C2", "token2 content", bm25_score=5.0)

    comparator = PhraseBoostComparator()
    res_single = comparator.rerank("token1", [cand1, cand2])
    assert res_single[0].candidate.chunk_id == "C1"
    assert res_single[0].phrase_ratio == 0.0
    assert res_single[1].phrase_ratio == 0.0

    res_empty = comparator.rerank("", [cand1, cand2])
    assert len(res_empty) == 2
    assert res_empty[0].candidate.chunk_id == "C1"


def test_empty_candidates_returns_empty():
    """Empty candidate pool returns empty list."""
    comparator = PhraseBoostComparator()
    assert comparator.rerank("any query", []) == []


def test_invalid_lambda_rejected():
    """Invalid lambda parameter raises ValueError."""
    with pytest.raises(ValueError, match="lambda_param must be between 0 and 1"):
        PhraseBoostConfig(lambda_param=-0.1)

    with pytest.raises(ValueError, match="lambda_param must be between 0 and 1"):
        PhraseBoostConfig(lambda_param=1.1)


def test_vietnamese_and_special_identifiers():
    """Vietnamese diacritics, AUTH_403, 3.1 and negation handled consistently."""
    query = "lỗi AUTH_403 phiên bản 3.1 không đúng"
    cand_match = _make_candidate(
        "C_match", "mã lỗi auth_403 phiên bản 3.1 không đúng hệ thống", bm25_score=5.0
    )
    cand_perm = _make_candidate("C_perm", "không đúng phiên bản 3.1 auth_403 lỗi", bm25_score=8.0)

    comparator = PhraseBoostComparator(config=PhraseBoostConfig(lambda_param=0.8))
    results = comparator.rerank(query, [cand_match, cand_perm])

    assert results[0].candidate.chunk_id == "C_match"
    assert results[0].phrase_ratio > results[1].phrase_ratio
