from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from knora.tools.contracts import freeze_canonical_value
from knora.tools.proposal_types import ResolvedCapabilityContext
from knora.tools.references import AuthorizedExternalResource


class ProviderTerminalFailureCode(StrEnum):
    TARGET_NOT_FOUND = "target_not_found"
    VALIDATION_REJECTED = "validation_rejected"
    POLICY_REJECTED = "policy_rejected"


@dataclass(frozen=True, slots=True)
class ExecutionSucceeded:
    proposal_id: str
    logical_execution_id: str
    external_resource_reference: str
    lifecycle: str = field(default="succeeded", init=False)
    outcome_type: str = field(default="execution_succeeded", init=False)


@dataclass(frozen=True, slots=True)
class ExecutionFailed:
    proposal_id: str
    logical_execution_id: str
    rejection_code: str
    lifecycle: str = field(default="failed", init=False)
    outcome_type: str = field(default="execution_failed", init=False)


@dataclass(frozen=True, slots=True)
class ExecutionIndeterminate:
    proposal_id: str
    logical_execution_id: str
    lifecycle: str = field(default="executing", init=False)
    outcome_type: str = field(default="execution_indeterminate", init=False)
    reason_code: str = field(default="indeterminate_external_outcome", init=False)


@dataclass(frozen=True, slots=True)
class ExecutionInProgress:
    proposal_id: str
    logical_execution_id: str
    lifecycle: str = field(default="executing", init=False)
    outcome_type: str = field(default="execution_in_progress", init=False)
    reason_code: str = "execution_in_progress"


@dataclass(frozen=True, slots=True)
class ExecutionFenced:
    proposal_id: str
    logical_execution_id: str
    lifecycle: str = field(default="executing", init=False)
    outcome_type: str = field(default="execution_fenced", init=False)
    reason_code: str = field(default="execution_fenced", init=False)


@dataclass(frozen=True, slots=True)
class ProposalNotExecutable:
    proposal_id: str
    logical_execution_id: str
    reason_code: str
    lifecycle: str = field(default="executing", init=False)
    outcome_type: str = field(default="proposal_not_executable", init=False)


ExecutionResult = (
    ExecutionSucceeded
    | ExecutionFailed
    | ExecutionIndeterminate
    | ExecutionInProgress
    | ExecutionFenced
    | ProposalNotExecutable
)


@dataclass(frozen=True, slots=True)
class AuthorizedExecutionBindingSnapshot:
    capability_id: str
    capability_version: str
    capability_digest: str
    binding_id: str
    binding_version: str
    binding_digest: str
    policy_id: str
    policy_version: str
    policy_digest: str

    @classmethod
    def from_context(cls, current: ResolvedCapabilityContext) -> AuthorizedExecutionBindingSnapshot:
        return cls(
            current.capability_id,
            current.capability_version,
            current.capability_digest,
            current.binding_id,
            current.binding_version,
            current.binding_digest,
            current.policy.policy_id,
            current.policy.policy_version,
            current.policy.policy_digest,
        )


@dataclass(frozen=True, slots=True)
class AcquireWitness:
    acquisition_identity: str
    acquisition_digest: str
    proposal_id: str
    logical_execution_id: str
    request_fingerprint: str
    owner: str
    generation: int
    lease_started_at: datetime
    lease_expires_at: datetime
    binding_snapshot: AuthorizedExecutionBindingSnapshot
    acquisition_audit_identity: str
    acquisition_audit_digest: str


@dataclass(frozen=True, slots=True)
class DispatchAdmissionWitness:
    admission_schema_version: int
    admission_identity: str
    admission_digest: str
    purpose: str
    workspace_id: str
    proposal_id: str
    logical_execution_id: str
    request_fingerprint: str
    capability_identity: str
    capability_version: str
    capability_digest: str
    binding_identity: str
    binding_version: str
    binding_digest: str
    policy_identity: str
    policy_version: str
    policy_digest: str
    reference_identity: str
    reference_version: str
    reference_digest: str
    reference_claims_digest: str
    resource_identity_digest: str
    canonical_target_digest: str
    canonical_parameter_digest: str
    complete_intent_digest: str
    reference_key_epoch: int
    workspace_dispatch_epoch: int
    authority_decision_digest: str
    authority_witness_digest: str
    owner: str
    generation: int
    database_issue_time: datetime
    lease_started_at: datetime
    lease_deadline: datetime
    envelope_signing_key_identity: str
    envelope_signing_key_version: str
    routing_snapshot_digest: str
    canonical_envelope_digest: str
    admission_audit_identity: str
    admission_audit_digest: str
    envelope_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ExecutionObservation:
    sequence: int
    observation_type: str
    rejection_code: str | None
    external_resource_reference: str | None
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class StoredExecution:
    lifecycle: str
    revision: int
    generation: int
    owner: str
    lease_started_at: datetime
    lease_expires_at: datetime
    acquisition: AcquireWitness
    observations: tuple[ExecutionObservation, ...] = ()
    rejection_code: str | None = None
    external_resource_reference: str | None = None
    finalized_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExecutionRecoverySeed:
    logical_execution_id: str
    request_fingerprint: str
    binding_snapshot: AuthorizedExecutionBindingSnapshot
    admission_identity: str | None
    envelope_digest: str | None

    @property
    def kind(self) -> str:
        return "NoAdmission" if self.admission_identity is None else "AdmissionOutstanding"


@dataclass(frozen=True, slots=True)
class AdmissionAuthorization:
    current: ResolvedCapabilityContext
    resource: AuthorizedExternalResource
    authority_decision_digest: str
    authority_witness_digest: str
    reference_version: str = "m4r1"
    reference_digest: str = ""


@dataclass(frozen=True, slots=True)
class DispatchEnvelopeClaims:
    admission_identity: str
    admission_claims_digest: str
    workspace_id: str
    proposal_id: str
    logical_execution_id: str
    request_fingerprint: str
    external_scope: str
    provider_routing_handle: str
    intent: Mapping[str, Any]

    def __post_init__(self) -> None:
        frozen = freeze_canonical_value(self.intent)
        if not isinstance(frozen, Mapping):
            raise ValueError("dispatch intent must be a mapping")
        object.__setattr__(self, "intent", frozen)


@dataclass(frozen=True, slots=True)
class AcquireApplied:
    execution: StoredExecution


@dataclass(frozen=True, slots=True)
class AcquireInProgress:
    execution: StoredExecution


@dataclass(frozen=True, slots=True)
class AcquireDenied:
    reason_code: str


@dataclass(frozen=True, slots=True)
class AcquireRevisionConflict:
    current_revision: int


@dataclass(frozen=True, slots=True)
class AdmissionApplied:
    admission: DispatchAdmissionWitness


@dataclass(frozen=True, slots=True)
class AdmissionDenied:
    reason_code: str


@dataclass(frozen=True, slots=True)
class StoreExecutionFenced:
    execution: StoredExecution


@dataclass(frozen=True, slots=True)
class ObservationApplied:
    execution: StoredExecution


@dataclass(frozen=True, slots=True)
class FinalizeApplied:
    execution: StoredExecution
