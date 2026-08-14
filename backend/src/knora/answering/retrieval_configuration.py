"""Production retrieval configuration resolution.

The resolver is intentionally a composition seam: HTTP requests never select retrieval strategy.
"""

from dataclasses import dataclass
from typing import Protocol

from knora.answering.stores import RetrievalConfiguration


class RetrievalConfigurationResolver(Protocol):
    def resolve(self, *, workspace_id: str) -> RetrievalConfiguration: ...


@dataclass(frozen=True, slots=True)
class DeploymentRetrievalConfigurationResolver:
    """Resolve one immutable deployment configuration for every production Workspace."""

    configuration: RetrievalConfiguration

    def resolve(self, *, workspace_id: str) -> RetrievalConfiguration:
        if not workspace_id:
            raise ValueError("workspace_id must not be blank")
        return self.configuration


def retrieval_configuration_for_id(configuration_id: str) -> RetrievalConfiguration:
    configurations = {
        "retrieval-m1-v1": RetrievalConfiguration.milestone_one(),
        "retrieval-m3-rrf-v1": RetrievalConfiguration.milestone_three_hybrid(),
    }
    try:
        return configurations[configuration_id]
    except KeyError as error:
        raise ValueError("unsupported retrieval configuration") from error

CALIBRATED_M3_VECTOR_MIN_SIMILARITY = 0.657410732025


def resolve_retrieval_configuration(
    configuration_id: str, *, vector_min_similarity: float | None
) -> RetrievalConfiguration:
    """Resolve the immutable deployment configuration, including calibrated v2 variants."""
    if configuration_id in {"retrieval-m1-v1", "retrieval-m3-rrf-v1"}:
        return retrieval_configuration_for_id(configuration_id)
    if configuration_id not in {"retrieval-m3-vector-v2", "retrieval-m3-rrf-v2"}:
        raise ValueError("unsupported retrieval configuration")
    if vector_min_similarity != CALIBRATED_M3_VECTOR_MIN_SIMILARITY:
        raise ValueError("v2 retrieval requires the exact calibrated numeric threshold")
    if configuration_id == "retrieval-m3-vector-v2":
        return RetrievalConfiguration.milestone_three_vector_v2(
            min_similarity=vector_min_similarity
        )
    return RetrievalConfiguration.milestone_three_hybrid_v2(
        min_similarity=vector_min_similarity
    )
