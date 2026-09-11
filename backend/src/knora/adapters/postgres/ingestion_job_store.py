"""PostgreSQL adapter for durable Ingestion Job submission."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from knora.adapters.postgres.ingestion_jobs.coordination import (
    PostgresIngestionJobCoordinationStore,
)
from knora.adapters.postgres.ingestion_jobs.lifecycle import PostgresObjectLifecycleStore
from knora.adapters.postgres.ingestion_jobs.submission import PostgresPdfSubmissionStore
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    CanonicalFailureV1,
    ClaimedAttempt,
    ClaimOperationId,
    ClaimResult,
    CoordinationInvariantError,
    ExpiredAttemptObservation,
    FailTerminal,
    FencingToken,
    FinalizationResult,
    HeartbeatOperationId,
    HeartbeatResult,
    RecoveryResult,
    RetryExhausted,
    RetryScheduleResult,
    ScheduleRetry,
    TransitionOperationId,
    WorkSuperseded,
)
from knora.ingestion.jobs import (
    JobStatusProjection,
    PdfSubmissionResult,
    PdfSubmissionStore,
    PreparedPdfSubmission,
    PreparedReprocess,
    ReprocessAuditProjection,
    ReprocessContext,
    ReprocessResult,
)
from knora.ingestion.object_lifecycle import (
    LifecycleClaim,
    LifecycleCompletion,
    LifecycleWorkState,
    ObjectLifecycleWorkItem,
    OriginalSourceDeleteCapability,
)
from knora.ingestion.object_store import ObjectMetadata


class PostgresIngestionJobStore(PdfSubmissionStore):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
        self._lifecycle_store = PostgresObjectLifecycleStore(
            session_factory=session_factory,
            database_now=self._database_now,
        )
        self._submission_store = PostgresPdfSubmissionStore(
            session_factory=session_factory,
            database_now=self._database_now,
        )
        self._coordination_store = PostgresIngestionJobCoordinationStore(
            session_factory=session_factory,
            database_now=self._database_now,
            lifecycle_store=self._lifecycle_store,
            enqueue_terminal_cleanup=lambda **kwargs: self._enqueue_lifecycle_work(**kwargs),
        )
        self._heartbeat_once = self._coordination_store._heartbeat_once

    def enqueue_object_lifecycle(self, *, item: ObjectLifecycleWorkItem) -> ObjectLifecycleWorkItem:
        return self._lifecycle_store.enqueue_object_lifecycle(item=item)

    def enqueue(self, item: ObjectLifecycleWorkItem) -> ObjectLifecycleWorkItem:
        return self.enqueue_object_lifecycle(item=item)

    def claim_object_lifecycle(
        self,
        *,
        worker_id: str,
        lease_duration: timedelta = timedelta(minutes=2),
        operation_id: str | None = None,
        work_id: str | None = None,
    ) -> ObjectLifecycleWorkItem | None:
        return self._lifecycle_store.claim_object_lifecycle(
            worker_id=worker_id,
            lease_duration=lease_duration,
            operation_id=operation_id,
            work_id=work_id,
        )

    def claim(
        self, *, worker_id: str, operation_id: str | None = None, work_id: str | None = None
    ) -> ObjectLifecycleWorkItem | None:
        return self.claim_object_lifecycle(
            worker_id=worker_id, operation_id=operation_id, work_id=work_id
        )

    def prepare_delete(
        self, *, claim: LifecycleClaim, operation_id: str | None = None
    ) -> str:
        return self._lifecycle_store.prepare_delete(claim=claim, operation_id=operation_id)

    def revalidate_delete(self, *, claim: LifecycleClaim, delete_generation: str) -> None:
        return self._lifecycle_store.revalidate_delete(
            claim=claim, delete_generation=delete_generation
        )

    def complete(
        self,
        *,
        claim: LifecycleClaim,
        delete_generation: str,
        operation_id: str | None = None,
    ) -> LifecycleCompletion:
        return self._lifecycle_store.complete(
            claim=claim,
            delete_generation=delete_generation,
            operation_id=operation_id,
        )

    def suppress(
        self, *, claim: LifecycleClaim, operation_id: str | None = None
    ) -> LifecycleCompletion:
        return self._lifecycle_store.suppress(claim=claim, operation_id=operation_id)

    def fail(
        self,
        *,
        claim: LifecycleClaim,
        retry_delay: timedelta | None,
        operation_id: str | None = None,
        retry_policy_version: str | None = None,
        retry_window_upper_bound_microseconds: int | None = None,
    ) -> LifecycleWorkState:
        return self._lifecycle_store.fail(
            claim=claim,
            retry_delay=retry_delay,
            operation_id=operation_id,
            retry_policy_version=retry_policy_version,
            retry_window_upper_bound_microseconds=retry_window_upper_bound_microseconds,
        )

    def complete_orphan_reconciliation(
        self, *, work_id: str, disposition: str
    ) -> bool:
        return self._lifecycle_store.complete_orphan_reconciliation(
            work_id=work_id, disposition=disposition
        )

    def prepare_original_source_hard_delete(
        self,
        *,
        workspace_id: str,
        object_key: str,
        operation_id: str | None = None,
    ) -> OriginalSourceDeleteCapability:
        return self._lifecycle_store.prepare_original_source_hard_delete(
            workspace_id=workspace_id,
            object_key=object_key,
            operation_id=operation_id,
        )

    def complete_original_source_hard_delete(
        self,
        *,
        capability: OriginalSourceDeleteCapability,
        operation_id: str | None = None,
    ) -> bool:
        return self._lifecycle_store.complete_original_source_hard_delete(
            capability=capability,
            operation_id=operation_id,
        )

    def revalidate_original_source_hard_delete(
        self, *, capability: OriginalSourceDeleteCapability
    ) -> None:
        return self._lifecycle_store.revalidate_original_source_hard_delete(capability=capability)

    def authorize_workspace(self, *, workspace_id: str) -> None:
        return self._submission_store.authorize_workspace(workspace_id=workspace_id)

    def is_object_referenced(self, *, source_object: ObjectMetadata) -> bool:
        return self._submission_store.is_object_referenced(source_object=source_object)

    def get_job_status(
        self, *, workspace_id: str, ingestion_job_id: str
    ) -> JobStatusProjection | None:
        return self._submission_store.get_job_status(
            workspace_id=workspace_id,
            ingestion_job_id=ingestion_job_id,
        )

    def _enqueue_lifecycle_work(self, *, session, job, database_now) -> None:
        self._lifecycle_store.enqueue_terminal_cleanup_in_transaction(
            session=session,
            job=job,
            database_now=database_now,
        )

    def pdf_profile_for_work(self, work):
        return self._coordination_store.pdf_profile_for_work(work)

    def read_reprocess_context(
        self,
        *,
        workspace_id: str,
        document_version_id: str,
        config_mode: str,
        config_source_job_id: str | None,
    ) -> ReprocessContext | None:
        return self._submission_store.read_reprocess_context(
            workspace_id=workspace_id,
            document_version_id=document_version_id,
            config_mode=config_mode,
            config_source_job_id=config_source_job_id,
        )

    def read_reprocess_replay(
        self, *, workspace_id: str, idempotency_key: str, request_fingerprint: str
    ) -> ReprocessResult | None:
        return self._submission_store.read_reprocess_replay(
            workspace_id=workspace_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )

    def commit_reprocess(self, prepared: PreparedReprocess) -> ReprocessResult:
        return self._submission_store.commit_reprocess(prepared)

    def read_reprocess_audit(
        self, *, workspace_id: str, audit_event_id: str
    ) -> ReprocessAuditProjection | None:
        return self._submission_store.read_reprocess_audit(
            workspace_id=workspace_id,
            audit_event_id=audit_event_id,
        )

    def observe_expired_attempt(self) -> ExpiredAttemptObservation | None:
        return self._coordination_store.observe_expired_attempt()

    def apply_expired_recovery(
        self,
        *,
        operation_id: TransitionOperationId,
        observation: ExpiredAttemptObservation,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry | RetryExhausted,
    ) -> RecoveryResult:
        return self._coordination_store.apply_expired_recovery(
            operation_id=operation_id,
            observation=observation,
            failure=failure,
            decision=decision,
        )

    def claim_next_attempt(
        self,
        *,
        operation_id: ClaimOperationId,
        worker_id: str,
        timing: AttemptTimingV1,
    ) -> ClaimResult:
        return self._coordination_store.claim_next_attempt(
            operation_id=operation_id,
            worker_id=worker_id,
            timing=timing,
        )

    def heartbeat(
        self,
        *,
        operation_id: HeartbeatOperationId,
        token: FencingToken,
        lease_duration: timedelta,
    ) -> HeartbeatResult:
        self._coordination_store._heartbeat_once = self._heartbeat_once
        return self._coordination_store.heartbeat(
            operation_id=operation_id,
            token=token,
            lease_duration=lease_duration,
        )

    def finalize_success[SuccessT](
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        success: SuccessT,
    ) -> FinalizationResult:
        return self._coordination_store.finalize_success(
            operation_id=operation_id,
            claim=claim,
            success=success,
        )

    def finalize_terminal_failure(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: RetryExhausted | FailTerminal | None = None,
    ) -> FinalizationResult:
        return self._coordination_store.finalize_terminal_failure(
            operation_id=operation_id,
            claim=claim,
            failure=failure,
            decision=decision,
        )

    def finalize_superseded(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        outcome: WorkSuperseded,
    ) -> FinalizationResult:
        return self._coordination_store.finalize_superseded(
            operation_id=operation_id,
            claim=claim,
            outcome=outcome,
        )

    def schedule_retry(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry,
    ) -> RetryScheduleResult:
        return self._coordination_store.schedule_retry(
            operation_id=operation_id,
            claim=claim,
            failure=failure,
            decision=decision,
        )

    @staticmethod
    def _database_now(session: Session) -> datetime:
        database_now = session.scalar(select(func.clock_timestamp()))
        if not isinstance(database_now, datetime):
            raise CoordinationInvariantError(
                "PostgreSQL did not return an authoritative timestamp"
            )
        return database_now

    def commit_pdf_submission(
        self,
        prepared: PreparedPdfSubmission,
    ) -> PdfSubmissionResult:
        return self._submission_store.commit_pdf_submission(prepared)
