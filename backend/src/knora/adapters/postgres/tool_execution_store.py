from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from knora.adapters.postgres.tables import (
    ToolActionAuditEventTable,
    ToolDispatchAdmissionTable,
    ToolDispatchGlobalEpochTable,
    ToolExecutionObservationTable,
    ToolExecutionTable,
    ToolProposalTable,
    ToolWorkspaceDispatchEpochTable,
)
from knora.domain.errors import KnoraError
from knora.tools.contracts import (
    canonical_digest_v1,
    freeze_canonical_value,
    thaw_canonical_value,
)
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
    ExecutionNotStale,
    ExecutionObservation,
    ExecutionRecoverySeed,
    FinalizeApplied,
    ObservationApplied,
    StoredExecution,
    StoreExecutionFenced,
    StoreExecutionFinalized,
    TakeoverApplied,
)
from knora.tools.proposal_store import _StoredProposal


class PostgresExecutionStoreMixin:
    """Own generation-1 execution transactions and record reconstruction."""

    def mark_execution_stale(
        self, workspace_id: str, proposal_id: str, reason_code: str
    ) -> _StoredProposal:
        try:
            with self._session_factory.begin() as session:
                changed = session.execute(
                    update(ToolProposalTable)
                    .where(
                        ToolProposalTable.id == proposal_id,
                        ToolProposalTable.workspace_id == workspace_id,
                        ToolProposalTable.execution_stale_reason.is_(None),
                    )
                    .values(execution_stale_reason=reason_code, updated_at=datetime.now(UTC))
                )
                row = session.scalar(
                    select(ToolProposalTable).where(
                        ToolProposalTable.id == proposal_id,
                        ToolProposalTable.workspace_id == workspace_id,
                    )
                )
                if row is None:
                    raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
                if changed.rowcount == 1:
                    self._append_audit(
                        session,
                        row,
                        event_type="approval_invalidated",
                        actor_id="compatibility-checker-v1",
                        payload={
                            "reason_code": reason_code,
                            "approval_validity": "invalidated",
                        },
                    )
                return self._to_stored(session, row)
        except SQLAlchemyError as error:
            raise KnoraError("PERSISTENCE_OPERATION_FAILED") from error

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
        del requested_at
        try:
            with self._session_factory.begin() as session:
                row = session.scalar(
                    select(ToolProposalTable)
                    .where(
                        ToolProposalTable.id == proposal_id,
                        ToolProposalTable.workspace_id == workspace_id,
                    )
                    .with_for_update()
                )
                if row is None:
                    raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
                existing = session.get(ToolExecutionTable, proposal_id)
                if existing is not None:
                    return AcquireInProgress(self._stored_execution(session, existing))
                if row.state != "approved":
                    return AcquireDenied("not_approved")
                if row.execution_stale_reason is not None:
                    return AcquireDenied(row.execution_stale_reason)
                if row.revision != expected_revision:
                    return AcquireRevisionConflict(row.revision)
                database_time = session.scalar(select(func.clock_timestamp()))
                assert isinstance(database_time, datetime)
                if database_time >= row.expires_at:
                    return AcquireDenied("expired")
                lease_expires_at = database_time + lease_duration
                acquisition_identity = str(uuid4())
                audit_identity = str(uuid4())
                core = {
                    "proposal_id": proposal_id,
                    "logical_execution_id": row.logical_execution_id,
                    "request_fingerprint": row.request_fingerprint,
                    "owner": owner,
                    "generation": 1,
                    "lease_started_at": database_time,
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
                    proposal_id,
                    row.logical_execution_id,
                    row.request_fingerprint,
                    owner,
                    1,
                    database_time,
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
                    database_time,
                    lease_expires_at,
                    witness,
                )
                session.add(self._execution_row(workspace_id, execution))
                session.flush()
                row.state = "executing"
                row.revision = expected_revision + 1
                row.updated_at = datetime.now(UTC)
                self._append_audit(
                    session,
                    row,
                    event_type="execution_acquired",
                    actor_id=owner,
                    payload={
                        "acquisition_identity": acquisition_identity,
                        "acquisition_digest": acquisition_digest,
                        "logical_execution_id": row.logical_execution_id,
                        "request_fingerprint": row.request_fingerprint,
                        "generation": 1,
                        "lease_started_at": database_time,
                        "lease_expires_at": lease_expires_at,
                        "audit_identity": audit_identity,
                        "audit_digest": audit_digest,
                    },
                )
                return AcquireApplied(execution)
        except SQLAlchemyError as error:
            raise KnoraError("PERSISTENCE_OPERATION_FAILED") from error

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
        del requested_at
        try:
            with self._session_factory.begin() as session:
                execution_row = session.scalar(
                    select(ToolExecutionTable)
                    .where(
                        ToolExecutionTable.proposal_id == proposal_id,
                        ToolExecutionTable.workspace_id == workspace_id,
                    )
                    .with_for_update()
                )
                if execution_row is None:
                    raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
                existing = session.scalar(
                    select(ToolDispatchAdmissionTable).where(
                        ToolDispatchAdmissionTable.proposal_id == proposal_id
                    )
                )
                if existing is not None:
                    return AdmissionApplied(self._stored_admission(existing))
                global_epoch = session.scalar(
                    select(ToolDispatchGlobalEpochTable)
                    .where(ToolDispatchGlobalEpochTable.singleton_id == 1)
                    .with_for_update()
                )
                assert global_epoch is not None
                session.execute(
                    pg_insert(ToolWorkspaceDispatchEpochTable)
                    .values(workspace_id=workspace_id, workspace_dispatch_epoch=1)
                    .on_conflict_do_nothing(index_elements=["workspace_id"])
                )
                workspace_epoch = session.scalar(
                    select(ToolWorkspaceDispatchEpochTable)
                    .where(ToolWorkspaceDispatchEpochTable.workspace_id == workspace_id)
                    .with_for_update()
                )
                assert workspace_epoch is not None
                database_time = session.scalar(select(func.clock_timestamp()))
                assert isinstance(database_time, datetime)
                execution = self._stored_execution(session, execution_row)
                if (
                    execution.owner != owner
                    or execution.generation != generation
                    or database_time >= execution.lease_expires_at
                ):
                    return StoreExecutionFenced(execution)
                proposal_row = session.get(ToolProposalTable, proposal_id)
                assert proposal_row is not None
                proposal = self._to_stored(session, proposal_row)
                witness_or_denial = build_witness(
                    proposal,
                    execution,
                    global_epoch.reference_key_epoch,
                    workspace_epoch.workspace_dispatch_epoch,
                    database_time,
                )
                if isinstance(witness_or_denial, AdmissionDenied):
                    if witness_or_denial.reason_code.endswith("_mismatch"):
                        proposal_row.execution_stale_reason = witness_or_denial.reason_code
                        self._append_audit(
                            session,
                            proposal_row,
                            event_type="approval_invalidated",
                            actor_id="compatibility-checker-v1",
                            payload={
                                "reason_code": witness_or_denial.reason_code,
                                "approval_validity": "invalidated",
                            },
                        )
                    return witness_or_denial
                witness = witness_or_denial
                session.add(self._admission_row(witness))
                self._append_audit(
                    session,
                    proposal_row,
                    event_type="dispatch_admitted",
                    actor_id=owner,
                    payload={
                        "admission_identity": witness.admission_identity,
                        "admission_digest": witness.admission_digest,
                        "logical_execution_id": witness.logical_execution_id,
                        "generation": witness.generation,
                        "reference_key_epoch": witness.reference_key_epoch,
                        "workspace_dispatch_epoch": witness.workspace_dispatch_epoch,
                        "audit_identity": witness.admission_audit_identity,
                        "audit_digest": witness.admission_audit_digest,
                    },
                )
                return AdmissionApplied(witness)
        except SQLAlchemyError as error:
            raise KnoraError("PERSISTENCE_OPERATION_FAILED") from error

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
        del requested_at
        try:
            with self._session_factory.begin() as session:
                row = session.scalar(
                    select(ToolExecutionTable)
                    .where(
                        ToolExecutionTable.proposal_id == proposal_id,
                        ToolExecutionTable.workspace_id == workspace_id,
                    )
                    .with_for_update()
                )
                if row is None:
                    raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
                database_time = session.scalar(select(func.clock_timestamp()))
                assert isinstance(database_time, datetime)
                execution = self._stored_execution(session, row)
                if execution.lifecycle != "executing":
                    return StoreExecutionFinalized(execution)
                if (
                    execution.owner != owner
                    or execution.generation != generation
                    or database_time >= execution.lease_expires_at
                ):
                    return StoreExecutionFenced(execution)
                sequence = len(execution.observations) + 1
                session.add(
                    ToolExecutionObservationTable(
                        id=str(uuid4()),
                        proposal_id=proposal_id,
                        workspace_id=workspace_id,
                        sequence=sequence,
                        observation_type=observation_type,
                        rejection_code=rejection_code,
                        external_resource_reference=external_resource_reference,
                        observed_at=database_time,
                    )
                )
                proposal_row = session.get(ToolProposalTable, proposal_id)
                assert proposal_row is not None
                self._append_audit(
                    session,
                    proposal_row,
                    event_type="execution_observed",
                    actor_id=owner,
                    payload={
                        "observation_type": observation_type,
                        "rejection_code": rejection_code,
                        "generation": generation,
                    },
                )
                session.flush()
                return ObservationApplied(self._stored_execution(session, row))
        except SQLAlchemyError as error:
            raise KnoraError("PERSISTENCE_OPERATION_FAILED") from error

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
        del requested_at
        try:
            with self._session_factory.begin() as session:
                row = session.scalar(
                    select(ToolExecutionTable)
                    .where(
                        ToolExecutionTable.proposal_id == proposal_id,
                        ToolExecutionTable.workspace_id == workspace_id,
                    )
                    .with_for_update()
                )
                if row is None:
                    raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
                database_time = session.scalar(select(func.clock_timestamp()))
                assert isinstance(database_time, datetime)
                execution = self._stored_execution(session, row)
                if execution.lifecycle != "executing":
                    return StoreExecutionFinalized(execution)
                if (
                    execution.owner != owner
                    or execution.generation != generation
                    or database_time >= execution.lease_expires_at
                ):
                    return StoreExecutionFenced(execution)
                row.lifecycle = lifecycle
                row.rejection_code = rejection_code
                row.external_resource_reference = external_resource_reference
                row.finalized_at = database_time
                row.revision += 1
                session.flush()
                proposal_row = session.get(ToolProposalTable, proposal_id)
                assert proposal_row is not None
                proposal_row.state = lifecycle
                proposal_row.revision = row.revision
                proposal_row.updated_at = datetime.now(UTC)
                self._append_audit(
                    session,
                    proposal_row,
                    event_type=lifecycle,
                    actor_id=owner,
                    payload={
                        "rejection_code": rejection_code,
                        "external_resource_reference": external_resource_reference,
                        "generation": generation,
                    },
                )
                session.flush()
                return FinalizeApplied(self._stored_execution(session, row))
        except SQLAlchemyError as error:
            raise KnoraError("PERSISTENCE_OPERATION_FAILED") from error

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

    def takeover_stale_execution(
        self,
        workspace_id: str,
        proposal_id: str,
        expected_generation: int,
        recovery_owner: str,
        lease_duration: timedelta,
        requested_at: datetime,
    ) -> TakeoverApplied | ExecutionNotStale | StoreExecutionFenced | StoreExecutionFinalized:
        del requested_at
        try:
            with self._session_factory.begin() as session:
                row = session.scalar(
                    select(ToolExecutionTable)
                    .where(
                        ToolExecutionTable.proposal_id == proposal_id,
                        ToolExecutionTable.workspace_id == workspace_id,
                    )
                    .with_for_update()
                )
                if row is None:
                    raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
                database_time = session.scalar(select(func.transaction_timestamp()))
                assert isinstance(database_time, datetime)
                execution = self._stored_execution(session, row)
                if execution.lifecycle != "executing":
                    return StoreExecutionFinalized(execution)
                if execution.generation != expected_generation:
                    return StoreExecutionFenced(execution)
                if execution.lease_expires_at >= database_time:
                    return ExecutionNotStale(execution)
                row.owner = recovery_owner
                row.generation += 1
                row.lease_started_at = database_time
                row.lease_expires_at = database_time + lease_duration
                row.revision += 1
                proposal_row = session.get(ToolProposalTable, proposal_id)
                assert proposal_row is not None
                proposal_row.revision = row.revision
                proposal_row.updated_at = datetime.now(UTC)
                self._append_audit(
                    session,
                    proposal_row,
                    event_type="execution_taken_over",
                    actor_id=recovery_owner,
                    payload={
                        "previous_generation": execution.generation,
                        "generation": row.generation,
                        "lease_started_at": database_time,
                        "lease_expires_at": row.lease_expires_at,
                    },
                )
                session.flush()
                return TakeoverApplied(self._stored_execution(session, row))
        except SQLAlchemyError as error:
            raise KnoraError("PERSISTENCE_OPERATION_FAILED") from error

    def advance_dispatch_epochs(
        self,
        workspace_id: str,
        *,
        reference_key: bool = False,
        workspace: bool = True,
    ) -> tuple[int, int]:
        """Advance authoritative mutation epochs in global-then-Workspace lock order."""
        try:
            with self._session_factory.begin() as session:
                global_row = session.scalar(
                    select(ToolDispatchGlobalEpochTable)
                    .where(ToolDispatchGlobalEpochTable.singleton_id == 1)
                    .with_for_update()
                )
                assert global_row is not None
                if reference_key:
                    global_row.reference_key_epoch += 1
                session.execute(
                    pg_insert(ToolWorkspaceDispatchEpochTable)
                    .values(workspace_id=workspace_id, workspace_dispatch_epoch=1)
                    .on_conflict_do_nothing(index_elements=["workspace_id"])
                )
                workspace_row = session.scalar(
                    select(ToolWorkspaceDispatchEpochTable)
                    .where(ToolWorkspaceDispatchEpochTable.workspace_id == workspace_id)
                    .with_for_update()
                )
                assert workspace_row is not None
                if workspace:
                    workspace_row.workspace_dispatch_epoch += 1
                session.flush()
                return (
                    global_row.reference_key_epoch,
                    workspace_row.workspace_dispatch_epoch,
                )
        except SQLAlchemyError as error:
            raise KnoraError("PERSISTENCE_OPERATION_FAILED") from error

    @staticmethod
    def _execution_row(workspace_id: str, execution: StoredExecution) -> ToolExecutionTable:
        acquisition = execution.acquisition
        return ToolExecutionTable(
            proposal_id=acquisition.proposal_id,
            workspace_id=workspace_id,
            logical_execution_id=acquisition.logical_execution_id,
            request_fingerprint=acquisition.request_fingerprint,
            lifecycle=execution.lifecycle,
            revision=execution.revision,
            owner=execution.owner,
            generation=execution.generation,
            lease_started_at=execution.lease_started_at,
            lease_expires_at=execution.lease_expires_at,
            binding_snapshot=asdict(acquisition.binding_snapshot),
            acquisition_identity=acquisition.acquisition_identity,
            acquisition_digest=acquisition.acquisition_digest,
            acquisition_audit_identity=acquisition.acquisition_audit_identity,
            acquisition_audit_digest=acquisition.acquisition_audit_digest,
        )

    @staticmethod
    def _stored_execution(session: Session, row: ToolExecutionTable) -> StoredExecution:
        snapshot = AuthorizedExecutionBindingSnapshot(**row.binding_snapshot)
        acquisition = AcquireWitness(
            row.acquisition_identity,
            row.acquisition_digest,
            row.proposal_id,
            row.logical_execution_id,
            row.request_fingerprint,
            row.owner,
            row.generation,
            row.lease_started_at,
            row.lease_expires_at,
            snapshot,
            row.acquisition_audit_identity,
            row.acquisition_audit_digest,
        )
        observations = session.scalars(
            select(ToolExecutionObservationTable)
            .where(ToolExecutionObservationTable.proposal_id == row.proposal_id)
            .order_by(ToolExecutionObservationTable.sequence)
        ).all()
        return StoredExecution(
            row.lifecycle,
            row.revision,
            row.generation,
            row.owner,
            row.lease_started_at,
            row.lease_expires_at,
            acquisition,
            tuple(
                ExecutionObservation(
                    item.sequence,
                    item.observation_type,
                    item.rejection_code,
                    item.external_resource_reference,
                    item.observed_at,
                )
                for item in observations
            ),
            row.rejection_code,
            row.external_resource_reference,
            row.finalized_at,
        )

    @staticmethod
    def _load_execution(session: Session, proposal_id: str) -> StoredExecution | None:
        row = session.get(ToolExecutionTable, proposal_id)
        return None if row is None else PostgresExecutionStoreMixin._stored_execution(session, row)

    @staticmethod
    def _admission_row(witness: DispatchAdmissionWitness) -> ToolDispatchAdmissionTable:
        return ToolDispatchAdmissionTable(**asdict(witness))

    @staticmethod
    def _stored_admission(row: ToolDispatchAdmissionTable) -> DispatchAdmissionWitness:
        return DispatchAdmissionWitness(
            row.admission_schema_version,
            row.admission_identity,
            row.admission_digest,
            row.purpose,
            row.workspace_id,
            row.proposal_id,
            row.logical_execution_id,
            row.request_fingerprint,
            row.capability_identity,
            row.capability_version,
            row.capability_digest,
            row.binding_identity,
            row.binding_version,
            row.binding_digest,
            row.policy_identity,
            row.policy_version,
            row.policy_digest,
            row.reference_identity,
            row.reference_version,
            row.reference_digest,
            row.reference_claims_digest,
            row.resource_identity_digest,
            row.canonical_target_digest,
            row.canonical_parameter_digest,
            row.complete_intent_digest,
            row.reference_key_epoch,
            row.workspace_dispatch_epoch,
            row.authority_decision_digest,
            row.authority_witness_digest,
            row.owner,
            row.generation,
            row.database_issue_time,
            row.lease_started_at,
            row.lease_deadline,
            row.envelope_signing_key_identity,
            row.envelope_signing_key_version,
            row.routing_snapshot_digest,
            row.canonical_envelope_digest,
            row.admission_audit_identity,
            row.admission_audit_digest,
            row.envelope_token,
        )

    @staticmethod
    def _load_admission(session: Session, proposal_id: str) -> DispatchAdmissionWitness | None:
        row = session.scalar(
            select(ToolDispatchAdmissionTable).where(
                ToolDispatchAdmissionTable.proposal_id == proposal_id
            )
        )
        return None if row is None else PostgresExecutionStoreMixin._stored_admission(row)

    @staticmethod
    def _append_audit(
        session: Session,
        proposal: ToolProposalTable,
        *,
        event_type: str,
        actor_id: str,
        payload: dict[str, object],
    ) -> None:
        sequence = (
            session.scalar(
                select(ToolActionAuditEventTable.sequence)
                .where(ToolActionAuditEventTable.proposal_id == proposal.id)
                .order_by(ToolActionAuditEventTable.sequence.desc())
                .limit(1)
            )
            or 0
        )
        session.add(
            ToolActionAuditEventTable(
                id=str(uuid4()),
                proposal_id=proposal.id,
                workspace_id=proposal.workspace_id,
                sequence=sequence + 1,
                event_type=event_type,
                actor_id=actor_id,
                actor_kind="system",
                payload=thaw_canonical_value(freeze_canonical_value(payload)),
            )
        )
