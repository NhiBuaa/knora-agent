from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.object_reconciliation import PostgresObjectReferenceResolver
from knora.adapters.postgres.tables import (
    DocumentTable,
    DocumentVersionTable,
    ObjectLifecycleAttemptTable,
    ObjectLifecycleWorkTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.domain.errors import KnoraError
from knora.ingestion.job_processing import CoordinationInvariantError
from knora.ingestion.object_lifecycle import (
    LifecycleClaim,
    LifecycleWorkState,
    ObjectLifecycleRetryPolicyV1,
    ObjectLifecycleWorker,
    ObjectLifecycleWorkItem,
)


@pytest.fixture(autouse=True)
def clean_lifecycle_state():
    with SessionFactory.begin() as session:
        session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
    yield
    with SessionFactory.begin() as session:
        session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))


def test_postgres_lifecycle_claim_handoff_and_generation_fencing() -> None:
    workspace_id = f"lifecycle-{uuid4()}"
    work_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle test"))
    store = PostgresIngestionJobStore(SessionFactory)
    try:
        queued = store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=work_id,
                workspace_id=workspace_id,
                object_key=uuid4().hex,
                state=LifecycleWorkState.QUEUED,
            )
        )
        assert queued.created
        first = store.claim(worker_id="worker-a", work_id=work_id)
        assert first is not None
        first_claim = LifecycleClaim(
            work_id=work_id,
            worker_id="worker-a",
            attempt_number=1,
            lease_version=first.lease_version,
        )
        generation = store.prepare_delete(claim=first_claim)

        with SessionFactory.begin() as session:
            session.execute(
                update(ObjectLifecycleWorkTable)
                .where(ObjectLifecycleWorkTable.id == work_id)
                .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )

        second = store.claim(worker_id="worker-b", work_id=work_id)
        assert second is not None
        assert second.attempt_count == 2
        second_claim = LifecycleClaim(
            work_id=work_id,
            worker_id="worker-b",
            attempt_number=2,
            lease_version=second.lease_version,
        )
        with pytest.raises(PermissionError, match="fenced"):
            store.revalidate_delete(claim=first_claim, delete_generation=generation)
        with pytest.raises(PermissionError, match="delete generation"):
            store.complete(claim=second_claim, delete_generation=generation)

        generation_b = store.prepare_delete(claim=second_claim)
        store.revalidate_delete(claim=second_claim, delete_generation=generation_b)
        assert store.complete(claim=second_claim, delete_generation=generation_b).state == (
            LifecycleWorkState.SUCCEEDED
        )

        with SessionFactory() as session:
            attempts = session.scalars(
                select(ObjectLifecycleAttemptTable)
                .where(ObjectLifecycleAttemptTable.object_lifecycle_work_id == work_id)
                .order_by(ObjectLifecycleAttemptTable.attempt_number)
            ).all()
            assert len(attempts) == 2
            assert attempts[0].disposition == "lease_expired"
            assert attempts[1].disposition == "succeeded"
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(
                delete(ObjectLifecycleWorkTable).where(ObjectLifecycleWorkTable.id == work_id)
            )
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_worker_returns_fenced_for_stale_delivery_after_lease_handoff() -> None:
    workspace_id = f"lifecycle-worker-stale-delivery-{uuid4()}"
    work_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="stale lifecycle delivery"))
    store = PostgresIngestionJobStore(SessionFactory)
    object_store = CountingDelete()
    try:
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=work_id,
                workspace_id=workspace_id,
                object_key=uuid4().hex,
                state=LifecycleWorkState.QUEUED,
            )
        )
        first = store.claim(worker_id="worker-a", operation_id="delivery-a", work_id=work_id)
        assert first is not None
        with SessionFactory.begin() as session:
            session.execute(
                update(ObjectLifecycleWorkTable)
                .where(ObjectLifecycleWorkTable.id == work_id)
                .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        second = store.claim(worker_id="worker-b", operation_id="delivery-b", work_id=work_id)
        assert second is not None

        result = ObjectLifecycleWorker(
            maintenance=store,
            object_store=object_store,
            retry_policy=ObjectLifecycleRetryPolicyV1(random_source=OneSample(0)),
        ).run_once(
            worker_id="worker-a",
            operation_id="delivery-a",
            work_id=work_id,
        )

        assert result.outcome == "fenced"
        assert object_store.count == 0
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_suppression_fences_stale_prepared_generation_after_handoff() -> None:
    workspace_id = f"lifecycle-suppression-fence-{uuid4()}"
    work_id = str(uuid4())
    object_key = uuid4().hex
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle suppression fence"))
    store = PostgresIngestionJobStore(SessionFactory)
    try:
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=work_id,
                workspace_id=workspace_id,
                object_key=object_key,
                state=LifecycleWorkState.QUEUED,
            )
        )
        first = store.claim(worker_id="worker-a", work_id=work_id)
        assert first is not None
        first_claim = LifecycleClaim(
            work_id=work_id,
            worker_id="worker-a",
            attempt_number=1,
            lease_version=first.lease_version,
        )
        generation_a = store.prepare_delete(claim=first_claim)
        with SessionFactory.begin() as session:
            session.execute(
                update(ObjectLifecycleWorkTable)
                .where(ObjectLifecycleWorkTable.id == work_id)
                .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            document_id = str(uuid4())
            version_id = str(uuid4())
            session.add(
                DocumentTable(
                    id=document_id,
                    workspace_id=workspace_id,
                    source_key=f"suppression-{uuid4()}",
                    source_name="suppression.pdf",
                    revision=0,
                )
            )
            session.flush()
            session.add(
                DocumentVersionTable(
                    id=version_id,
                    document_id=document_id,
                    raw_sha256="a" * 64,
                    media_type="application/pdf",
                    version_number=1,
                )
            )
            session.flush()
            session.add(
                OriginalSourceObjectTable(
                    id=str(uuid4()),
                    workspace_id=workspace_id,
                    document_version_id=version_id,
                    object_key=object_key,
                    raw_sha256="a" * 64,
                    byte_size=1,
                    media_type="application/pdf",
                )
            )
            session.flush()
            session.execute(
                update(DocumentTable)
                .where(DocumentTable.id == document_id)
                .values(current_document_version_id=version_id)
            )

        result = ObjectLifecycleWorker(
            maintenance=store,
            object_store=CountingDelete(),
            retry_policy=ObjectLifecycleRetryPolicyV1(random_source=OneSample(0)),
        ).run_once(worker_id="worker-b", work_id=work_id)

        assert result.outcome == "suppressed"
        with pytest.raises(PermissionError, match="fenced|suppression"):
            store.suppress(claim=first_claim, operation_id="stale-suppress")
        with pytest.raises(PermissionError, match="fenced|failure"):
            store.fail(
                claim=first_claim,
                retry_delay=timedelta(microseconds=1),
                operation_id="stale-failure",
            )
        with pytest.raises(PermissionError, match="fenced|generation"):
            store.complete(claim=first_claim, delete_generation=generation_a)
        with SessionFactory() as session:
            work = session.get(ObjectLifecycleWorkTable, work_id)
            assert work is not None
            assert work.state == LifecycleWorkState.SUCCEEDED.value
            assert work.deletion_generation is None
            assert work.reconciliation_disposition == "delete_suppressed"
    finally:
        with SessionFactory.begin() as session:
            version_ids = select(DocumentVersionTable.id).where(
                DocumentVersionTable.document_id.in_(
                    select(DocumentTable.id).where(DocumentTable.workspace_id == workspace_id)
                )
            )
            session.execute(
                delete(OriginalSourceObjectTable).where(
                    OriginalSourceObjectTable.workspace_id == workspace_id
                )
            )
            session.execute(
                update(DocumentTable)
                .where(DocumentTable.workspace_id == workspace_id)
                .values(current_document_version_id=None)
            )
            session.execute(delete(DocumentVersionTable).where(DocumentVersionTable.id.in_(version_ids)))
            session.execute(delete(DocumentTable).where(DocumentTable.workspace_id == workspace_id))
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(
                delete(ObjectLifecycleWorkTable).where(ObjectLifecycleWorkTable.id == work_id)
            )
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_lifecycle_expiry_fails_closed_when_attempt_history_is_missing() -> None:
    workspace_id = f"lifecycle-missing-attempt-{uuid4()}"
    work_id = str(uuid4())
    expired_at = datetime.now(UTC) - timedelta(seconds=1)
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle missing attempt"))
        session.flush()
        session.add(
            ObjectLifecycleWorkTable(
                id=work_id,
                workspace_id=workspace_id,
                object_key=uuid4().hex,
                artifact_class="orphan",
                lifecycle_generation=work_id,
                state=LifecycleWorkState.PROCESSING.value,
                attempt_count=1,
                max_attempts=4,
                worker_id="worker-a",
                lease_version=1,
                lease_expires_at=expired_at,
            )
        )

    try:
        with pytest.raises(CoordinationInvariantError, match="immutable lifecycle attempt"):
            PostgresIngestionJobStore(SessionFactory).claim(worker_id="worker-b")
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_lifecycle_claim_respects_durable_eligibility_timestamp() -> None:
    workspace_id = f"lifecycle-eligibility-{uuid4()}"
    work_id = str(uuid4())
    classified_at = datetime.now(UTC)
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle eligibility"))
    store = PostgresIngestionJobStore(SessionFactory)
    try:
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=work_id,
                workspace_id=workspace_id,
                object_key=uuid4().hex,
                state=LifecycleWorkState.QUEUED,
                artifact_class="failed_upload_diagnostic",
                eligible_at=classified_at + timedelta(hours=24),
                discovery_recorded_at=classified_at,
            )
        )
        with SessionFactory() as session:
            persisted = session.get(ObjectLifecycleWorkTable, work_id)
            assert persisted is not None
            assert persisted.discovery_recorded_at == classified_at
        assert store.claim(worker_id="worker-a", work_id=work_id) is None

        with SessionFactory.begin() as session:
            session.execute(
                update(ObjectLifecycleWorkTable)
                .where(ObjectLifecycleWorkTable.id == work_id)
                .values(eligible_at=datetime.now(UTC) - timedelta(seconds=1))
            )

        claimed = store.claim(worker_id="worker-a", work_id=work_id)
        assert claimed is not None
        assert claimed.work_id == work_id
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(
                delete(ObjectLifecycleWorkTable).where(ObjectLifecycleWorkTable.id == work_id)
            )
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_delete_revalidation_honors_other_active_diagnostic_retention() -> None:
    workspace_id = f"lifecycle-retention-blocker-{uuid4()}"
    orphan_work_id = str(uuid4())
    diagnostic_work_id = str(uuid4())
    object_key = uuid4().hex
    classified_at = datetime.now(UTC)
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle retention blocker"))
    store = PostgresIngestionJobStore(SessionFactory)
    object_store = CountingDelete()
    try:
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=diagnostic_work_id,
                workspace_id=workspace_id,
                object_key=object_key,
                state=LifecycleWorkState.QUEUED,
                artifact_class="failed_upload_diagnostic",
                lifecycle_generation=diagnostic_work_id,
                discovery_recorded_at=classified_at,
                eligible_at=classified_at + timedelta(hours=24),
            )
        )
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=orphan_work_id,
                workspace_id=workspace_id,
                object_key=object_key,
                state=LifecycleWorkState.QUEUED,
                artifact_class="orphan",
                lifecycle_generation=orphan_work_id,
                eligible_at=classified_at,
            )
        )

        result = ObjectLifecycleWorker(
            maintenance=store,
            object_store=object_store,
            retry_policy=ObjectLifecycleRetryPolicyV1(random_source=OneSample(0)),
        ).run_once(worker_id="worker-a", work_id=orphan_work_id)

        assert result.outcome == "not_eligible"
        assert object_store.count == 0

        with SessionFactory.begin() as session:
            expired_at = datetime.now(UTC) - timedelta(seconds=1)
            session.execute(
                update(ObjectLifecycleWorkTable)
                .where(ObjectLifecycleWorkTable.id == diagnostic_work_id)
                .values(eligible_at=expired_at)
            )
            session.execute(
                update(ObjectLifecycleWorkTable)
                .where(ObjectLifecycleWorkTable.id == orphan_work_id)
                .values(lease_expires_at=expired_at)
            )

        retry = ObjectLifecycleWorker(
            maintenance=store,
            object_store=object_store,
            retry_policy=ObjectLifecycleRetryPolicyV1(random_source=OneSample(0)),
        ).run_once(worker_id="worker-a", work_id=orphan_work_id)

        assert retry.outcome == "succeeded"
        assert object_store.count == 1
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_lifecycle_work_rejects_attempt_count_beyond_total_budget() -> None:
    workspace_id = f"lifecycle-attempt-budget-{uuid4()}"
    work_id = str(uuid4())
    now = datetime.now(UTC)
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle attempt budget"))

    try:
        with pytest.raises(IntegrityError), SessionFactory.begin() as session:
            session.add(
                ObjectLifecycleWorkTable(
                    id=work_id,
                    workspace_id=workspace_id,
                    object_key=uuid4().hex,
                    artifact_class="orphan",
                    lifecycle_generation=work_id,
                    state=LifecycleWorkState.QUEUED.value,
                    attempt_count=5,
                    max_attempts=4,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.flush()
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_lifecycle_attempt_rejects_attempt_number_beyond_total_budget() -> None:
    workspace_id = f"lifecycle-attempt-number-budget-{uuid4()}"
    work_id = str(uuid4())
    now = datetime.now(UTC)
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle attempt number budget"))
        session.flush()
        session.add(
            ObjectLifecycleWorkTable(
                id=work_id,
                workspace_id=workspace_id,
                object_key=uuid4().hex,
                artifact_class="orphan",
                lifecycle_generation=work_id,
                state=LifecycleWorkState.FAILED.value,
                attempt_count=4,
                max_attempts=4,
                created_at=now,
                updated_at=now,
                terminal_at=now,
            )
        )

    try:
        with pytest.raises(IntegrityError), SessionFactory.begin() as session:
            session.add(
                ObjectLifecycleAttemptTable(
                    object_lifecycle_work_id=work_id,
                    attempt_number=5,
                    worker_id="worker-a",
                    lease_version=5,
                    claim_operation_id=str(uuid4()),
                    attempt_started_at=now,
                )
            )
            session.flush()
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_lifecycle_enqueue_rejects_invalid_diagnostic_retention_metadata() -> None:
    workspace_id = f"lifecycle-invalid-diagnostic-{uuid4()}"
    classified_at = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="invalid diagnostic retention"))

    store = PostgresIngestionJobStore(SessionFactory)
    try:
        invalid_items = (
            ObjectLifecycleWorkItem(
                work_id=f"{workspace_id}-missing-classification",
                workspace_id=workspace_id,
                object_key=uuid4().hex,
                state=LifecycleWorkState.QUEUED,
                artifact_class="failed_upload_diagnostic",
                eligible_at=classified_at + timedelta(hours=24),
            ),
            ObjectLifecycleWorkItem(
                work_id=f"{workspace_id}-too-early",
                workspace_id=workspace_id,
                object_key=uuid4().hex,
                state=LifecycleWorkState.QUEUED,
                artifact_class="failed_upload_diagnostic",
                discovery_recorded_at=classified_at,
                eligible_at=classified_at + timedelta(hours=23, minutes=59),
            ),
        )
        for item in invalid_items:
            with pytest.raises(ValueError, match="failed-upload diagnostic retention"):
                store.enqueue(item)

        with SessionFactory() as session:
            assert session.scalar(
                select(ObjectLifecycleWorkTable.id).where(
                    ObjectLifecycleWorkTable.workspace_id == workspace_id
                )
            ) is None
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_reference_resolver_retains_diagnostic_before_eligibility() -> None:
    workspace_id = f"lifecycle-diagnostic-retention-{uuid4()}"
    work_id = str(uuid4())
    object_key = uuid4().hex
    classified_at = datetime.now(UTC)
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="diagnostic retention"))
        session.flush()
        session.add(
            ObjectLifecycleWorkTable(
                id=work_id,
                workspace_id=workspace_id,
                object_key=object_key,
                artifact_class="failed_upload_diagnostic",
                lifecycle_generation=work_id,
                state=LifecycleWorkState.SUCCEEDED.value,
                max_attempts=4,
                eligible_at=classified_at + timedelta(hours=1),
                discovery_recorded_at=classified_at,
            )
        )

    try:
        assert PostgresObjectReferenceResolver(SessionFactory).is_authoritatively_retained(
            workspace_id=workspace_id, object_key=object_key
        )
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_reference_resolver_releases_failed_diagnostic_after_eligibility() -> None:
    workspace_id = f"lifecycle-diagnostic-expired-{uuid4()}"
    work_id = str(uuid4())
    object_key = uuid4().hex
    now = datetime.now(UTC)
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="expired diagnostic retention"))
        session.flush()
        session.add(
            ObjectLifecycleWorkTable(
                id=work_id,
                workspace_id=workspace_id,
                object_key=object_key,
                artifact_class="failed_upload_diagnostic",
                lifecycle_generation=work_id,
                state=LifecycleWorkState.FAILED.value,
                max_attempts=4,
                eligible_at=now - timedelta(hours=1),
                discovery_recorded_at=now - timedelta(hours=25),
            )
        )

    try:
        assert not PostgresObjectReferenceResolver(SessionFactory).is_authoritatively_retained(
            workspace_id=workspace_id, object_key=object_key
        )
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_reference_resolver_suppresses_active_staging_duplicate_orphan() -> None:
    workspace_id = f"lifecycle-staging-active-{uuid4()}"
    work_id = str(uuid4())
    object_key = uuid4().hex
    now = datetime.now(UTC)
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="active staging cleanup"))
        session.flush()
        session.add(
            ObjectLifecycleWorkTable(
                id=work_id,
                workspace_id=workspace_id,
                object_key=object_key,
                artifact_class="staging",
                lifecycle_generation=work_id,
                state=LifecycleWorkState.QUEUED.value,
                max_attempts=4,
                eligible_at=now - timedelta(hours=1),
                created_at=now,
                updated_at=now,
            )
        )

    try:
        assert PostgresObjectReferenceResolver(SessionFactory).is_authoritatively_retained(
            workspace_id=workspace_id, object_key=object_key
        )
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_reference_resolver_retains_active_cleanup_after_eligibility() -> None:
    workspace_id = f"lifecycle-diagnostic-active-{uuid4()}"
    work_id = str(uuid4())
    object_key = uuid4().hex
    now = datetime.now(UTC)
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="active diagnostic cleanup"))
        session.flush()
        session.add(
            ObjectLifecycleWorkTable(
                id=work_id,
                workspace_id=workspace_id,
                object_key=object_key,
                artifact_class="failed_upload_diagnostic",
                lifecycle_generation=work_id,
                state=LifecycleWorkState.RETRY_SCHEDULED.value,
                max_attempts=4,
                eligible_at=now - timedelta(hours=1),
                discovery_recorded_at=now - timedelta(hours=25),
            )
        )

    try:
        assert PostgresObjectReferenceResolver(SessionFactory).is_authoritatively_retained(
            workspace_id=workspace_id, object_key=object_key
        )
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_report_only_orphan_can_record_completed_repair() -> None:
    workspace_id = f"lifecycle-repair-{uuid4()}"
    work_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle repair"))
    store = PostgresIngestionJobStore(SessionFactory)
    try:
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=work_id,
                workspace_id=workspace_id,
                object_key=uuid4().hex,
                state=LifecycleWorkState.QUEUED,
                artifact_class="orphan_report",
            )
        )
        claimed = store.claim(worker_id="worker-a", work_id=work_id)
        assert claimed is not None
        claim = LifecycleClaim(
            work_id=work_id,
            worker_id="worker-a",
            attempt_number=claimed.attempt_count,
            lease_version=claimed.lease_version,
        )
        store.suppress(claim=claim, operation_id="report-op")

        assert store.complete_orphan_reconciliation(
            work_id=work_id, disposition="repaired"
        )
        assert not store.complete_orphan_reconciliation(
            work_id=work_id, disposition="repaired"
        )
        with SessionFactory() as session:
            work = session.get(ObjectLifecycleWorkTable, work_id)
            assert work is not None
            assert work.reconciliation_disposition == "repaired"
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


