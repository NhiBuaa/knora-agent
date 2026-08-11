from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, text

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.operational_observability import PostgresOperationalMetricsStore
from knora.adapters.postgres.tables import (
    ObjectLifecycleAttemptTable,
    ObjectLifecycleWorkTable,
    WorkspaceTable,
)
from knora.ingestion.object_lifecycle import LifecycleWorkState


@pytest.fixture(autouse=True)
def clean_lifecycle_state():
    with SessionFactory.begin() as session:
        session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
    yield
    with SessionFactory.begin() as session:
        session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))


def test_postgres_operational_metrics_count_completed_orphan_dispositions_once() -> None:
    workspace_id = f"metrics-orphan-{uuid4()}"
    cleanup_work_id = str(uuid4())
    repaired_id = str(uuid4())
    report_repair_id = str(uuid4())
    deleted_id = str(uuid4())
    unresolved_id = str(uuid4())
    undiscovered_id = str(uuid4())
    now = datetime.now(UTC)
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="metrics orphan"))
        session.flush()
        session.add_all(
            [
                ObjectLifecycleWorkTable(
                    id=cleanup_work_id,
                    workspace_id=workspace_id,
                    object_key=uuid4().hex,
                    artifact_class="terminal_cleanup",
                    lifecycle_generation=cleanup_work_id,
                    state=LifecycleWorkState.SUCCEEDED.value,
                    attempt_count=2,
                    max_attempts=4,
                    created_at=now,
                    updated_at=now,
                    terminal_at=now,
                ),
                ObjectLifecycleWorkTable(
                    id=repaired_id,
                    workspace_id=workspace_id,
                    object_key=uuid4().hex,
                    artifact_class="orphan",
                    lifecycle_generation=repaired_id,
                    state=LifecycleWorkState.SUCCEEDED.value,
                    max_attempts=4,
                    created_at=now,
                    updated_at=now,
                    terminal_at=now,
                    reconciliation_disposition="repaired",
                ),
                ObjectLifecycleWorkTable(
                    id=deleted_id,
                    workspace_id=workspace_id,
                    object_key=uuid4().hex,
                    artifact_class="orphan",
                    lifecycle_generation=deleted_id,
                    state=LifecycleWorkState.SUCCEEDED.value,
                    max_attempts=4,
                    created_at=now,
                    updated_at=now,
                    terminal_at=now,
                    reconciliation_disposition="deleted",
                ),
                ObjectLifecycleWorkTable(
                    id=report_repair_id,
                    workspace_id=workspace_id,
                    object_key=uuid4().hex,
                    artifact_class="orphan_report",
                    lifecycle_generation=report_repair_id,
                    state=LifecycleWorkState.SUCCEEDED.value,
                    max_attempts=4,
                    created_at=now,
                    updated_at=now,
                    terminal_at=now,
                    reconciliation_disposition="reported",
                ),
                ObjectLifecycleWorkTable(
                    id=unresolved_id,
                    workspace_id=workspace_id,
                    object_key=uuid4().hex,
                    artifact_class="orphan",
                    lifecycle_generation=unresolved_id,
                    state=LifecycleWorkState.QUEUED.value,
                    max_attempts=4,
                    created_at=now,
                    updated_at=now,
                    discovery_recorded_at=now,
                ),
                ObjectLifecycleWorkTable(
                    id=undiscovered_id,
                    workspace_id=workspace_id,
                    object_key=uuid4().hex,
                    artifact_class="orphan",
                    lifecycle_generation=undiscovered_id,
                    state=LifecycleWorkState.QUEUED.value,
                    max_attempts=4,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                ObjectLifecycleAttemptTable(
                    object_lifecycle_work_id=cleanup_work_id,
                    attempt_number=1,
                    worker_id="worker-a",
                    lease_version=1,
                    claim_operation_id=str(uuid4()),
                    attempt_started_at=now,
                    closed_at=now,
                    disposition="failed",
                ),
                ObjectLifecycleAttemptTable(
                    object_lifecycle_work_id=cleanup_work_id,
                    attempt_number=2,
                    worker_id="worker-b",
                    lease_version=2,
                    claim_operation_id=str(uuid4()),
                    attempt_started_at=now,
                    closed_at=now,
                    disposition="succeeded",
                ),
            ]
        )

    try:
        store = PostgresIngestionJobStore(SessionFactory)
        metrics = PostgresOperationalMetricsStore(
            SessionFactory,
            retry_window=timedelta(days=1),
        )
        assert store.complete_orphan_reconciliation(
            work_id=report_repair_id, disposition="repaired"
        )
        baseline = metrics.snapshot().metrics
        assert baseline["cleanup_attempt_total"] >= 2
        assert baseline["cleanup_failure_total"] >= 1
        assert baseline["orphan_discovery_total"] == 1
        assert baseline["orphan_reconciliation_total"] >= 3

        assert (
            store.complete_orphan_reconciliation(work_id=repaired_id, disposition="repaired")
            is False
        )
        assert (
            store.complete_orphan_reconciliation(work_id=deleted_id, disposition="deleted") is False
        )
        assert (
            store.complete_orphan_reconciliation(work_id=report_repair_id, disposition="repaired")
            is False
        )
        replay = metrics.snapshot().metrics
        assert replay["orphan_reconciliation_total"] == baseline["orphan_reconciliation_total"]
        assert replay["cleanup_attempt_total"] == baseline["cleanup_attempt_total"]
        assert replay["cleanup_failure_total"] == baseline["cleanup_failure_total"]
    finally:
        with SessionFactory.begin() as session:
            session.execute(text("TRUNCATE TABLE object_lifecycle_attempts, object_lifecycle_work"))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))
