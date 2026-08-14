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