class CountingDelete:
    def __init__(self) -> None:
        self.count = 0

    def delete(self, *, workspace_id: str, object_key: str) -> None:
        del workspace_id, object_key
        self.count += 1


class AlreadyAbsent:
    def __init__(self) -> None:
        self.deletes = 0

    def head(self, *, workspace_id: str, object_key: str) -> object:
        del workspace_id, object_key
        raise KnoraError("OBJECT_NOT_FOUND")

    def delete(self, *, workspace_id: str, object_key: str) -> None:
        del workspace_id, object_key
        self.deletes += 1


def test_postgres_crash_reconciliation_reissues_generation_for_new_owner() -> None:
    workspace_id = f"lifecycle-crash-generation-{uuid4()}"
    work_id = str(uuid4())
    object_key = uuid4().hex
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle crash generation"))
    store = PostgresIngestionJobStore(SessionFactory)
    object_store = AlreadyAbsent()
    try:
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=work_id,
                workspace_id=workspace_id,
                object_key=object_key,
                state=LifecycleWorkState.QUEUED,
            )
        )
        first = store.claim(worker_id="worker-a", work_id=work_id)
        assert first is not None
        first_claim = LifecycleClaim(
            work_id=work_id,
            worker_id="worker-a",
            attempt_number=1,
            lease_version=first.lease_version,
        )
        generation_a = store.prepare_delete(claim=first_claim)
        with SessionFactory.begin() as session:
            session.execute(
                update(ObjectLifecycleWorkTable)
                .where(ObjectLifecycleWorkTable.id == work_id)
                .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )

        worker = ObjectLifecycleWorker(
            maintenance=store,
            object_store=object_store,
            retry_policy=ObjectLifecycleRetryPolicyV1(random_source=OneSample(0)),
        )
        result = worker.run_once(worker_id="worker-b", work_id=work_id)

        assert result.outcome == "succeeded"
        assert object_store.deletes == 0
        with SessionFactory() as session:
            attempts = session.scalars(
                select(ObjectLifecycleAttemptTable)
                .where(ObjectLifecycleAttemptTable.object_lifecycle_work_id == work_id)
                .order_by(ObjectLifecycleAttemptTable.attempt_number)
            ).all()
            assert len(attempts) == 2
            assert attempts[0].deletion_generation == generation_a
            assert attempts[1].deletion_generation is not None
            assert attempts[1].deletion_generation != generation_a
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


