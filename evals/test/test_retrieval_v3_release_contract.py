"""Tests for Retrieval V3 release contract, configuration identities and policy boundaries.

Refs #153 (Retrieval V3 Stage 8 Task 1).
"""

from __future__ import annotations

from knora.answering.query_planning import (
    DEFAULT_QUERY_PLAN_POLICY,
    MAX_RERANK_INPUTS,
    MAX_SUBQUESTIONS,
    MAX_TOTAL_SEARCHES,
    MAX_VARIANTS_PER_QUERY,
    PLANNER_TIMEOUT_SECONDS,
)
from knora.answering.query_results import MAX_MERGED_CANDIDATE_POOL
from knora.answering.reranking_configuration import RerankingConfiguration
from knora.answering.retrieval_configuration import RetrievalConfiguration


def test_release_contract_budget_caps_and_defaults() -> None:
    """Verifies that system default configurations adhere strictly to release budget constraints."""
    # Query Planning bounds
    assert DEFAULT_QUERY_PLAN_POLICY == "query-planning-v1"
    assert MAX_SUBQUESTIONS == 4
    assert MAX_VARIANTS_PER_QUERY == 6
    assert MAX_TOTAL_SEARCHES == 8
    assert MAX_RERANK_INPUTS == 100
    assert MAX_MERGED_CANDIDATE_POOL == 100
    assert PLANNER_TIMEOUT_SECONDS == 15.0


def test_release_contract_retrieval_configuration_defaults() -> None:
    """Verifies retrieval configuration constraints (max 5 chunks, max 3000 tokens)."""
    cfg_bm25 = RetrievalConfiguration.bm25_top8_v1()
    assert cfg_bm25.max_evidence_chunks == 5
    assert cfg_bm25.max_evidence_tokens == 3000
    assert cfg_bm25.strategy == "bm25-only"

    cfg_hybrid = RetrievalConfiguration.hybrid_top8_v3(min_similarity=0.65)
    assert cfg_hybrid.max_evidence_chunks == 5
    assert cfg_hybrid.max_evidence_tokens == 3000
    assert cfg_hybrid.strategy == "hybrid"


def test_release_contract_reranking_configuration_defaults() -> None:
    """Verifies Cloudflare BGE reranker and MMR parameters."""
    cfg_cf = RerankingConfiguration.cloudflare_bge_reranker_v1()
    assert cfg_cf.id == "reranking-cloudflare-bge-base-v1"
    assert cfg_cf.provider == "cloudflare-workers-ai"
    assert cfg_cf.model == "@cf/baai/bge-reranker-base"
    assert cfg_cf.max_candidates == 100
    assert cfg_cf.timeout_seconds == 30.0
    assert cfg_cf.fallback_policy == "fallback_dbsf_sdm"
    assert cfg_cf.normalization == "min_max"
    assert cfg_cf.weight_reranker == 0.50
    assert cfg_cf.weight_retrieval == 0.50
    assert cfg_cf.mmr_enabled is True
    assert cfg_cf.mmr_lambda == 0.70
    assert cfg_cf.max_evidence_chunks == 5
    assert cfg_cf.max_evidence_tokens == 3000
