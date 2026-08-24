from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from threading import RLock
from uuid import uuid4

from knora.domain.errors import KnoraError
from knora.tools.contracts import canonical_digest_v1
from knora.tools.execution_types import (
    AcquireApplied,
    AcquireDenied,
    AcquireInProgress,
    AcquireRevisionConflict,
    AcquireWitness,
    AdmissionApplied,
    AdmissionDenied,
    AuthorizedExecutionBindingSnapshot,
    DispatchAdmissionWitness,
    ExecutionObservation,
    ExecutionRecoverySeed,
    FinalizeApplied,
    ObservationApplied,
    StoredExecution,
    StoreExecutionFenced,
)
from knora.tools.proposal_store import _DecisionResult, _StoredProposal
from knora.tools.proposal_types import ApprovalActor, AuditProjection, ProposalDecision


class InMemoryToolActionStore:
    """Deterministic proposal and generation-1 execution state for unit tests."""

    def __init__(self) -> None:
        self._proposals: dict[str, _StoredProposal] = {}
        self._lock = RLock()
        self.reference_key_epoch = 1
        self.workspace_dispatch_epochs: dict[str, int] = {}

    def create_proposal(self, proposal: _StoredProposal) -> _StoredProposal:
        if not proposal.audit:
            proposal = replace(
                proposal,
                audit=(
                    AuditProjection(
                        sequence=1,
                        event_type="proposed",
                        actor_id=proposal.proposal_actor_id,
                        actor_kind=proposal.proposal_actor_kind,
                        payload={
                            "caller_principal_id": proposal.caller_principal_id,
                            "authority_id": proposal.proposal_actor_authority_id,
                            "authority_version": proposal.proposal_actor_authority_version,
                            "authority_digest": proposal.proposal_actor_authority_digest,
                        },
                    ),
                ),
            )
        with self._lock:
            self._proposals[proposal.proposal_id] = proposal
            return proposal

    def read_proposal(self, workspace_id: str, proposal_id: str) -> _StoredProposal | None:
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if proposal is None or proposal.workspace_id != workspace_id:
                return None
            return proposal

    def decide_proposal(
        self,
        workspace_id: str,
        proposal_id: str,
        expected_revision: int,
        decision: ProposalDecision,
        actor: ApprovalActor,
        reason_code: str | None,
        decided_at: datetime,
    ) -> _DecisionResult:
        with self._lock:
            proposal = self.read_proposal(workspace_id, proposal_id)
            if proposal is None:
                raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
            if proposal.state != "proposed" or proposal.revision != expected_revision:
                return _DecisionResult(False, proposal)
            decided = replace(
                proposal,
                state=decision.value,
                revision=proposal.revision + 1,
                decision_actor_id=actor.actor_id,
                decision_actor_kind=actor.actor_kind,
                decision_authority_id=actor.authority.authority_id,
                decision_authority_version=actor.authority.authority_version,
                decision_authority_digest=actor.authority.authority_digest,
                decision_reason=reason_code,
                decision_at=decided_at,
                audit=proposal.audit
                + (
                    AuditProjection(
                        sequence=len(proposal.audit) + 1,
                        event_type=decision.value,
                        actor_id=actor.actor_id,
                        actor_kind=actor.actor_kind,
                        payload={
                            "reason_code": reason_code,
                            "revision": proposal.revision + 1,
                            "authority_id": actor.authority.authority_id,
                            "authority_version": actor.authority.authority_version,
                            "authority_digest": actor.authority.authority_digest,
                        },
                    ),
                ),
            )
            self._proposals[proposal_id] = decided
            return _DecisionResult(True, decided)

    def mark_execution_stale(
        self, workspace_id: str, proposal_id: str, reason_code: str
    ) -> _StoredProposal:
        with self._lock:
            proposal = self.read_proposal(workspace_id, proposal_id)
            if proposal is None:
                raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
            if proposal.execution_stale_reason is None:
                proposal = replace(
                    proposal,
                    execution_stale_reason=reason_code,
                    audit=proposal.audit
                    + (
                        AuditProjection(
                            len(proposal.audit) + 1,
                            "approval_invalidated",
                            "compatibility-checker-v1",
                            "system",
                            {
                                "reason_code": reason_code,
                                "approval_validity": "invalidated",
                            },
                        ),
                    ),
                )
                self._proposals[proposal_id] = proposal
            return proposal

    def acquire_execution(
        self,
        workspace_id: str,
        proposal_id: str,
        expected_revision: int,
        owner: str,
        lease_duration: timedelta,
        binding_snapshot: AuthorizedExecutionBindingSnapshot,
        requested_at: datetime,
    ) -> AcquireApplied | AcquireInProgress | AcquireDenied | AcquireRevisionConflict:
        with self._lock:
            proposal = self.read_proposal(workspace_id, proposal_id)
            if proposal is None:
                raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
            if proposal.execution is not None:
                return AcquireInProgress(proposal.execution)
            if proposal.state != "approved":
                return AcquireDenied("not_approved")
            if proposal.execution_stale_reason is not None:
                return AcquireDenied(proposal.execution_stale_reason)
            if proposal.revision != expected_revision:
                return AcquireRevisionConflict(proposal.revision)
            if requested_at >= proposal.expires_at:
                return AcquireDenied("expired")
            acquisition_identity = str(uuid4())
            audit_identity = str(uuid4())
            lease_expires_at = requested_at + lease_duration
            core = {
                "proposal_id": proposal.proposal_id,
                "logical_execution_id": proposal.logical_execution_id,
                "request_fingerprint": proposal.request_fingerprint,
                "owner": owner,
                "generation": 1,
                "lease_started_at": requested_at,
                "lease_expires_at": lease_expires_at,
                "binding_snapshot": asdict(binding_snapshot),
            }
            acquisition_digest = canonical_digest_v1(core)
            audit_digest = canonical_digest_v1(
                {
                    "event_type": "execution_acquired",
                    "identity": audit_identity,
                    "acquisition_digest": acquisition_digest,
                }
            )
            witness = AcquireWitness(
                acquisition_identity,
                acquisition_digest,
                proposal.proposal_id,
                proposal.logical_execution_id,
                proposal.request_fingerprint,
                owner,
                1,
                requested_at,
                lease_expires_at,
                binding_snapshot,
                audit_identity,
                audit_digest,
            )
            execution = StoredExecution(
                "executing",
                expected_revision + 1,
                1,
                owner,
                requested_at,
                lease_expires_at,
                witness,
            )
            acquired = replace(
                proposal,
                state="executing",
                revision=expected_revision + 1,
                execution=execution,
                audit=proposal.audit
                + (
                    AuditProjection(
                        len(proposal.audit) + 1,
                        "execution_acquired",
                        owner,
                        "system",
                        {
                            "acquisition_identity": acquisition_identity,
                            "acquisition_digest": acquisition_digest,
                            "logical_execution_id": proposal.logical_execution_id,
                            "request_fingerprint": proposal.request_fingerprint,
                            "generation": 1,
                            "lease_started_at": requested_at,
                            "lease_expires_at": lease_expires_at,
                            "audit_identity": audit_identity,
                            "audit_digest": audit_digest,
                        },
                    ),
                ),
            )
            self._proposals[proposal_id] = acquired
            return AcquireApplied(execution)

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
    ) -> AdmissionApplied | AdmissionDenied | StoreExecutionFenced:
        with self._lock:
            proposal = self.read_proposal(workspace_id, proposal_id)
            if proposal is None:
                raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
            execution = proposal.execution
            if execution is None:
                return AdmissionDenied("not_approved")
            if proposal.admission is not None:
                return AdmissionApplied(proposal.admission)
            if (
                execution.owner != owner
                or execution.generation != generation
                or requested_at >= execution.lease_expires_at
            ):
                return StoreExecutionFenced(execution)
            workspace_epoch = self.workspace_dispatch_epochs.setdefault(workspace_id, 1)
            try:
                witness_or_denial = build_witness(
                    proposal,
                    execution,
                    self.reference_key_epoch,
                    workspace_epoch,
                    requested_at,
                )
            except KnoraError as error:
                reason = {
                    "UNAUTHENTICATED": "workspace_access_denied",
                    "WORKSPACE_ACCESS_DENIED": "workspace_access_denied",
                    "INVALID_TOOL_RESOURCE_REFERENCE": "invalid_tool_resource_reference",
                    "TOOL_RESOURCE_ACCESS_DENIED": "resource_access_denied",
                    "TOOL_EXECUTION_NOT_AUTHORIZED": "execution_not_authorized",
                    "TOOL_PROPOSAL_STALE": "proposal_stale",
                }.get(error.code, "resource_access_denied")
                return AdmissionDenied(reason)
            if isinstance(witness_or_denial, AdmissionDenied):
                if witness_or_denial.reason_code.endswith("_mismatch"):
                    self._proposals[proposal_id] = replace(
                        proposal,
                        execution_stale_reason=witness_or_denial.reason_code,
                        audit=proposal.audit
                        + (
                            AuditProjection(
                                len(proposal.audit) + 1,
                                "approval_invalidated",
                                "compatibility-checker-v1",
                                "system",
                                {
                                    "reason_code": witness_or_denial.reason_code,
                                    "approval_validity": "invalidated",
                                },
                            ),
                        ),
                    )
                return witness_or_denial
            witness = witness_or_denial
            admitted = replace(
                proposal,
                admission=witness,
                audit=proposal.audit
                + (
                    AuditProjection(
                        len(proposal.audit) + 1,
                        "dispatch_admitted",
                        owner,
                        "system",
                        {
                            "admission_identity": witness.admission_identity,
                            "admission_digest": witness.admission_digest,
                            "logical_execution_id": witness.logical_execution_id,
                            "generation": witness.generation,
                            "reference_key_epoch": witness.reference_key_epoch,
                            "workspace_dispatch_epoch": witness.workspace_dispatch_epoch,
                            "audit_identity": witness.admission_audit_identity,
                            "audit_digest": witness.admission_audit_digest,
                        },
                    ),
                ),
            )
            self._proposals[proposal_id] = admitted
            return AdmissionApplied(witness)

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
    ) -> ObservationApplied | StoreExecutionFenced:
        with self._lock:
            proposal = self.read_proposal(workspace_id, proposal_id)
            if proposal is None or proposal.execution is None:
                raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
            execution = proposal.execution
            if (
                execution.owner != owner
                or execution.generation != generation
                or requested_at >= execution.lease_expires_at
            ):
                return StoreExecutionFenced(execution)
            observation = ExecutionObservation(
                len(execution.observations) + 1,
                observation_type,
                rejection_code,
                external_resource_reference,
                requested_at,
            )
            updated_execution = replace(
                execution, observations=execution.observations + (observation,)
            )
            self._proposals[proposal_id] = replace(
                proposal,
                execution=updated_execution,
                audit=proposal.audit
                + (
                    AuditProjection(
                        len(proposal.audit) + 1,
                        "execution_observed",
                        owner,
                        "system",
                        {
                            "observation_type": observation_type,
                            "rejection_code": rejection_code,
                            "generation": generation,
                        },
                    ),
                ),
            )
            return ObservationApplied(updated_execution)

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
    ) -> FinalizeApplied | StoreExecutionFenced:
        with self._lock:
            proposal = self.read_proposal(workspace_id, proposal_id)
            if proposal is None or proposal.execution is None:
                raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
            execution = proposal.execution
            if (
                execution.owner != owner
                or execution.generation != generation
                or requested_at >= execution.lease_expires_at
            ):
                return StoreExecutionFenced(execution)
            finalized = replace(
                execution,
                lifecycle=lifecycle,
                rejection_code=rejection_code,
                external_resource_reference=external_resource_reference,
                finalized_at=requested_at,
            )
            self._proposals[proposal_id] = replace(
                proposal,
                state=lifecycle,
                revision=execution.revision + 1,
                execution=finalized,
                audit=proposal.audit
                + (
                    AuditProjection(
                        len(proposal.audit) + 1,
                        lifecycle,
                        owner,
                        "system",
                        {
                            "rejection_code": rejection_code,
                            "external_resource_reference": external_resource_reference,
                            "generation": generation,
                        },
                    ),
                ),
            )
            return FinalizeApplied(finalized)

    def read_execution_recovery_seed(
        self, workspace_id: str, proposal_id: str
    ) -> ExecutionRecoverySeed | None:
        proposal = self.read_proposal(workspace_id, proposal_id)
        if proposal is None or proposal.execution is None:
            return None
        admission = proposal.admission
        return ExecutionRecoverySeed(
            proposal.logical_execution_id,
            proposal.request_fingerprint,
            proposal.execution.acquisition.binding_snapshot,
            None if admission is None else admission.admission_identity,
            None if admission is None else admission.canonical_envelope_digest,
        )

    def advance_dispatch_epochs(
        self,
        workspace_id: str,
        *,
        reference_key: bool = False,
        workspace: bool = True,
    ) -> tuple[int, int]:
        """Advance typed epochs in the global-then-Workspace lock order."""
        with self._lock:
            if reference_key:
                self.reference_key_epoch += 1
            current = self.workspace_dispatch_epochs.setdefault(workspace_id, 1)
            if workspace:
                current += 1
                self.workspace_dispatch_epochs[workspace_id] = current
            return self.reference_key_epoch, current