class AttachOnRevalidation(PostgresIngestionJobStore):
    def __init__(self, *, workspace_id: str, object_key: str) -> None:
        super().__init__(SessionFactory)
        self._workspace_id = workspace_id
        self._object_key = object_key
        self.attached = False

    def revalidate_delete(self, *, claim: LifecycleClaim, delete_generation: str) -> None:
        with SessionFactory.begin() as session:
            document_id = str(uuid4())
            version_id = str(uuid4())
            session.add(
                DocumentTable(
                    id=document_id,
                    workspace_id=self._workspace_id,
                    source_key=f"attached-{uuid4()}",
                    source_name="attached.pdf",
                    revision=0,
                )
            )
            session.flush()
            session.add(
                DocumentVersionTable(
                    id=version_id,
                    document_id=document_id,
                    raw_sha256="a" * 64,
                    media_type="application/pdf",
                    version_number=1,
                )
            )
            session.flush()
            session.add(
                OriginalSourceObjectTable(
                    id=str(uuid4()),
                    workspace_id=self._workspace_id,
                    document_version_id=version_id,
                    object_key=self._object_key,
                    raw_sha256="a" * 64,
                    byte_size=1,
                    media_type="application/pdf",
                )
            )
            session.flush()
            session.execute(
                update(DocumentTable)
                .where(DocumentTable.id == document_id)
                .values(current_document_version_id=version_id)
            )
        self.attached = True
        super().revalidate_delete(claim=claim, delete_generation=delete_generation)


