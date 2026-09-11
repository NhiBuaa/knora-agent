"""Private PostgreSQL persistence for Object Lifecycle work."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import Session, sessionmaker

from knora.adapters.postgres.tables import (
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingSetTable,
    IngestionJobTable,
    ObjectLifecycleAttemptTable,
    ObjectLifecycleWorkTable,
    OriginalSourceObjectTable,
    QuestionTraceTable,
)
from knora.ingestion.job_processing import CoordinationInvariantError
from knora.ingestion.object_lifecycle import (
    LifecycleClaim,
    LifecycleCompletion,
    LifecycleRetentionPending,
    LifecycleWorkState,
    ObjectLifecycleWorkItem,
    OriginalSourceDeleteCapability,
    validate_lifecycle_retry_delay,
    validate_object_lifecycle_work_item,
)


def _duration_microseconds(value: timedelta) -> int:
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds


class PostgresObjectLifecycleStore:
    def __init__(
        self,
        session_factory: sessionmaker,
        database_now: Callable[[Session], datetime],
    ) -> None:
        self._session_factory = session_factory
        self._database_now = database_now

    def enqueue_object_lifecycle(self, *, item: ObjectLifecycleWorkItem) -> ObjectLifecycleWorkItem:
        validate_object_lifecycle_work_item(item)
        with self._session_factory.begin() as session:
            inserted = session.execute(
                postgres_insert(ObjectLifecycleWorkTable)
                .values(
                    id=item.work_id,
                    workspace_id=item.workspace_id,
                    object_key=item.object_key,
                    artifact_class=item.artifact_class,
                    lifecycle_generation=item.lifecycle_generation or item.work_id,
                    state=LifecycleWorkState.QUEUED.value,
                    max_attempts=4,
                    eligible_at=item.eligible_at,
                    discovery_recorded_at=item.discovery_recorded_at,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        "workspace_id",
                        "object_key",
                        "artifact_class",
                        "lifecycle_generation",
                    ]
                )
                .returning(ObjectLifecycleWorkTable.id)
            )
            if inserted.scalar_one_or_none() is not None:
                session.flush()
                return item
            existing = session.scalar(
                select(ObjectLifecycleWorkTable).where(
                    ObjectLifecycleWorkTable.workspace_id == item.workspace_id,
                    ObjectLifecycleWorkTable.object_key == item.object_key,
                    ObjectLifecycleWorkTable.artifact_class == item.artifact_class,
                    ObjectLifecycleWorkTable.lifecycle_generation
                    == (item.lifecycle_generation or item.work_id),
                )
            )
            if existing is None:
                raise CoordinationInvariantError("lifecycle enqueue disappeared after conflict")
            return ObjectLifecycleWorkItem(
                work_id=existing.id,
                workspace_id=existing.workspace_id,
                object_key=existing.object_key,
                state=LifecycleWorkState(existing.state),
                attempt_count=existing.attempt_count,
                worker_id=existing.worker_id,
                lease_version=existing.lease_version,
                lease_expires_at=existing.lease_expires_at,
                next_attempt_at=existing.next_attempt_at,
                delete_generation=existing.deletion_generation,
                reconciliation_disposition=existing.reconciliation_disposition,
                artifact_class=existing.artifact_class,
                lifecycle_generation=existing.lifecycle_generation,
                eligible_at=existing.eligible_at,
                discovery_recorded_at=existing.discovery_recorded_at,
                created=False,
            )

    def enqueue(self, item: ObjectLifecycleWorkItem) -> ObjectLifecycleWorkItem:
        return self.enqueue_object_lifecycle(item=item)

    def enqueue_terminal_cleanup_in_transaction(
        self,
        *,
        session: Session,
        job: IngestionJobTable,
        database_now: datetime,
    ) -> None:
        """Insert terminal cleanup work into an already-open coordination transaction."""

        source_object = session.scalar(
            select(OriginalSourceObjectTable).where(
                OriginalSourceObjectTable.id == job.source_object_id,
                OriginalSourceObjectTable.workspace_id == job.workspace_id,
                OriginalSourceObjectTable.deleted_at.is_(None),
            )
        )
        if source_object is None:
            raise CoordinationInvariantError("terminal Job has no Workspace-owned source object")
        existing = session.scalar(
            select(ObjectLifecycleWorkTable).where(
                ObjectLifecycleWorkTable.workspace_id == job.workspace_id,
                ObjectLifecycleWorkTable.object_key == source_object.object_key,
                ObjectLifecycleWorkTable.artifact_class == "terminal_cleanup",
                ObjectLifecycleWorkTable.lifecycle_generation == job.id,
            )
        )
        if existing is None:
            session.add(
                ObjectLifecycleWorkTable(
                    id=str(uuid4()),
                    workspace_id=job.workspace_id,
                    object_key=source_object.object_key,
                    artifact_class="terminal_cleanup",
                    lifecycle_generation=job.id,
                    state="queued",
                    attempt_count=0,
                    max_attempts=4,
                    created_at=database_now,
                    updated_at=database_now,
                )
            )

    def claim_object_lifecycle(
        self,
        *,
        worker_id: str,
        lease_duration: timedelta = timedelta(minutes=2),
        operation_id: str | None = None,
        work_id: str | None = None,
    ) -> ObjectLifecycleWorkItem | None:
        """Atomically claim one due lifecycle item and insert its immutable attempt."""
        with self._session_factory.begin() as session:
            now = self._database_now(session)
            if operation_id is not None:
                replay_attempt = session.scalar(
                    select(ObjectLifecycleAttemptTable).where(
                        ObjectLifecycleAttemptTable.claim_operation_id == operation_id
                    )
                )
                if replay_attempt is not None:
                    replay_work = session.scalar(
                        select(ObjectLifecycleWorkTable)
                        .where(
                            ObjectLifecycleWorkTable.id
                            == replay_attempt.object_lifecycle_work_id
                        )
                        .with_for_update()
                    )
                    if (
                        replay_work is None
                        or replay_attempt.worker_id != worker_id
                        or (work_id is not None and replay_work.id != work_id)
                    ):
                        raise PermissionError("lifecycle claim operation belongs to another owner")
                    replay_now = self._database_now(session)
                    if replay_work.state == LifecycleWorkState.PROCESSING.value and (
                        replay_work.worker_id != worker_id
                        or replay_work.lease_expires_at is None
                        or replay_work.lease_expires_at <= replay_now
                    ):
                        raise PermissionError("lifecycle claim is fenced")
                    if replay_work.state not in {
                        LifecycleWorkState.PROCESSING.value,
                        LifecycleWorkState.RETRY_SCHEDULED.value,
                        LifecycleWorkState.SUCCEEDED.value,
                        LifecycleWorkState.FAILED.value,
                    }:
                        raise CoordinationInvariantError("lifecycle claim replay has invalid state")
                    return self._lifecycle_work_item(
                        replay_work, claim_operation_id=replay_attempt.claim_operation_id
                    )
            self._recover_expired_lifecycle(session=session, now=now)
            work = session.scalar(
                select(ObjectLifecycleWorkTable)
                .where(
                    ObjectLifecycleWorkTable.state.in_(
                        (LifecycleWorkState.QUEUED.value, LifecycleWorkState.RETRY_SCHEDULED.value)
                    ),
                    ObjectLifecycleWorkTable.attempt_count < ObjectLifecycleWorkTable.max_attempts,
                    or_(
                        ObjectLifecycleWorkTable.state == LifecycleWorkState.QUEUED.value,
                        ObjectLifecycleWorkTable.next_attempt_at <= now,
                    ),
                    or_(
                        ObjectLifecycleWorkTable.eligible_at.is_(None),
                        ObjectLifecycleWorkTable.eligible_at <= now,
                    ),
                    *(ObjectLifecycleWorkTable.id == work_id,) if work_id is not None else (),
                )
                .order_by(ObjectLifecycleWorkTable.created_at, ObjectLifecycleWorkTable.id)
                .with_for_update(skip_locked=True)
            )
            if work is None:
                return None
            now = self._database_now(session)
            if (
                work.eligible_at is not None
                and work.eligible_at > now
            ):
                return None
            if work.state == LifecycleWorkState.RETRY_SCHEDULED.value and (
                work.next_attempt_at is None or work.next_attempt_at > now
            ):
                return None
            attempt_number = work.attempt_count + 1
            work.state = LifecycleWorkState.PROCESSING.value
            work.attempt_count = attempt_number
            work.worker_id = worker_id
            work.lease_version += 1
            work.lease_expires_at = now + lease_duration
            work.next_attempt_at = None
            claim_operation_id = operation_id or str(uuid4())
            session.add(
                ObjectLifecycleAttemptTable(
                    object_lifecycle_work_id=work.id,
                    attempt_number=attempt_number,
                    worker_id=worker_id,
                    lease_version=work.lease_version,
                    claim_operation_id=claim_operation_id,
                    attempt_started_at=now,
                )
            )
            session.flush()
            return self._lifecycle_work_item(work, claim_operation_id=claim_operation_id)

    @staticmethod
    def _lifecycle_work_item(
        work: ObjectLifecycleWorkTable, *, claim_operation_id: str | None = None
    ) -> ObjectLifecycleWorkItem:
        return ObjectLifecycleWorkItem(
            work_id=work.id,
            workspace_id=work.workspace_id,
            object_key=work.object_key,
            state=LifecycleWorkState(work.state),
            attempt_count=work.attempt_count,
            worker_id=work.worker_id,
            lease_version=work.lease_version,
            lease_expires_at=work.lease_expires_at,
            delete_generation=work.deletion_generation,
            reconciliation_disposition=work.reconciliation_disposition,
            artifact_class=work.artifact_class,
            lifecycle_generation=work.lifecycle_generation,
            eligible_at=work.eligible_at,
            discovery_recorded_at=work.discovery_recorded_at,
            claim_operation_id=claim_operation_id,
        )

    # ObjectLifecycleMaintenance application-port aliases. Keeping the concrete persistence
    # adapter behind these names lets the worker exercise only the approved typed seam.
    def claim(
        self, *, worker_id: str, operation_id: str | None = None, work_id: str | None = None
    ) -> ObjectLifecycleWorkItem | None:
        return self.claim_object_lifecycle(
            worker_id=worker_id, operation_id=operation_id, work_id=work_id
        )

    def prepare_delete(
        self, *, claim: LifecycleClaim, operation_id: str | None = None
    ) -> str:
        return self.prepare_object_lifecycle_delete(claim=claim, operation_id=operation_id)

    def revalidate_delete(self, *, claim: LifecycleClaim, delete_generation: str) -> None:
        with self._session_factory.begin() as session:
            work = session.scalar(
                select(ObjectLifecycleWorkTable)
                .where(ObjectLifecycleWorkTable.id == claim.work_id)
                .with_for_update()
            )
            now = self._database_now(session)
            if work is None or not self._owns_lifecycle_claim(work, claim, now):
                raise PermissionError("lifecycle claim is fenced")
            if work.deletion_generation != delete_generation:
                raise PermissionError("delete generation is fenced")
            attempt = session.scalar(
                select(ObjectLifecycleAttemptTable)
                .where(
                    ObjectLifecycleAttemptTable.object_lifecycle_work_id == work.id,
                    ObjectLifecycleAttemptTable.attempt_number == claim.attempt_number,
                )
                .with_for_update()
            )
            if attempt is None or attempt.deletion_generation != delete_generation:
                raise PermissionError("delete generation is fenced")
            if work.eligible_at is not None and work.eligible_at > now:
                raise LifecycleRetentionPending("lifecycle retention window has not expired")
            if session.scalar(
                select(OriginalSourceObjectTable.id).where(
                    OriginalSourceObjectTable.workspace_id == work.workspace_id,
                    OriginalSourceObjectTable.object_key == work.object_key,
                    OriginalSourceObjectTable.deleted_at.is_(None),
                )
            ) is not None:
                raise PermissionError("retained Original Source Object suppresses deletion")
            self._assert_no_other_lifecycle_retention(
                session=session, work=work, database_now=now
            )

    def complete(
        self,
        *,
        claim: LifecycleClaim,
        delete_generation: str,
        operation_id: str | None = None,
    ) -> LifecycleCompletion:
        state = self.complete_object_lifecycle_delete(
            claim=claim, delete_generation=delete_generation, operation_id=operation_id
        )
        return LifecycleCompletion(state, claim.work_id, claim.attempt_number)

    def suppress(
        self, *, claim: LifecycleClaim, operation_id: str | None = None
    ) -> LifecycleCompletion:
        return self.suppress_object_lifecycle(claim=claim, operation_id=operation_id)

    def fail(
        self,
        *,
        claim: LifecycleClaim,
        retry_delay: timedelta | None,
        operation_id: str | None = None,
        retry_policy_version: str | None = None,
        retry_window_upper_bound_microseconds: int | None = None,
    ) -> LifecycleWorkState:
        return self.fail_object_lifecycle(
            claim=claim,
            retry_delay=retry_delay,
            operation_id=operation_id,
            retry_policy_version=retry_policy_version,
            retry_window_upper_bound_microseconds=retry_window_upper_bound_microseconds,
        )

    def _recover_expired_lifecycle(self, *, session: Session, now: datetime) -> None:
        expired = session.scalars(
            select(ObjectLifecycleWorkTable)
            .where(
                ObjectLifecycleWorkTable.state == LifecycleWorkState.PROCESSING.value,
                ObjectLifecycleWorkTable.lease_expires_at <= now,
            )
            .with_for_update(skip_locked=True)
        ).all()
        for work in expired:
            attempt = session.scalar(
                select(ObjectLifecycleAttemptTable)
                .where(
                    ObjectLifecycleAttemptTable.object_lifecycle_work_id == work.id,
                    ObjectLifecycleAttemptTable.attempt_number == work.attempt_count,
                    ObjectLifecycleAttemptTable.closed_at.is_(None),
                )
                .with_for_update()
            )
            if attempt is None:
                raise CoordinationInvariantError(
                    "expired lifecycle work has no immutable lifecycle attempt"
                )
            attempt.closed_at = now
            attempt.disposition = "lease_expired"
            work.worker_id = None
            work.lease_expires_at = None
            if work.attempt_count >= work.max_attempts:
                work.state = LifecycleWorkState.FAILED.value
                work.terminal_at = now
                work.next_attempt_at = None
            else:
                work.state = LifecycleWorkState.RETRY_SCHEDULED.value
                work.next_attempt_at = now

    def prepare_object_lifecycle_delete(
        self, *, claim: LifecycleClaim, operation_id: str | None = None
    ) -> str:
        """Fence and authorize one destructive lifecycle generation."""
        with self._session_factory.begin() as session:
            work = session.scalar(
                select(ObjectLifecycleWorkTable)
                .where(ObjectLifecycleWorkTable.id == claim.work_id)
                .with_for_update()
            )
            now = self._database_now(session)
            if work is None or not self._owns_lifecycle_claim(work, claim, now):
                raise PermissionError("lifecycle claim is fenced")
            if work.eligible_at is not None and work.eligible_at > now:
                raise LifecycleRetentionPending("lifecycle retention window has not expired")
            if work.artifact_class == "orphan_report":
                raise PermissionError("inconsistent database record is report-only")
            retained = session.scalar(
                select(OriginalSourceObjectTable.id).where(
                    OriginalSourceObjectTable.workspace_id == work.workspace_id,
                    OriginalSourceObjectTable.object_key == work.object_key,
                    OriginalSourceObjectTable.deleted_at.is_(None),
                )
            )
            if retained is not None:
                raise PermissionError("retained Original Source Object suppresses deletion")
            self._assert_no_other_lifecycle_retention(
                session=session, work=work, database_now=now
            )
            attempt = session.scalar(
                select(ObjectLifecycleAttemptTable)
                .where(
                    ObjectLifecycleAttemptTable.object_lifecycle_work_id == work.id,
                    ObjectLifecycleAttemptTable.attempt_number == claim.attempt_number,
                )
                .with_for_update()
            )
            if attempt is None:
                raise CoordinationInvariantError("lifecycle preparation has no immutable attempt")
            if attempt.deletion_generation is not None:
                if attempt.prepare_operation_id not in {None, operation_id}:
                    raise PermissionError("lifecycle preparation operation is already bound")
                return attempt.deletion_generation
            generation = str(uuid4())
            work.deletion_generation = generation
            attempt.prepare_operation_id = operation_id
            attempt.deletion_generation = generation
            session.flush()
            return generation

    def complete_object_lifecycle_delete(
        self,
        *,
        claim: LifecycleClaim,
        delete_generation: str,
        operation_id: str | None = None,
    ) -> LifecycleWorkState:
        with self._session_factory.begin() as session:
            work = session.scalar(
                select(ObjectLifecycleWorkTable)
                .where(ObjectLifecycleWorkTable.id == claim.work_id)
                .with_for_update()
            )
            now = self._database_now(session)
            if work is None:
                raise PermissionError("lifecycle claim is fenced")
            if (
                work.state == LifecycleWorkState.SUCCEEDED.value
                and work.deletion_generation == delete_generation
            ):
                attempt = session.scalar(
                    select(ObjectLifecycleAttemptTable)
                    .where(
                        ObjectLifecycleAttemptTable.object_lifecycle_work_id == work.id,
                        ObjectLifecycleAttemptTable.attempt_number == claim.attempt_number,
                    )
                    .with_for_update()
                )
                if attempt is None:
                    raise CoordinationInvariantError(
                        "lifecycle completion replay has no immutable attempt"
                    )
                if attempt.deletion_generation != delete_generation:
                    raise PermissionError("delete generation is fenced")
                if attempt.completion_operation_id not in {None, operation_id}:
                    raise PermissionError("lifecycle completion operation is already bound")
                return LifecycleWorkState.SUCCEEDED
            if not self._owns_lifecycle_claim(work, claim, now):
                raise PermissionError("lifecycle claim is fenced")
            if work.deletion_generation != delete_generation:
                raise PermissionError("delete generation is fenced")
            if work.artifact_class == "orphan_report":
                raise PermissionError("inconsistent database record is report-only")
            if session.scalar(
                select(OriginalSourceObjectTable.id).where(
                    OriginalSourceObjectTable.workspace_id == work.workspace_id,
                    OriginalSourceObjectTable.object_key == work.object_key,
                    OriginalSourceObjectTable.deleted_at.is_(None),
                )
            ) is not None:
                raise PermissionError("retained Original Source Object suppresses deletion")
            attempt = session.scalar(
                select(ObjectLifecycleAttemptTable)
                .where(
                    ObjectLifecycleAttemptTable.object_lifecycle_work_id == work.id,
                    ObjectLifecycleAttemptTable.attempt_number == claim.attempt_number,
                )
                .with_for_update()
            )
            if attempt is None:
                raise CoordinationInvariantError("lifecycle completion has no immutable attempt")
            if attempt.deletion_generation != delete_generation:
                raise PermissionError("delete generation is fenced")
            if attempt.completion_operation_id is not None:
                if attempt.completion_operation_id != operation_id:
                    raise PermissionError("lifecycle completion operation is already bound")
                return LifecycleWorkState.SUCCEEDED
            work.state = LifecycleWorkState.SUCCEEDED.value
            work.worker_id = None
            work.lease_expires_at = None
            work.terminal_at = now
            if work.artifact_class == "orphan":
                work.reconciliation_disposition = "deleted"
            attempt.closed_at = now
            attempt.disposition = LifecycleWorkState.SUCCEEDED.value
            attempt.completion_operation_id = operation_id
            session.flush()
            return LifecycleWorkState.SUCCEEDED

    def suppress_object_lifecycle(
        self, *, claim: LifecycleClaim, operation_id: str | None = None
    ) -> LifecycleCompletion:
        with self._session_factory.begin() as session:
            work = session.scalar(
                select(ObjectLifecycleWorkTable)
                .where(ObjectLifecycleWorkTable.id == claim.work_id)
                .with_for_update()
            )
            now = self._database_now(session)
            if work is None:
                raise PermissionError("lifecycle claim is fenced")
            if work.state == LifecycleWorkState.SUCCEEDED.value:
                attempt = session.scalar(
                    select(ObjectLifecycleAttemptTable)
                    .where(
                        ObjectLifecycleAttemptTable.object_lifecycle_work_id == work.id,
                        ObjectLifecycleAttemptTable.attempt_number == claim.attempt_number,
                    )
                    .with_for_update()
                )
                if attempt is None:
                    raise CoordinationInvariantError(
                        "lifecycle suppression replay has no immutable attempt"
                    )
                if attempt.closed_at is None or attempt.disposition != "suppressed":
                    raise PermissionError("lifecycle suppression is fenced")
                if attempt.completion_operation_id not in {None, operation_id}:
                    raise PermissionError("lifecycle suppression operation is already bound")
                return LifecycleCompletion(
                    state=LifecycleWorkState.SUCCEEDED,
                    work_id=work.id,
                    attempt_number=claim.attempt_number,
                )
            if not self._owns_lifecycle_claim(work, claim, now):
                raise PermissionError("lifecycle claim is fenced")
            attempt = session.scalar(
                select(ObjectLifecycleAttemptTable)
                .where(
                    ObjectLifecycleAttemptTable.object_lifecycle_work_id == work.id,
                    ObjectLifecycleAttemptTable.attempt_number == claim.attempt_number,
                )
                .with_for_update()
            )
            if attempt is None:
                raise CoordinationInvariantError("lifecycle suppression has no immutable attempt")
            if attempt.completion_operation_id is not None:
                if attempt.completion_operation_id != operation_id:
                    raise PermissionError("lifecycle suppression operation is already bound")
                return LifecycleCompletion(
                    state=LifecycleWorkState.SUCCEEDED,
                    work_id=work.id,
                    attempt_number=claim.attempt_number,
                )
            work.state = LifecycleWorkState.SUCCEEDED.value
            work.worker_id = None
            work.lease_expires_at = None
            work.terminal_at = now
            # Suppression is a terminal no-effect outcome. Clear any generation prepared by a
            # stale owner so that its pre-issued capability cannot replay completion after the
            # valid owner has fenced it.
            work.deletion_generation = None
            if work.artifact_class == "orphan":
                work.reconciliation_disposition = "delete_suppressed"
            elif work.artifact_class == "orphan_report":

                work.reconciliation_disposition = "reported"
            attempt.closed_at = now
            attempt.disposition = "suppressed"
            attempt.completion_operation_id = operation_id
            session.flush()
            return LifecycleCompletion(
                state=LifecycleWorkState.SUCCEEDED,
                work_id=work.id,
                attempt_number=claim.attempt_number,
            )

    def fail_object_lifecycle(
        self,
        *,
        claim: LifecycleClaim,
        retry_delay: timedelta | None,
        operation_id: str | None = None,
        retry_policy_version: str | None = None,
        retry_window_upper_bound_microseconds: int | None = None,
    ) -> LifecycleWorkState:
        validate_lifecycle_retry_delay(retry_delay)
        with self._session_factory.begin() as session:
            work = session.scalar(
                select(ObjectLifecycleWorkTable)
                .where(ObjectLifecycleWorkTable.id == claim.work_id)
                .with_for_update()
            )
            now = self._database_now(session)
            if work is None:
                raise PermissionError("lifecycle claim is fenced")
            attempt = session.scalar(
                select(ObjectLifecycleAttemptTable)
                .where(
                    ObjectLifecycleAttemptTable.object_lifecycle_work_id == work.id,
                    ObjectLifecycleAttemptTable.attempt_number == claim.attempt_number,
                )
                .with_for_update()
            )
            if attempt is None:
                raise ValueError("lifecycle attempt is already closed")
            if attempt.closed_at is not None:
                if attempt.disposition != LifecycleWorkState.FAILED.value:
                    raise PermissionError("lifecycle failure is fenced")
                if (
                    attempt.failure_operation_id is not None
                    and attempt.failure_operation_id != operation_id
                ):
                    raise PermissionError("lifecycle failure operation is already bound")
                requested_retry_delay = (
                    None
                    if retry_delay is None or claim.attempt_number >= 4
                    else _duration_microseconds(retry_delay)
                )
                if (
                    attempt.retry_delay_microseconds != requested_retry_delay
                    or attempt.retry_policy_version != retry_policy_version
                    or attempt.retry_window_upper_bound_microseconds
                    != retry_window_upper_bound_microseconds
                ):
                    raise PermissionError(
                        "lifecycle failure operation request does not match replay"
                    )
                return LifecycleWorkState(work.state)
            if not self._owns_lifecycle_claim(work, claim, now):
                raise PermissionError("lifecycle claim is fenced")
            attempt.closed_at = now
            # Every failed external cleanup attempt is a failed attempt for the monotonic
            # cleanup_failure_total counter, even when the work item remains retry_scheduled.
            attempt.disposition = LifecycleWorkState.FAILED.value
            attempt.failure_operation_id = operation_id
            attempt.retry_policy_version = retry_policy_version
            attempt.retry_window_upper_bound_microseconds = (
                retry_window_upper_bound_microseconds
            )
            if retry_delay is not None and claim.attempt_number < 4:
                work.state = LifecycleWorkState.RETRY_SCHEDULED.value
                work.next_attempt_at = now + retry_delay
                attempt.retry_delay_microseconds = _duration_microseconds(retry_delay)
                attempt.retry_next_attempt_at = work.next_attempt_at
            else:
                work.state = LifecycleWorkState.FAILED.value
                work.terminal_at = now
            work.worker_id = None
            work.lease_expires_at = None
            session.flush()
            return LifecycleWorkState(work.state)

    def complete_orphan_reconciliation(
        self, *, work_id: str, disposition: str
    ) -> bool:
        """Record one completed orphan or inconsistent-record correction idempotently."""
        if disposition not in {"repaired", "deleted"}:
            raise ValueError("unsupported orphan reconciliation disposition")
        with self._session_factory.begin() as session:
            work = session.scalar(
                select(ObjectLifecycleWorkTable)
                .where(
                    ObjectLifecycleWorkTable.id == work_id,
                    ObjectLifecycleWorkTable.artifact_class.in_(("orphan", "orphan_report")),
                )
                .with_for_update()
            )
            if work is None:
                raise ValueError("orphan lifecycle work does not exist")
            if work.artifact_class == "orphan_report" and disposition != "repaired":
                raise ValueError(
                    "inconsistent database record cannot be deleted by orphan cleanup"
                )
            if work.reconciliation_disposition is not None:
                if work.reconciliation_disposition == disposition:
                    return False
                if not (
                    work.artifact_class == "orphan_report"
                    and work.reconciliation_disposition == "reported"
                    and disposition == "repaired"
                ):
                    raise ValueError("orphan corrective disposition is already bound")
            if work.state != LifecycleWorkState.SUCCEEDED.value:
                raise ValueError("orphan corrective disposition is not complete")
            work.reconciliation_disposition = disposition
            session.flush()
            return True

    def prepare_original_source_hard_delete(
        self,
        *,
        workspace_id: str,
        object_key: str,
        operation_id: str | None = None,
    ) -> OriginalSourceDeleteCapability:
        """Authorize one approved hard-delete effect after an authoritative read.

        The capability is intentionally consumed by the application worker around the external
        ObjectStore delete.  The final completion call repeats this check, so a pointer, trace or
        citation attached after preparation fences the stale capability before bookkeeping.
        """

        del operation_id
        with self._session_factory.begin() as session:
            source = self._lock_original_source_for_hard_delete(
                session=session,
                workspace_id=workspace_id,
                object_key=object_key,
            )
            return OriginalSourceDeleteCapability(
                workspace_id=workspace_id,
                object_key=object_key,
                document_version_id=source.document_version_id,
                generation=str(uuid4()),
                already_deleted=source.deleted_at is not None,
            )

    def complete_original_source_hard_delete(
        self,
        *,
        capability: OriginalSourceDeleteCapability,
        operation_id: str | None = None,
    ) -> bool:
        """Commit the approved hard-delete bookkeeping idempotently after ObjectStore delete."""

        del operation_id
        with self._session_factory.begin() as session:
            source = session.scalar(
                select(OriginalSourceObjectTable)
                .where(
                    OriginalSourceObjectTable.workspace_id == capability.workspace_id,
                    OriginalSourceObjectTable.object_key == capability.object_key,
                )
                .with_for_update()
            )
            if source is None:
                raise PermissionError("Original Source Object belongs to another Workspace")
            if source.document_version_id != capability.document_version_id:
                raise PermissionError("Original Source Object delete capability is fenced")
            if source.deleted_at is not None:
                return True
            self._assert_original_source_hard_deleteable(session=session, source=source)
            source.deleted_at = self._database_now(session)
            session.flush()
            return True

    def revalidate_original_source_hard_delete(
        self, *, capability: OriginalSourceDeleteCapability
    ) -> None:
        """Repeat the authoritative retention read immediately before ObjectStore delete."""

        with self._session_factory.begin() as session:
            source = self._lock_original_source_for_hard_delete(
                session=session,
                workspace_id=capability.workspace_id,
                object_key=capability.object_key,
            )
            if source.document_version_id != capability.document_version_id:
                raise PermissionError("Original Source Object delete capability is fenced")
            if source.deleted_at is not None:
                raise PermissionError("Original Source Object is already deleted")

    def _lock_original_source_for_hard_delete(
        self, *, session: Session, workspace_id: str, object_key: str
    ) -> OriginalSourceObjectTable:
        source = session.scalar(
            select(OriginalSourceObjectTable)
            .where(
                OriginalSourceObjectTable.workspace_id == workspace_id,
                OriginalSourceObjectTable.object_key == object_key,
            )
            .with_for_update()
        )
        if source is None:
            raise PermissionError("Original Source Object is not owned by this Workspace")
        if source.deleted_at is not None:
            return source
        self._assert_original_source_hard_deleteable(session=session, source=source)
        return source

    @classmethod
    def _assert_original_source_hard_deleteable(
        cls, *, session: Session, source: OriginalSourceObjectTable
    ) -> None:
        document_version = session.scalar(
            select(DocumentVersionTable).where(
                DocumentVersionTable.id == source.document_version_id
            )
        )
        document = (
            session.scalar(
                select(DocumentTable)
                .where(
                    DocumentTable.id == document_version.document_id,
                    DocumentTable.workspace_id == source.workspace_id,
                )
                .with_for_update()
            )
            if document_version is not None
            else None
        )
        if document_version is None or document is None:
            raise CoordinationInvariantError("Original Source Object has invalid ownership")
        if document.current_document_version_id == document_version.id:
            raise PermissionError("current Document Version ownership suppresses hard deletion")

        active_embedding_set_id = session.scalar(
            select(EmbeddingSetTable.id)
            .join(ChunkSetTable, ChunkSetTable.id == EmbeddingSetTable.chunk_set_id)
            .where(
                EmbeddingSetTable.id == document.active_embedding_set_id,
                ChunkSetTable.document_version_id == document_version.id,
            )
        )
        if active_embedding_set_id is not None:
            raise PermissionError("active Embedding Set ownership suppresses hard deletion")

        chunk_set_ids = set(
            session.scalars(
                select(ChunkSetTable.id).where(
                    ChunkSetTable.document_version_id == document_version.id
                )
            ).all()
        )
        chunk_ids = set()
        if chunk_set_ids:
            chunk_ids = set(
                session.scalars(
                    select(ChunkTable.id).where(ChunkTable.chunk_set_id.in_(chunk_set_ids))
                ).all()
            )
        embedding_set_ids = set(
            session.scalars(
                select(EmbeddingSetTable.id)
                .join(ChunkSetTable, ChunkSetTable.id == EmbeddingSetTable.chunk_set_id)
                .where(ChunkSetTable.document_version_id == document_version.id)
            ).all()
        )
        if cls._workspace_trace_references_source(
            session=session,
            workspace_id=source.workspace_id,
            source_identifiers={
                source.id,
                source.object_key,
                document_version.id,
                *chunk_ids,
                *chunk_set_ids,
                *embedding_set_ids,
            },
            chunk_ids=chunk_ids,
            chunk_set_ids=chunk_set_ids,
            embedding_set_ids=embedding_set_ids,
        ):
            raise PermissionError("citation/trace/evaluation retention suppresses hard deletion")

    @staticmethod
    def _workspace_trace_references_source(
        *,
        session: Session,
        workspace_id: str,
        source_identifiers: set[str],
        chunk_ids: set[str],
        chunk_set_ids: set[str],
        embedding_set_ids: set[str],
    ) -> bool:
        for trace in session.scalars(
            select(QuestionTraceTable).where(QuestionTraceTable.workspace_id == workspace_id)
        ).all():
            if chunk_set_ids.intersection(str(value) for value in (trace.chunk_set_ids or ())):
                return True
            if embedding_set_ids.intersection(
                str(value) for value in (trace.embedding_set_ids or ())
            ):
                return True
            referenced_chunks = {
                str(value) for value in (trace.retrieved_chunk_ids or ())
            }
            referenced_chunks.update(
                str(value)
                for value in (trace.alias_mapping or {}).values()
                if isinstance(value, str)
            )
            referenced_chunks.update(
                str(candidate.get("chunk_id"))
                for candidate in (trace.candidate_decisions or ())
                if isinstance(candidate, dict) and candidate.get("chunk_id") is not None
            )
            if chunk_ids.intersection(referenced_chunks):
                return True
            if PostgresObjectLifecycleStore._json_contains_identifier(
                trace.provider_metadata, source_identifiers
            ):
                return True
        return False

    @staticmethod
    def _json_contains_identifier(value: object, identifiers: set[str]) -> bool:
        if isinstance(value, str):
            return value in identifiers
        if isinstance(value, dict):
            return any(
                PostgresObjectLifecycleStore._json_contains_identifier(item, identifiers)
                for item in value.values()
            )
        if isinstance(value, (list, tuple, set)):
            return any(
                PostgresObjectLifecycleStore._json_contains_identifier(item, identifiers)
                for item in value
            )
        return False

    @staticmethod
    def _assert_no_other_lifecycle_retention(
        *, session: Session, work: ObjectLifecycleWorkTable, database_now: datetime
    ) -> None:
        """Keep a stale cleanup candidate behind another diagnostic retention window."""

        blocking_diagnostic = session.scalar(
            select(ObjectLifecycleWorkTable.id).where(
                ObjectLifecycleWorkTable.workspace_id == work.workspace_id,
                ObjectLifecycleWorkTable.object_key == work.object_key,
                ObjectLifecycleWorkTable.id != work.id,
                ObjectLifecycleWorkTable.artifact_class == "failed_upload_diagnostic",
                or_(
                    ObjectLifecycleWorkTable.eligible_at.is_(None),
                    ObjectLifecycleWorkTable.eligible_at > database_now,
                ),
            )
        )
        if blocking_diagnostic is not None:
            raise LifecycleRetentionPending(
                "another failed-upload diagnostic retention window has not expired"
            )

    @staticmethod
    def _owns_lifecycle_claim(
        work: ObjectLifecycleWorkTable, claim: LifecycleClaim, now: datetime
    ) -> bool:
        return (
            work.state == LifecycleWorkState.PROCESSING.value
            and work.worker_id == claim.worker_id
            and work.attempt_count == claim.attempt_number
            and work.lease_version == claim.lease_version
            and work.lease_expires_at is not None
            and work.lease_expires_at > now
        )
