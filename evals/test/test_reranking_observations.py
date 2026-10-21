"""Tests for cross-encoder reranking trace observations and evidence selection ablations.

Refs #153 (Retrieval V3 Stage 6).
"""

from __future__ import annotations

import math

from knora.answering.evidence import select_evidence
from knora.answering.reranking import (
    calculate_lexical_jaccard,
    combine_reranking_scores,
    normalize_scores,
    select_evidence_mmr,
)
from knora.answering.reranking_configuration import RerankingConfiguration
from knora.answering.retrieval_configuration import RetrievalConfiguration
from knora.answering.stores import RetrievalCandidate


def _make_candidate(
    chunk_id: str,
    content: str,
    *,
    fusion_score: float = 0.5,
    sdm_score: float | None = None,
    token_count: int | None = None,
    chunk_ordinal: int = 0,
) -> RetrievalCandidate:
    tokens = content.split()
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
        heading_path=(),
        start_line=1,
        end_line=1,
        content=content,
        content_checksum="chk-" + chunk_id,
        token_count=token_count if token_count is not None else len(tokens),
        cosine_distance=None,
        similarity=None,
        fusion_score=fusion_score,
        sdm_score=sdm_score,
        index_generation_id="gen-1",
    )


def test_score_normalization_methods_and_bounds():
    """Verify min_max, z_score and sigmoid normalization properties."""
    scores = [1.0, 2.0, 3.0, 4.0, 5.0]

    # Min-max
    norm_mm = normalize_scores(scores, method="min_max")
    assert math.isclose(norm_mm[0], 0.0)
    assert math.isclose(norm_mm[-1], 1.0)
    assert all(0.0 <= s <= 1.0 for s in norm_mm)

    # Sigmoid
    norm_sig = normalize_scores(scores, method="sigmoid")
    assert all(0.0 <= s <= 1.0 for s in norm_sig)
    # Monotonicity preserved
    assert all(norm_sig[i] < norm_sig[i + 1] for i in range(len(norm_sig) - 1))

    # Degenerate all-equal scores
    equal_scores = [3.5, 3.5, 3.5]
    norm_equal = normalize_scores(equal_scores, method="min_max")
    assert norm_equal == [1.0, 1.0, 1.0]


def test_reranking_score_combination_ablation():
    """Verify combination of normalized rerank score and retrieval score.

    Tests that a high cross-encoder score can promote a semantically deep candidate
    even if initial retrieval rank was lower, while preserving tie-breaking on chunk_id.
    """
    c1 = _make_candidate("chunk-a", "general terms overview", fusion_score=0.90, sdm_score=0.90)
    c2 = _make_candidate(
        "chunk-b", "specific legal clause answer", fusion_score=0.60, sdm_score=0.60
    )
    c3 = _make_candidate("chunk-c", "unrelated text background", fusion_score=0.30, sdm_score=0.30)

    config = RerankingConfiguration.cloudflare_bge_reranker_v1()
    # Cross-encoder rates chunk-b much higher
    rerank_scores = {"chunk-a": 0.20, "chunk-b": 0.95, "chunk-c": 0.10}

    combined = combine_reranking_scores([c1, c2, c3], rerank_scores, config)
    assert len(combined) == 3

    # c2 (chunk-b) should now be rank 1
    assert combined[0].chunk_id == "chunk-b"
    assert combined[0].rerank_rank == 1
    assert combined[0].rerank_score is not None

    # Verify audit metadata in rerank_contribution
    contrib = combined[0].rerank_contribution
    assert contrib is not None
    assert contrib["policy_id"] == config.id
    assert contrib["model"] == config.model
    assert contrib["raw_rerank_score"] == 0.95
    assert contrib["weight_reranker"] == config.weight_reranker
    assert contrib["weight_retrieval"] == config.weight_retrieval


def test_mmr_diversity_penalizes_redundant_duplicates():
    """Verify that MMR diversifies selection by penalizing near-identical text chunks."""
    c1 = _make_candidate(
        "chunk-1",
        "hợp đồng lao động xác định thời hạn có hiệu lực từ ngày ký kết giữa các bên",
        fusion_score=0.9,
    )
    # c2 has almost identical content (high lexical Jaccard) with c1
    c2 = _make_candidate(
        "chunk-2",
        "hợp đồng lao động xác định thời hạn có hiệu lực từ ngày ký kết giữa các bên theo luật",
        fusion_score=0.88,
    )
    # c3 has different important facts (mức lương và bảo hiểm xã hội)
    c3 = _make_candidate(
        "chunk-3",
        "mức lương tháng và tiền đóng bảo hiểm xã hội được chi trả vào ngày cuối tháng",
        fusion_score=0.85,
    )

    config = RerankingConfiguration.cloudflare_bge_reranker_v1()
    # MMR enabled with lambda = 0.7
    assert config.mmr_enabled is True
    assert config.mmr_lambda == 0.7

    selection = select_evidence_mmr([c1, c2, c3], config)
    selected_ids = [item.candidate.chunk_id for item in selection.selected]

    # chunk-1 is selected first (highest relevance)
    assert selected_ids[0] == "chunk-1"

    # chunk-3 selected over chunk-2 because chunk-2 is heavily penalized by similarity to chunk-1
    assert "chunk-3" in selected_ids
    assert selected_ids[1] == "chunk-3"


def test_lexical_jaccard_similarity_normalization():
    """Verify NFKC lowercase normalization and token Jaccard calculation."""
    text1 = "Tiền Lương   tháng 13"
    text2 = "tiền lương tháng 13!"

    sim = calculate_lexical_jaccard(text1, text2)
    # After normalization and tokenization, identical tokens -> Jaccard = 1.0
    assert math.isclose(sim, 1.0)

    # Disjoint tokens -> Jaccard = 0.0
    sim_disjoint = calculate_lexical_jaccard("hợp đồng lao động", "thời tiết hôm nay")
    assert math.isclose(sim_disjoint, 0.0)


def test_evidence_selection_backward_compatibility():
    """Ensure select_evidence without reranking config preserves legacy containment."""
    c1 = _make_candidate("c1", "exact content one", fusion_score=0.8, chunk_ordinal=0)
    c2 = _make_candidate("c2", "exact content one extra words", fusion_score=0.7, chunk_ordinal=1)

    retrieval_config = RetrievalConfiguration.milestone_one()
    selection = select_evidence([c1, c2], retrieval_config)

    # Legacy containment eliminates c2 as REDUNDANT_OVERLAP
    assert len(selection.selected) == 1
    assert selection.selected[0].candidate.chunk_id == "c1"
    assert selection.decisions[1].outcome == "REDUNDANT_OVERLAP"