def test_postgres_worker_revalidates_attachment_after_prepare_before_delete() -> None:
    workspace_id = f"lifecycle-attachment-{uuid4()}"
    work_id = str(uuid4())
    object_key = uuid4().hex
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle attachment"))
    maintenance = AttachOnRevalidation(workspace_id=workspace_id, object_key=object_key)
    object_store = CountingDelete()
    try:
        maintenance.enqueue(
            ObjectLifecycleWorkItem(
                work_id=work_id,
                workspace_id=workspace_id,
                object_key=object_key,
                state=LifecycleWorkState.QUEUED,
            )
        )
        result = ObjectLifecycleWorker(
            maintenance=maintenance,
            object_store=object_store,
            retry_policy=ObjectLifecycleRetryPolicyV1(random_source=OneSample(0)),
        ).run_once(worker_id="worker-a", work_id=work_id)

        assert maintenance.attached
        assert result.outcome == "suppressed"
        assert object_store.count == 0
        with SessionFactory() as session:
            assert (
                session.scalar(
                    select(OriginalSourceObjectTable.id).where(
                        OriginalSourceObjectTable.workspace_id == workspace_id,
                        OriginalSourceObjectTable.object_key == object_key,
                    )
                )
                is not None
            )
    finally:
        with SessionFactory.begin() as session:
            version_ids = select(DocumentVersionTable.id).where(
                DocumentVersionTable.document_id.in_(
                    select(DocumentTable.id).where(DocumentTable.workspace_id == workspace_id)
                )
            )
            session.execute(
                delete(OriginalSourceObjectTable).where(
                    OriginalSourceObjectTable.workspace_id == workspace_id
                )
            )
            session.execute(
                update(DocumentTable)
                .where(DocumentTable.workspace_id == workspace_id)
                .values(current_document_version_id=None)
            )
            session.execute(delete(DocumentVersionTable).where(DocumentVersionTable.id.in_(version_ids)))
            session.execute(delete(DocumentTable).where(DocumentTable.workspace_id == workspace_id))
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(
                delete(ObjectLifecycleWorkTable).where(ObjectLifecycleWorkTable.id == work_id)
            )
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_worker_completes_unchanged_prepared_generation() -> None:
    workspace_id = f"lifecycle-positive-{uuid4()}"
    work_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle positive"))
    store = PostgresIngestionJobStore(SessionFactory)
    object_store = CountingDelete()
    try:
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=work_id,
                workspace_id=workspace_id,
                object_key=uuid4().hex,
                state=LifecycleWorkState.QUEUED,
            )
        )
        result = ObjectLifecycleWorker(
            maintenance=store,
            object_store=object_store,
            retry_policy=ObjectLifecycleRetryPolicyV1(random_source=OneSample(0)),
        ).run_once(worker_id="worker-a", work_id=work_id)

        assert result.outcome == "succeeded"
        assert object_store.count == 1
        with SessionFactory() as session:
            work = session.get(ObjectLifecycleWorkTable, work_id)
            assert work is not None
            assert work.state == LifecycleWorkState.SUCCEEDED.value
            assert work.deletion_generation is not None
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(
                delete(ObjectLifecycleWorkTable).where(ObjectLifecycleWorkTable.id == work_id)
            )
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_worker_replays_successful_cleanup_without_second_effect() -> None:
    workspace_id = f"lifecycle-success-replay-{uuid4()}"
    work_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle success replay"))
    store = PostgresIngestionJobStore(SessionFactory)
    object_store = CountingDelete()
    worker = ObjectLifecycleWorker(
        maintenance=store,
        object_store=object_store,
        retry_policy=ObjectLifecycleRetryPolicyV1(random_source=OneSample(0)),
    )
    try:
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=work_id,
                workspace_id=workspace_id,
                object_key=uuid4().hex,
                state=LifecycleWorkState.QUEUED,
            )
        )
        first = worker.run_once(
            worker_id="worker-a", operation_id="delivery-success", work_id=work_id
        )
        replay = worker.run_once(
            worker_id="worker-a", operation_id="delivery-success", work_id=work_id
        )

        assert first.outcome == "succeeded"
        assert replay.outcome == "succeeded"
        assert object_store.count == 1
        with SessionFactory() as session:
            attempts = session.scalars(
                select(ObjectLifecycleAttemptTable).where(
                    ObjectLifecycleAttemptTable.object_lifecycle_work_id == work_id
                )
            ).all()
            assert len(attempts) == 1
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(
                delete(ObjectLifecycleWorkTable).where(ObjectLifecycleWorkTable.id == work_id)
            )
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_lifecycle_operation_replay_keeps_one_attempt_and_exact_retry_fields() -> None:
    workspace_id = f"lifecycle-replay-{uuid4()}"
    work_id = str(uuid4())
    object_key = uuid4().hex
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle replay"))
    store = PostgresIngestionJobStore(SessionFactory)
    try:
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=work_id,
                workspace_id=workspace_id,
                object_key=object_key,
                state=LifecycleWorkState.QUEUED,
            )
        )
        claimed = store.claim(worker_id="worker-a", operation_id="claim-op", work_id=work_id)
        assert claimed is not None
        replayed = store.claim(worker_id="worker-a", operation_id="claim-op", work_id=work_id)
        assert replayed == claimed
        claim = LifecycleClaim(
            work_id=work_id,
            worker_id="worker-a",
            attempt_number=1,
            lease_version=claimed.lease_version,
            claim_operation_id="claim-op",
        )
        generation = store.prepare_delete(claim=claim, operation_id="prepare-op")
        assert store.prepare_delete(claim=claim, operation_id="prepare-op") == generation
        store.fail(
            claim=claim,
            retry_delay=timedelta(seconds=3),
            operation_id="failure-op",
            retry_policy_version="object-lifecycle-retry-v1",
            retry_window_upper_bound_microseconds=5_000_000,
        )
        assert store.fail(
            claim=claim,
            retry_delay=timedelta(seconds=3),
            operation_id="failure-op",
            retry_policy_version="object-lifecycle-retry-v1",
            retry_window_upper_bound_microseconds=5_000_000,
        ) == LifecycleWorkState.RETRY_SCHEDULED
        with pytest.raises(PermissionError, match="operation|request"):
            store.fail(
                claim=claim,
                retry_delay=timedelta(seconds=4),
                operation_id="failure-op",
                retry_policy_version="object-lifecycle-retry-v1",
                retry_window_upper_bound_microseconds=5_000_000,
            )

        with SessionFactory() as session:
            attempt = session.scalar(
                select(ObjectLifecycleAttemptTable).where(
                    ObjectLifecycleAttemptTable.object_lifecycle_work_id == work_id,
                    ObjectLifecycleAttemptTable.attempt_number == 1,
                )
            )
            assert attempt is not None
            assert attempt.claim_operation_id == "claim-op"
            assert attempt.prepare_operation_id == "prepare-op"
            assert attempt.deletion_generation == generation
            assert attempt.retry_policy_version == "object-lifecycle-retry-v1"
            assert attempt.retry_window_upper_bound_microseconds == 5_000_000
            assert attempt.retry_delay_microseconds == 3_000_000
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(
                delete(ObjectLifecycleWorkTable).where(ObjectLifecycleWorkTable.id == work_id)
            )
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


