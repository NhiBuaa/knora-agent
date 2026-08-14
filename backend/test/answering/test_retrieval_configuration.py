import pytest

from knora.answering.retrieval_configuration import (
    CALIBRATED_M3_VECTOR_MIN_SIMILARITY,
    DeploymentRetrievalConfigurationResolver,
    resolve_retrieval_configuration,
    retrieval_configuration_for_id,
)


def test_deployment_resolver_returns_pinned_hybrid_configuration_for_any_workspace() -> None:
    resolver = DeploymentRetrievalConfigurationResolver(
        retrieval_configuration_for_id("retrieval-m3-rrf-v1")
    )

    configuration = resolver.resolve(workspace_id="evaluation-m3-v1")

    assert configuration.id == "retrieval-m3-rrf-v1"
    assert configuration.strategy == "hybrid"


def test_resolver_rejects_unknown_configuration_and_blank_workspace() -> None:
    with pytest.raises(ValueError, match="unsupported retrieval configuration"):
        retrieval_configuration_for_id("evaluation-override")
    with pytest.raises(ValueError, match="workspace_id"):
        DeploymentRetrievalConfigurationResolver(
            retrieval_configuration_for_id("retrieval-m1-v1")
        ).resolve(workspace_id="")


def test_v2_resolver_fails_closed_without_calibrated_threshold() -> None:
    with pytest.raises(ValueError, match="exact calibrated numeric threshold"):
        resolve_retrieval_configuration(
            "retrieval-m3-rrf-v2", vector_min_similarity=None
        )


def test_v2_resolver_builds_exact_paired_configuration() -> None:
    result = resolve_retrieval_configuration(
        "retrieval-m3-rrf-v2",
        vector_min_similarity=CALIBRATED_M3_VECTOR_MIN_SIMILARITY,
    )

    assert result.id == "retrieval-m3-rrf-v2"
    assert result.min_similarity == 0.657410732025
    assert result.fusion_policy_id == "rrf-v2"


def test_v2_resolver_rejects_guessed_or_inherited_numeric_threshold() -> None:
    with pytest.raises(ValueError, match="exact calibrated numeric threshold"):
        resolve_retrieval_configuration(
            "retrieval-m3-vector-v2", vector_min_similarity=0.65
        )
