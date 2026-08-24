from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from knora.tools.contracts import freeze_canonical_value
from knora.tools.execution_types import (
    AcquireApplied,
    AcquireDenied,
    AcquireInProgress,
    AcquireRevisionConflict,
    AdmissionApplied,
    AdmissionDenied,
    AuthorizedExecutionBindingSnapshot,
    DispatchAdmissionWitness,
    ExecutionRecoverySeed,
    FinalizeApplied,
    ObservationApplied,
    StoredExecution,
    StoreExecutionFenced,
)
from knora.tools.proposal_types import ApprovalActor, AuditProjection, ProposalDecision


@dataclass(frozen=True, slots=True)
class _StoredProposal:
    proposal_id: str
    workspace_id: str
    state: str
    revision: int
    capability_id: str
    capability_version: str
    capability_digest: str
    binding_id: str
    binding_version: str
    binding_digest: str
    policy_id: str
    policy_version: str
    policy_digest: str
    policy_snapshot: Mapping[str, Any]
    target_reference: str
    target_reference_digest: str
    target_reference_id: str
    target_resource_identity_digest: str
    target_resource_claims_digest: str
    resource_kind: str
    parameters: Mapping[str, str]
    parameters_digest: str
    request_fingerprint: str
    caller_principal_id: str
    caller_key_id: str
    proposal_actor_id: str
    proposal_actor_kind: str
    proposal_actor_authority_id: str
    proposal_actor_authority_version: str
    proposal_actor_authority_digest: str
    logical_execution_id: str
    created_at: datetime
    expires_at: datetime
    decision_at: datetime | None = None
    decision_actor_id: str | None = None
    decision_actor_kind: str | None = None
    decision_authority_id: str | None = None
    decision_authority_version: str | None = None
    decision_authority_digest: str | None = None
    decision_reason: str | None = None
    execution_stale_reason: str | None = None
    execution: StoredExecution | None = None
    admission: DispatchAdmissionWitness | None = None
    audit: tuple[AuditProjection, ...] = ()

    def __post_init__(self) -> None:
        frozen_policy = freeze_canonical_value(self.policy_snapshot)
        frozen_parameters = freeze_canonical_value(self.parameters)
        if not isinstance(frozen_policy, Mapping) or not isinstance(frozen_parameters, Mapping):
            raise ValueError("stored proposal mappings are required")
        object.__setattr__(self, "policy_snapshot", frozen_policy)
        object.__setattr__(self, "parameters", frozen_parameters)
        object.__setattr__(self, "audit", tuple(self.audit))


@dataclass(frozen=True, slots=True)
class _DecisionResult:
    applied: bool
    proposal: _StoredProposal


class ToolActionStore(Protocol):
    def create_proposal(self, proposal: _StoredProposal) -> _StoredProposal: ...

    def read_proposal(self, workspace_id: str, proposal_id: str) -> _StoredProposal | None: ...

    def decide_proposal(
        self,
        workspace_id: str,
        proposal_id: str,
        expected_revision: int,
        decision: ProposalDecision,
        actor: ApprovalActor,
        reason_code: str | None,
        decided_at: datetime,
    ) -> _DecisionResult: ...

    def mark_execution_stale(
        self, workspace_id: str, proposal_id: str, reason_code: str
    ) -> _StoredProposal: ...

    def acquire_execution(
        self,
        workspace_id: str,
        proposal_id: str,
        expected_revision: int,
        owner: str,
        lease_duration: timedelta,
        binding_snapshot: AuthorizedExecutionBindingSnapshot,
        requested_at: datetime,
    ) -> AcquireApplied | AcquireInProgress | AcquireDenied | AcquireRevisionConflict: ...

    def authorize_and_admit_dispatch(
        self,
        workspace_id: str,
        proposal_id: str,
        owner: str,
        generation: int,
        requested_at: datetime,
        build_witness: Callable[
            [_StoredProposal, StoredExecution, int, int, datetime],
            DispatchAdmissionWitness | AdmissionDenied,
        ],
    ) -> AdmissionApplied | AdmissionDenied | StoreExecutionFenced: ...

    def record_execution_observation(
        self,
        workspace_id: str,
        proposal_id: str,
        owner: str,
        generation: int,
        observation_type: str,
        rejection_code: str | None,
        external_resource_reference: str | None,
        requested_at: datetime,
    ) -> ObservationApplied | StoreExecutionFenced: ...

    def finalize_execution(
        self,
        workspace_id: str,
        proposal_id: str,
        owner: str,
        generation: int,
        lifecycle: str,
        rejection_code: str | None,
        external_resource_reference: str | None,
        requested_at: datetime,
    ) -> FinalizeApplied | StoreExecutionFenced: ...

    def read_execution_recovery_seed(
        self, workspace_id: str, proposal_id: str
    ) -> ExecutionRecoverySeed | None: ...