class FailingDelete:
    def delete(self, *, workspace_id: str, object_key: str) -> None:
        del workspace_id, object_key
        raise OSError("controlled cleanup failure")


class OneSample:
    def __init__(self, sample: int) -> None:
        self.sample_value = sample
        self.bounds: list[int] = []

    def sample(self, upper_bound_microseconds: int) -> int:
        self.bounds.append(upper_bound_microseconds)
        return self.sample_value


class Samples:
    def __init__(self, values: list[int]) -> None:
        self.values = values
        self.bounds: list[int] = []

    def sample(self, upper_bound_microseconds: int) -> int:
        self.bounds.append(upper_bound_microseconds)
        return self.values.pop(0)


def test_postgres_worker_persists_exact_policy_sample_and_window() -> None:
    workspace_id = f"lifecycle-worker-{uuid4()}"
    work_id = str(uuid4())
    object_key = uuid4().hex
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle worker"))
    store = PostgresIngestionJobStore(SessionFactory)
    random = OneSample(123_456)
    try:
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=work_id,
                workspace_id=workspace_id,
                object_key=object_key,
                state=LifecycleWorkState.QUEUED,
            )
        )
        result = ObjectLifecycleWorker(
            maintenance=store,
            object_store=FailingDelete(),
            retry_policy=ObjectLifecycleRetryPolicyV1(random_source=random),
        ).run_once(worker_id="worker-a", operation_id=str(uuid4()), work_id=work_id)
        assert result.outcome == "retry_scheduled"
        assert random.bounds == [5_000_000]
        with SessionFactory() as session:
            attempt = session.scalar(
                select(ObjectLifecycleAttemptTable).where(
                    ObjectLifecycleAttemptTable.object_lifecycle_work_id == work_id,
                    ObjectLifecycleAttemptTable.attempt_number == 1,
                )
            )
            assert attempt is not None
            assert attempt.retry_policy_version == "object-lifecycle-retry-v1"
            assert attempt.retry_window_upper_bound_microseconds == 5_000_000
            assert attempt.retry_delay_microseconds == 123_456
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(
                delete(ObjectLifecycleWorkTable).where(ObjectLifecycleWorkTable.id == work_id)
            )
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_postgres_worker_exhausts_exactly_four_retry_attempts() -> None:
    workspace_id = f"lifecycle-budget-{uuid4()}"
    work_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="lifecycle budget"))
    store = PostgresIngestionJobStore(SessionFactory)
    random = Samples([123, 456, 789])
    try:
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id=work_id,
                workspace_id=workspace_id,
                object_key=uuid4().hex,
                state=LifecycleWorkState.QUEUED,
            )
        )
        worker = ObjectLifecycleWorker(
            maintenance=store,
            object_store=FailingDelete(),
            retry_policy=ObjectLifecycleRetryPolicyV1(random_source=random),
        )
        for attempt_number in range(1, 5):
            result = worker.run_once(worker_id="worker-a", work_id=work_id)
            expected = "failed" if attempt_number == 4 else "retry_scheduled"
            assert result.outcome == expected
            if attempt_number < 4:
                with SessionFactory.begin() as session:
                    session.execute(
                        update(ObjectLifecycleWorkTable)
                        .where(ObjectLifecycleWorkTable.id == work_id)
                        .values(next_attempt_at=datetime.now(UTC) - timedelta(seconds=1))
                    )

        assert random.bounds == [5_000_000, 30_000_000, 120_000_000]
        with SessionFactory() as session:
            work = session.get(ObjectLifecycleWorkTable, work_id)
            attempts = session.scalars(
                select(ObjectLifecycleAttemptTable)
                .where(ObjectLifecycleAttemptTable.object_lifecycle_work_id == work_id)
                .order_by(ObjectLifecycleAttemptTable.attempt_number)
            ).all()
            assert work is not None and work.state == LifecycleWorkState.FAILED.value
            assert len(attempts) == 4
            assert [attempt.retry_delay_microseconds for attempt in attempts[:3]] == [123, 456, 789]
            assert attempts[-1].retry_delay_microseconds is None
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(
                delete(ObjectLifecycleWorkTable).where(ObjectLifecycleWorkTable.id == work_id)
            )
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))
