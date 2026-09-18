from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools.lifecycle_projection import (
    ToolLifecycleObservationFailure,
    ToolLifecycleProjectionReader,
    ToolLifecycleUnavailable,
)


@dataclass(frozen=True)
class _Proposal:
    proposal_id: str = "proposal-1"
    workspace_id: str = "workspace-a"
    state: str = "approved"
    revision: int = 3
    decision_at: datetime | None = datetime(2026, 1, 1, tzinfo=UTC)
    decision_actor_kind: str | None = "human"
    execution: object | None = None
    audit: tuple[object, ...] = ()
    provider_api_key: str = "must-not-escape"


@dataclass(frozen=True)
class _Observation:
    sequence: int = 1
    observation_type: str = "provider_outcome_not_found"
    rejection_code: str | None = "provider_request_rejected"
    observed_at: datetime = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)


@dataclass(frozen=True)
class _Execution:
    lifecycle: str = "failed"
    revision: int = 2
    generation: int = 1
    observations: tuple[object, ...] = (_Observation(),)
    rejection_code: str | None = "provider_request_rejected"
    external_resource_reference: str | None = "provider-secret-reference"
    finalized_at: datetime | None = datetime(2026, 1, 1, 0, 2, tzinfo=UTC)


class _Store:
    def __init__(self, proposals: list[object] | None = None, error: Exception | None = None):
        self.proposals = proposals or []
        self.error = error
        self.list_calls = 0

    def list_proposals(self, workspace_id: str) -> list[object]:
        self.list_calls += 1
        if self.error:
            raise self.error
        return [proposal for proposal in self.proposals if proposal.workspace_id == workspace_id]


def test_authorized_read_returns_sanitized_lifecycle_items() -> None:
    reader = ToolLifecycleProjectionReader(_Store([_Proposal()]))

    result = reader.read_lifecycle(
        workspace_id="workspace-a",
        principal=WorkspacePrincipal("workspace-a", "operator"),
    )

    assert result.availability == "available"
    item = result.items[0]
    assert item.proposal.state == "approved"
    assert item.proposal.revision == 3
    assert item.approval.decision == "approved"
    assert item.approval.actor_kind == "human"
    assert not hasattr(item, "provider_api_key")
    assert "must-not-escape" not in repr(item)


def test_empty_workspace_is_explicitly_unavailable() -> None:
    reader = ToolLifecycleProjectionReader(_Store())

    result = reader.read_lifecycle(
        workspace_id="workspace-a",
        principal=WorkspacePrincipal("workspace-a", "operator"),
    )

    assert isinstance(result, ToolLifecycleUnavailable)
    assert result.availability == "unavailable"


def test_execution_and_reconciliation_are_projected_without_provider_reference() -> None:
    reader = ToolLifecycleProjectionReader(_Store([_Proposal(execution=_Execution())]))

    result = reader.read_lifecycle(
        workspace_id="workspace-a",
        principal=WorkspacePrincipal("workspace-a", "operator"),
    )

    item = result.items[0]
    assert item.execution is not None
    assert item.execution.lifecycle == "failed"
    assert item.execution.failure_code == "provider_request_rejected"
    assert item.reconciliation is not None
    assert item.reconciliation.status == "observed"
    assert "provider-secret-reference" not in repr(item)


def test_store_failure_is_explicit_observation_failure_without_exception_details() -> None:
    reader = ToolLifecycleProjectionReader(_Store(error=RuntimeError("password=secret")))

    result = reader.read_lifecycle(
        workspace_id="workspace-a",
        principal=WorkspacePrincipal("workspace-a", "operator"),
    )

    assert isinstance(result, ToolLifecycleObservationFailure)
    assert result.availability == "observation_failure"
    assert result.code == "TOOL_LIFECYCLE_OBSERVATION_FAILED"
    assert "password" not in repr(result)
    assert "secret" not in repr(result)


def test_cross_workspace_is_rejected_before_store_lookup() -> None:
    store = _Store([_Proposal()])
    reader = ToolLifecycleProjectionReader(store)

    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        reader.read_lifecycle(
            workspace_id="workspace-a",
            principal=WorkspacePrincipal("workspace-b", "operator"),
        )

    assert store.list_calls == 0
