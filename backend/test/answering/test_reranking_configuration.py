"""Unit tests for deployment-wide reranking configuration and resolver."""

from __future__ import annotations

import pytest

from knora.answering.reranking_configuration import (
    DeploymentRerankingConfigurationResolver,
    RerankingConfiguration,
    resolve_reranking_configuration,
)
from knora.answering.retrieval_configuration import (
    resolve_retrieval_configuration,
    retrieval_configuration_for_id,
)
from knora.answering.stores import RetrievalConfiguration


def test_reranking_configuration_cloudflare_defaults_and_digest() -> None:
    config = RerankingConfiguration.cloudflare_bge_reranker_v1()
    assert config.id == "reranking-cloudflare-bge-base-v1"
    assert config.provider == "cloudflare-workers-ai"
    assert config.model == "@cf/baai/bge-reranker-base"
    assert config.revision == "cf-v1"
    assert config.max_candidates == 100
    assert config.timeout_seconds == 30.0
    assert config.fallback_policy == "fallback_dbsf_sdm"
    assert config.normalization == "min_max"
    assert config.weight_reranker == 0.50
    assert config.weight_retrieval == 0.50
    assert config.mmr_enabled is True
    assert config.mmr_lambda == 0.70
    assert config.max_evidence_chunks == 5
    assert config.max_evidence_tokens == 3000

    digest = config.digest()
    assert isinstance(digest, str)
    assert len(digest) == 64
    # Deterministic digest across calls
    assert config.digest() == digest


def test_reranking_configuration_rejects_invalid_weights() -> None:
    # Negative weight
    with pytest.raises(ValueError, match="weights must be non-negative"):
        RerankingConfiguration(
            id="test-bad",
            provider="test",
            model="test",
            weight_reranker=-0.1,
            weight_retrieval=0.5,
        )

    # Zero sum
    with pytest.raises(ValueError, match="sum of weights must be positive"):
        RerankingConfiguration(
            id="test-bad",
            provider="test",
            model="test",
            weight_reranker=0.0,
            weight_retrieval=0.0,
        )

    # Non-finite weight
    with pytest.raises(ValueError, match="weights must be finite numbers"):
        RerankingConfiguration(
            id="test-bad",
            provider="test",
            model="test",
            weight_reranker=float("nan"),
            weight_retrieval=0.5,
        )


def test_reranking_configuration_rejects_invalid_budgets() -> None:
    with pytest.raises(ValueError, match="max_evidence_chunks must be positive"):
        RerankingConfiguration(
            id="test-bad",
            provider="test",
            model="test",
            max_evidence_chunks=0,
        )

    with pytest.raises(ValueError, match="max_evidence_tokens must be positive"):
        RerankingConfiguration(
            id="test-bad",
            provider="test",
            model="test",
            max_evidence_tokens=0,
        )

    with pytest.raises(ValueError, match="max_candidates must be positive"):
        RerankingConfiguration(
            id="test-bad",
            provider="test",
            model="test",
            max_candidates=0,
        )


def test_reranking_configuration_rejects_invalid_normalization_and_mmr() -> None:
    with pytest.raises(ValueError, match="unsupported normalization"):
        RerankingConfiguration(
            id="test-bad",
            provider="test",
            model="test",
            normalization="unsupported_norm",
        )

    with pytest.raises(ValueError, match="mmr_lambda must be between 0.0 and 1.0"):
        RerankingConfiguration(
            id="test-bad",
            provider="test",
            model="test",
            mmr_lambda=1.5,
        )


def test_resolve_reranking_configuration() -> None:
    assert resolve_reranking_configuration(None) is None
    assert resolve_reranking_configuration("") is None

    cf = resolve_reranking_configuration("reranking-cloudflare-bge-base-v1")
    assert cf is not None
    assert cf.model == "@cf/baai/bge-reranker-base"

    det = resolve_reranking_configuration("reranking-deterministic-v1")
    assert det is not None
    assert det.model == "deterministic-reranker-v1"

    with pytest.raises(ValueError, match="unsupported reranking configuration"):
        resolve_reranking_configuration("non-existent-config")


def test_deployment_resolver_and_immutable_request_snapshot() -> None:
    c1 = RerankingConfiguration.cloudflare_bge_reranker_v1()
    c2 = RerankingConfiguration.deterministic_v1()

    resolver = DeploymentRerankingConfigurationResolver(c1)
    snapshot = resolver.resolve()
    assert snapshot == c1

    # An administrator switching deployment configuration between requests
    # does not mutate previously resolved snapshots held by active requests.
    new_resolver = DeploymentRerankingConfigurationResolver(c2)
    assert new_resolver.resolve() == c2
    assert snapshot == c1  # original snapshot remains unmodified


def test_retrieval_configuration_hybrid_rerank_top8_v3() -> None:
    config = RetrievalConfiguration.hybrid_rerank_top8_v3()
    assert config.id == "retrieval-hybrid-rerank-top8-v3"
    assert config.strategy == "hybrid"
    assert config.fusion_policy_id == "dbsf-v1"
    assert config.sdm_policy_id == "sdm-metzler-croft-2005-v1"
    assert config.reranking_policy_id == "cross-encoder-bge-reranker-base-v1"
    assert config.max_evidence_chunks == 5
    assert config.max_evidence_tokens == 3000

    resolved = retrieval_configuration_for_id("retrieval-hybrid-rerank-top8-v3")
    assert resolved == config

    resolved_dep = resolve_retrieval_configuration(
        "retrieval-hybrid-rerank-top8-v3", vector_min_similarity=None
    )
    assert resolved_dep == config
