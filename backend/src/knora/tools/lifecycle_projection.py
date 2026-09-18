"""Secret-safe, workspace-scoped read projection for tool lifecycles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools.proposal_store import ToolActionStore, _StoredProposal
from knora.tools.proposal_types import safe_failure_code

LifecycleAvailability = Literal["available", "unavailable", "observation_failure"]


@dataclass(frozen=True, slots=True)
class ToolLifecycleProposal:
    proposal_id: str
    state: str
    revision: int


@dataclass(frozen=True, slots=True)
class ToolLifecycleApproval:
    decision: str | None
    decided_at: datetime | None
    actor_kind: str | None


@dataclass(frozen=True, slots=True)
class ToolLifecycleExecutionObservation:
    sequence: int
    observation_type: str
    failure_code: str | None
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ToolLifecycleExecution:
    lifecycle: str
    revision: int
    generation: int
    observations: tuple[ToolLifecycleExecutionObservation, ...]
    failure_code: str | None
    finalized_at: datetime | None


@dataclass(frozen=True, slots=True)
class ToolLifecycleReconciliation:
    status: str
    observation_type: str | None
    failure_code: str | None
    observed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ToolLifecycleProjection:
    proposal: ToolLifecycleProposal
    approval: ToolLifecycleApproval
    execution: ToolLifecycleExecution | None
    reconciliation: ToolLifecycleReconciliation | None


@dataclass(frozen=True, slots=True)
class ToolLifecycleListProjection:
    items: tuple[ToolLifecycleProjection, ...]
    availability: Literal["available"] = "available"


@dataclass(frozen=True, slots=True)
class ToolLifecycleUnavailable:
    availability: Literal["unavailable"] = "unavailable"


@dataclass(frozen=True, slots=True)
class ToolLifecycleObservationFailure:
    code: Literal["TOOL_LIFECYCLE_OBSERVATION_FAILED"] = "TOOL_LIFECYCLE_OBSERVATION_FAILED"
    availability: Literal["observation_failure"] = "observation_failure"


ToolLifecycleReadResult = (
    ToolLifecycleListProjection | ToolLifecycleUnavailable | ToolLifecycleObservationFailure
)


class ToolLifecycleProjectionReader:
    """Read lifecycle observations without exposing mutation authority or secrets."""

    def __init__(self, store: ToolActionStore) -> None:
        self._store = store

    def read_lifecycle(
        self, *, workspace_id: str, principal: WorkspacePrincipal
    ) -> ToolLifecycleReadResult:
        if principal.workspace_id != workspace_id:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")

        try:
            proposals = tuple(self._store.list_proposals(workspace_id))
        except Exception:
            return ToolLifecycleObservationFailure()

        if not proposals:
            return ToolLifecycleUnavailable()
        try:
            return ToolLifecycleListProjection(
                items=tuple(self._project_proposal(proposal) for proposal in proposals)
            )
        except Exception:
            return ToolLifecycleObservationFailure()

    @staticmethod
    def _project_proposal(proposal: _StoredProposal) -> ToolLifecycleProjection:
        execution = proposal.execution
        execution_projection = None
        reconciliation = None
        if execution is not None:
            observations = tuple(
                ToolLifecycleExecutionObservation(
                    sequence=observation.sequence,
                    observation_type=_public_observation_type(observation.observation_type),
                    failure_code=safe_failure_code(observation.rejection_code),
                    observed_at=observation.observed_at,
                )
                for observation in execution.observations
            )
            execution_projection = ToolLifecycleExecution(
                lifecycle=execution.lifecycle,
                revision=execution.revision,
                generation=execution.generation,
                observations=observations,
                failure_code=safe_failure_code(execution.rejection_code),
                finalized_at=execution.finalized_at,
            )
            if observations:
                last = observations[-1]
                reconciliation = ToolLifecycleReconciliation(
                    status="observed",
                    observation_type=last.observation_type,
                    failure_code=last.failure_code,
                    observed_at=last.observed_at,
                )

        decision = proposal.state if proposal.state in {"approved", "rejected"} else None
        return ToolLifecycleProjection(
            proposal=ToolLifecycleProposal(
                proposal_id=proposal.proposal_id,
                state=proposal.state,
                revision=proposal.revision,
            ),
            approval=ToolLifecycleApproval(
                decision=decision,
                decided_at=proposal.decision_at,
                actor_kind=proposal.decision_actor_kind,
            ),
            execution=execution_projection,
            reconciliation=reconciliation,
        )


_PUBLIC_OBSERVATION_TYPES = frozenset(
    {
        "execution_started",
        "execution_succeeded",
        "execution_failed",
        "provider_outcome_not_found",
        "provider_observation_unavailable",
        "provider_observation_timeout",
    }
)


def _public_observation_type(value: str) -> str:
    return value if value in _PUBLIC_OBSERVATION_TYPES else "observation_recorded"
