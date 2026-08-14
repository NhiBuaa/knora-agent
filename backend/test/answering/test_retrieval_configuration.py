import pytest

from knora.answering.retrieval_configuration import (
    DeploymentRetrievalConfigurationResolver,
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
