"""Unit tests for score normalization, score combination, and MMR evidence selection."""

from __future__ import annotations

import pytest

from knora.answering.evidence import select_evidence
from knora.answering.reranking import (
    calculate_lexical_jaccard,
    combine_reranking_scores,
    normalize_scores,
    select_evidence_mmr,
)
from knora.answering.reranking_configuration import RerankingConfiguration
from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration


def _make_candidate(
    chunk_id: str,
    content: str,
    *,
    chunk_ordinal: int = 0,
    token_count: int | None = None,
    fusion_score: float = 0.5,
    sdm_score: float | None = None,
) -> RetrievalCandidate:
    tokens = content.split()
    actual_tokens = token_count if token_count is not None else len(tokens)
    return RetrievalCandidate(
        document_id="doc-1",
        document_version_id="ver-1",
        source_key="policy",
        source_name="policy.pdf",
        chunk_set_id="cset-1",
        embedding_set_id=None,
        embedding_configuration_id=None,
        chunk_id=chunk_id,
        chunk_ordinal=chunk_ordinal,
        heading_path=("Chương I",),
        start_line=1,
        end_line=10,
        content=content,
        content_checksum=f"chk-{chunk_id}",
        token_count=actual_tokens,
        cosine_distance=None,
        similarity=None,
        fusion_score=fusion_score,
        sdm_score=sdm_score,
    )


def test_normalize_scores_min_max() -> None:
    scores = [10.0, 20.0, 30.0]
    norm = normalize_scores(scores, method="min_max")
    assert pytest.approx(norm[0]) == 0.0
    assert pytest.approx(norm[1]) == 0.5
    assert pytest.approx(norm[2]) == 1.0

    # Degenerate equal scores
    equal_scores = [5.0, 5.0, 5.0]
    norm_eq = normalize_scores(equal_scores, method="min_max")
    assert norm_eq == [1.0, 1.0, 1.0]

    # Empty
    assert normalize_scores([]) == []


def test_normalize_scores_sigmoid() -> None:
    scores = [0.0, -100.0, 100.0]
    norm = normalize_scores(scores, method="sigmoid")
    assert pytest.approx(norm[0]) == 0.5
    assert norm[1] > 0.0 and norm[1] < 1e-10
    assert norm[2] <= 1.0 and norm[2] > 0.9999999999


def test_calculate_lexical_jaccard() -> None:
    assert calculate_lexical_jaccard("apple banana", "apple banana") == 1.0
    assert calculate_lexical_jaccard("apple banana", "orange grape") == 0.0
    # "apple banana" (2) vs "banana cherry" (2) -> intersection=1, union=3 -> 1/3
    assert pytest.approx(calculate_lexical_jaccard("apple banana", "banana cherry")) == 1.0 / 3.0


def test_combine_reranking_scores_and_tie_breaking() -> None:
    c1 = _make_candidate("c1", "content one", fusion_score=0.8)
    c2 = _make_candidate("c2", "content two", fusion_score=0.4)

    # Reranker reverses order: c2 gets high score, c1 gets low score
    rerank_scores = {"c1": 1.0, "c2": 9.0}

    config = RerankingConfiguration.cloudflare_bge_reranker_v1()
    combined = combine_reranking_scores([c1, c2], rerank_scores, config)

    assert len(combined) == 2
    # c2: rerank_norm=1.0, retrieval_norm=0.0 -> combined = 0.50*1.0 + 0.50*0.0 = 0.50
    # c1: rerank_norm=0.0, retrieval_norm=1.0 -> combined = 0.50*0.0 + 0.50*1.0 = 0.50
    # Scores are tied at 0.50! Tie-break by chunk_id ascending ("c1" < "c2"):
    assert combined[0].chunk_id == "c1"
    assert combined[0].rerank_rank == 1
    assert combined[1].chunk_id == "c2"
    assert combined[1].rerank_rank == 2


def test_select_evidence_mmr_diversification() -> None:
    """MMR penalizes redundant candidate in favor of diverse candidate."""
    # c1: highly relevant about refund policy
    c1 = _make_candidate("c1", "quy định hoàn tiền trong 30 ngày cho khách hàng", fusion_score=0.95)
    # c2: duplicate/near-identical text to c1 (relevance 0.90)
    c2 = _make_candidate(
        "c2", "quy định hoàn tiền trong 30 ngày cho khách hàng thân thiết", fusion_score=0.90
    )
    # c3: completely different topic but relevant: warranty policy (relevance 0.85)
    c3 = _make_candidate("c3", "chính sách bảo hành sản phẩm điện tử 12 tháng", fusion_score=0.85)

    # Assign rerank scores matching fusion
    rerank_scores = {"c1": 0.95, "c2": 0.90, "c3": 0.85}
    config = RerankingConfiguration(
        id="test-mmr-v1",
        provider="test",
        model="test",
        max_evidence_chunks=2,
        max_evidence_tokens=1000,
        mmr_enabled=True,
        mmr_lambda=0.50,  # strong diversity penalty
    )

    combined = combine_reranking_scores([c1, c2, c3], rerank_scores, config)

    # Select evidence with max 2 chunks:
    # First pick is c1.
    # Second pick between c2 (high relevance 0.90, but ~80% overlap with c1)
    # and c3 (relevance 0.85, 0% overlap with c1).
    # With mmr_lambda=0.50:
    # c2 score: 0.50*0.50 - 0.50*0.80 = 0.25 - 0.40 = -0.15
    # c3 score: 0.50*0.00 - 0.50*0.00 = 0.00
    # Therefore c3 MUST be chosen over c2!
    selection = select_evidence_mmr(combined, config)

    assert len(selection.selected) == 2
    selected_ids = [d.candidate.chunk_id for d in selection.selected]
    assert selected_ids == ["c1", "c3"]


def test_select_evidence_mmr_enforces_chunk_and_token_limits() -> None:
    c1 = _make_candidate("c1", "chunk one text", token_count=100, fusion_score=0.9)
    c2 = _make_candidate("c2", "chunk two text", token_count=200, fusion_score=0.8)
    c3 = _make_candidate("c3", "chunk three text", token_count=50, fusion_score=0.7)

    # Token budget = 250 -> c1 (100) + c2 (200) = 300 > 250 -> c2 rejected
    config = RerankingConfiguration(
        id="test-budget",
        provider="test",
        model="test",
        max_evidence_chunks=5,
        max_evidence_tokens=250,
        mmr_enabled=False,
    )

    selection = select_evidence_mmr([c1, c2, c3], config)
    decisions_by_id = {d.candidate.chunk_id: d.outcome for d in selection.decisions}

    assert decisions_by_id["c1"] == "SELECTED"
    assert decisions_by_id["c2"] == "TOKEN_BUDGET_EXCEEDED"
    assert decisions_by_id["c3"] == "SELECTED"  # c3 fits: 100 + 50 = 150 <= 250


def test_select_evidence_facade_routes_to_mmr_when_configured() -> None:
    c1 = _make_candidate("c1", "content one", fusion_score=0.9)
    c2 = _make_candidate("c2", "content two", fusion_score=0.8)

    retrieval_conf = RetrievalConfiguration.hybrid_rerank_top8_v3()
    rerank_conf = RerankingConfiguration.cloudflare_bge_reranker_v1()

    selection = select_evidence([c1, c2], retrieval_conf, reranking_configuration=rerank_conf)
    assert len(selection.selected) == 2
    assert selection.selected[0].outcome == "SELECTED"
    assert selection.selected[1].outcome == "SELECTED"
