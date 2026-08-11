from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

import pytest

from knora.domain.errors import KnoraError
from knora.ingestion.object_lifecycle import (
    InMemoryObjectLifecycleMaintenance,
    LifecycleClaim,
    LifecycleRetentionPending,
    LifecycleWorkState,
    ObjectLifecycleReconciler,
    ObjectLifecycleRetryPolicyV1,
    ObjectLifecycleWorker,
    ObjectLifecycleWorkItem,
    SnapshotObjectInventory,
)


@dataclass
class ControlledRandomSource:
    samples: list[int]
    requests: list[int]

    def sample(self, upper_bound_microseconds: int) -> int:
        self.requests.append(upper_bound_microseconds)
        return self.samples.pop(0)


def test_object_lifecycle_retry_uses_one_controlled_sample_per_window() -> None:
    source = ControlledRandomSource(samples=[3, 7, 11], requests=[])
    policy = ObjectLifecycleRetryPolicyV1(random_source=source)

    first = policy.schedule(attempt_number=1)
    second = policy.schedule(attempt_number=2)
    third = policy.schedule(attempt_number=3)

    assert source.requests == [5_000_000, 30_000_000, 120_000_000]
    assert [first.delay_microseconds, second.delay_microseconds, third.delay_microseconds] == [
        3,
        7,
        11,
    ]


@pytest.mark.parametrize("attempt_number", [True, 1.0, 0, 4])
def test_object_lifecycle_retry_rejects_invalid_scheduling_attempt_numbers(
    attempt_number: object,
) -> None:
    policy = ObjectLifecycleRetryPolicyV1(
        random_source=ControlledRandomSource(samples=[0], requests=[])
    )

    with pytest.raises(ValueError, match="attempts one through three"):
        policy.schedule(attempt_number=attempt_number)  # type: ignore[arg-type]


def test_lifecycle_claim_is_single_owner_and_stale_generation_is_fenced() -> None:
    store = InMemoryObjectLifecycleMaintenance(lease_duration=timedelta(seconds=10))
    store.enqueue(
        ObjectLifecycleWorkItem(
            work_id="work-1",
            workspace_id="workspace-1",
            object_key="object-1",
            state=LifecycleWorkState.QUEUED,
        )
    )

    owned = store.claim(worker_id="worker-a")
    assert owned is not None
    assert store.claim(worker_id="worker-b") is None
    claim = LifecycleClaim("work-1", "worker-a", 1, owned.lease_version)
    generation = store.prepare_delete(claim=claim)
    assert store.prepare_delete(claim=claim) == generation
    store.fence(work_id="work-1")

    with pytest.raises(PermissionError, match="fenced"):
        store.complete(claim=claim, delete_generation=generation)

    recovered = store.claim(worker_id="worker-b")
    assert recovered is not None
    assert recovered.worker_id == "worker-b"
    assert recovered.attempt_count == 2
    assert recovered.lease_version == owned.lease_version + 1
    with pytest.raises(PermissionError, match="fenced"):
        store.prepare_delete(claim=claim)


def test_stale_delete_generation_cannot_complete_after_lease_handoff() -> None:
    store = InMemoryObjectLifecycleMaintenance(lease_duration=timedelta(seconds=10))
    store.enqueue(
        ObjectLifecycleWorkItem(
            work_id="prepared-handoff",
            workspace_id="workspace-1",
            object_key="object-1",
            state=LifecycleWorkState.QUEUED,
        )
    )

    first = store.claim(worker_id="worker-a")
    assert first is not None
    first_claim = LifecycleClaim("prepared-handoff", "worker-a", 1, first.lease_version)
    generation_a = store.prepare_delete(claim=first_claim)
    store.fence(work_id="prepared-handoff")

    second = store.claim(worker_id="worker-b")
    assert second is not None
    second_claim = LifecycleClaim(
        "prepared-handoff", "worker-b", 2, second.lease_version
    )
    with pytest.raises(PermissionError, match="stale delete generation"):
        store.complete(claim=second_claim, delete_generation=generation_a)

    generation_b = store.prepare_delete(claim=second_claim)
    assert generation_b != generation_a
    assert store.complete(claim=second_claim, delete_generation=generation_b).state == (
        LifecycleWorkState.SUCCEEDED
    )


def test_reconciler_counts_an_orphan_only_once_across_reobservations() -> None:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    inventory = SnapshotObjectInventory({"w1": [("old", now - timedelta(days=2))]})
    maintenance = InMemoryObjectLifecycleMaintenance()
    reconciler = ObjectLifecycleReconciler(
        inventory=inventory,
        references=References(set()),
        maintenance=maintenance,
        minimum_age=timedelta(days=1),
        now=Clock(now),
    )

    assert reconciler.reconcile(workspace_id="w1") == 1
    assert reconciler.reconcile(workspace_id="w1") == 0


def test_lifecycle_claim_does_not_dispatch_before_retention_eligibility() -> None:
    store = InMemoryObjectLifecycleMaintenance()
    classified_at = datetime.now(UTC)
    store.enqueue(
        ObjectLifecycleWorkItem(
            work_id="too-young",
            workspace_id="w1",
            object_key="diagnostic",
            state=LifecycleWorkState.QUEUED,
            eligible_at=classified_at + timedelta(hours=24),
            discovery_recorded_at=classified_at,
            artifact_class="failed_upload_diagnostic",
        )
    )

    assert store.claim(worker_id="worker-a") is None

    store.advance(timedelta(days=1, seconds=1))
    claimed = store.claim(worker_id="worker-a")
    assert claimed is not None
    assert claimed.work_id == "too-young"


@pytest.mark.parametrize(
    ("discovery_recorded_at", "eligible_at"),
    [
        (None, datetime(2026, 1, 3, 12, tzinfo=UTC)),
        (
            datetime(2026, 1, 2, 12, tzinfo=UTC),
            datetime(2026, 1, 3, 11, 59, 59, tzinfo=UTC),
        ),
    ],
)
def test_failed_upload_diagnostic_enqueue_requires_durable_24_hour_retention(
    discovery_recorded_at: datetime | None,
    eligible_at: datetime,
) -> None:
    store = InMemoryObjectLifecycleMaintenance()

    with pytest.raises(ValueError, match="failed-upload diagnostic retention"):
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id="invalid-diagnostic-retention",
                workspace_id="w1",
                object_key="diagnostic",
                state=LifecycleWorkState.QUEUED,
                artifact_class="failed_upload_diagnostic",
                discovery_recorded_at=discovery_recorded_at,
                eligible_at=eligible_at,
            )
        )


def test_failed_upload_diagnostic_enqueue_requires_timezone_aware_timestamps() -> None:
    store = InMemoryObjectLifecycleMaintenance()
    classified_at = datetime(2026, 8, 10, 12, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id="naive-diagnostic-retention",
                workspace_id="w1",
                object_key="diagnostic",
                state=LifecycleWorkState.QUEUED,
                artifact_class="failed_upload_diagnostic",
                discovery_recorded_at=classified_at,
                eligible_at=classified_at + timedelta(hours=24),
            )
        )


def test_lifecycle_enqueue_rejects_attempt_count_beyond_budget() -> None:
    store = InMemoryObjectLifecycleMaintenance()

    with pytest.raises(ValueError, match="attempt count"):
        store.enqueue(
            ObjectLifecycleWorkItem(
                work_id="over-budget",
                workspace_id="w1",
                object_key="object-1",
                state=LifecycleWorkState.QUEUED,
                attempt_count=5,
            )
        )


class PendingOnPrepare(InMemoryObjectLifecycleMaintenance):
    def prepare_delete(self, *, claim: LifecycleClaim, operation_id: str | None = None) -> str:
        del claim, operation_id
        raise LifecycleRetentionPending("controlled retention race")


def test_worker_does_not_terminalize_a_claim_when_retention_expires_after_claim() -> None:
    maintenance = PendingOnPrepare()
    maintenance.enqueue(
        ObjectLifecycleWorkItem(
            work_id="retention-race",
            workspace_id="w1",
            object_key="diagnostic",
            state=LifecycleWorkState.QUEUED,
        )
    )

    result = ObjectLifecycleWorker(
        maintenance=maintenance,
        object_store=DeletingStore(),
        retry_policy=ObjectLifecycleRetryPolicyV1(
            random_source=ControlledRandomSource(samples=[], requests=[])
        ),
    ).run_once(worker_id="worker-a", work_id="retention-race")

    assert result.outcome == "not_eligible"
    assert maintenance.read(work_id="retention-race").state == LifecycleWorkState.PROCESSING


def test_replaying_lifecycle_claim_operation_does_not_create_another_attempt() -> None:
    store = InMemoryObjectLifecycleMaintenance()
    store.enqueue(
        ObjectLifecycleWorkItem(
            work_id="replay-work",
            workspace_id="w1",
            object_key="k1",
            state=LifecycleWorkState.QUEUED,
        )
    )

    first = store.claim(worker_id="worker-a", operation_id="op-1")
    replay = store.claim(worker_id="worker-a", operation_id="op-1")

    assert first == replay
    assert len(store.attempts(work_id="replay-work")) == 1


def test_lifecycle_enqueue_deduplicates_workspace_object_artifact_generation() -> None:
    store = InMemoryObjectLifecycleMaintenance()
    first = store.enqueue(
        ObjectLifecycleWorkItem(
            work_id="work-identity-a",
            workspace_id="w1",
            object_key="object-1",
            state=LifecycleWorkState.QUEUED,
            artifact_class="staging",
            lifecycle_generation="generation-1",
        )
    )
    replay = store.enqueue(
        ObjectLifecycleWorkItem(
            work_id="work-identity-b",
            workspace_id="w1",
            object_key="object-1",
            state=LifecycleWorkState.QUEUED,
            artifact_class="staging",
            lifecycle_generation="generation-1",
        )
    )

    assert first.created
    assert not replay.created
    assert replay.work_id == first.work_id


class DeletingStore:
    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.deletes = 0

    def delete(self, *, workspace_id: str, object_key: str) -> None:
        del workspace_id, object_key
        self.deletes += 1
        if self.failures:
            self.failures -= 1
            raise OSError("transient delete")


class AlreadyDeletedStore(DeletingStore):
    def head(self, *, workspace_id: str, object_key: str) -> object:
        del workspace_id, object_key
        raise KnoraError("OBJECT_NOT_FOUND")


class HeadFailureStore(DeletingStore):
    def head(self, *, workspace_id: str, object_key: str) -> object:
        del workspace_id, object_key
        raise OSError("indeterminate head read")


def test_worker_retries_delete_without_changing_work_outcome() -> None:
    store = InMemoryObjectLifecycleMaintenance(lease_duration=timedelta(seconds=10))
    store.enqueue(
        ObjectLifecycleWorkItem(
            work_id="work-retry",
            workspace_id="workspace-1",
            object_key="object-1",
            state=LifecycleWorkState.QUEUED,
        )
    )
    random = ControlledRandomSource(samples=[5, 5], requests=[])
    deleting = DeletingStore(failures=1)
    worker = ObjectLifecycleWorker(
        maintenance=store,
        object_store=deleting,
        retry_policy=ObjectLifecycleRetryPolicyV1(random_source=random),
    )

    first = worker.run_once(worker_id="worker-a")
    assert first.outcome == "retry_scheduled"
    assert random.requests == [5_000_000]

    store.advance(timedelta(microseconds=5))
    second = worker.run_once(worker_id="worker-a")
    assert second.outcome == "succeeded"
    assert deleting.deletes == 2


def test_worker_operation_replay_returns_durable_failure_without_new_attempt() -> None:
    maintenance = InMemoryObjectLifecycleMaintenance(lease_duration=timedelta(seconds=10))
    maintenance.enqueue(
        ObjectLifecycleWorkItem(
            work_id="worker-replay",
            workspace_id="workspace-1",
            object_key="object-1",
            state=LifecycleWorkState.QUEUED,
        )
    )
    random = ControlledRandomSource(samples=[5], requests=[])
    deleting = DeletingStore(failures=1)
    worker = ObjectLifecycleWorker(
        maintenance=maintenance,
        object_store=deleting,
        retry_policy=ObjectLifecycleRetryPolicyV1(random_source=random),
    )

    first = worker.run_once(worker_id="worker-a", operation_id="delivery-1")
    replay = worker.run_once(worker_id="worker-a", operation_id="delivery-1")

    assert first.outcome == "retry_scheduled"
    assert replay.outcome == "retry_scheduled"
    assert len(maintenance.attempts(work_id="worker-replay")) == 1
    assert deleting.deletes == 1
    assert random.requests == [5_000_000]


def test_inmemory_failure_operation_replay_returns_durable_state() -> None:
    maintenance = InMemoryObjectLifecycleMaintenance()
    maintenance.enqueue(
        ObjectLifecycleWorkItem(
            work_id="failure-replay",
            workspace_id="workspace-1",
            object_key="object-1",
            state=LifecycleWorkState.QUEUED,
        )
    )
    claimed = maintenance.claim(worker_id="worker-a", operation_id="claim-op")
    assert claimed is not None
    claim = LifecycleClaim(
        work_id="failure-replay",
        worker_id="worker-a",
        attempt_number=1,
        lease_version=claimed.lease_version,
        claim_operation_id="claim-op",
    )

    first = maintenance.fail(
        claim=claim,
        retry_delay=timedelta(microseconds=5),
        operation_id="failure-op",
    )
    replay = maintenance.fail(
        claim=claim,
        retry_delay=timedelta(microseconds=5),
        operation_id="failure-op",
    )

    assert first == LifecycleWorkState.RETRY_SCHEDULED
    assert replay == first
    assert len(maintenance.attempts(work_id="failure-replay")) == 1


def test_lifecycle_failure_rejects_negative_retry_delay_without_closing_attempt() -> None:
    maintenance = InMemoryObjectLifecycleMaintenance()
    maintenance.enqueue(
        ObjectLifecycleWorkItem(
            work_id="negative-retry-delay",
            workspace_id="w1",
            object_key="object-1",
            state=LifecycleWorkState.QUEUED,
        )
    )
    claimed = maintenance.claim(worker_id="worker-a", operation_id="claim-op")
    assert claimed is not None
    claim = LifecycleClaim(
        work_id="negative-retry-delay",
        worker_id="worker-a",
        attempt_number=1,
        lease_version=claimed.lease_version,
    )

    with pytest.raises(ValueError, match="non-negative"):
        maintenance.fail(
            claim=claim,
            retry_delay=timedelta(microseconds=-1),
            operation_id="failure-op",
        )

    assert maintenance.read(work_id="negative-retry-delay").state == LifecycleWorkState.PROCESSING
    assert maintenance.attempts(work_id="negative-retry-delay")[0]["closed"] is False


def test_worker_persists_exact_controlled_samples_for_all_three_retry_windows() -> None:
    store = InMemoryObjectLifecycleMaintenance(lease_duration=timedelta(seconds=10))
    store.enqueue(
        ObjectLifecycleWorkItem(
            work_id="work-four-attempts",
            workspace_id="workspace-1",
            object_key="object-1",
            state=LifecycleWorkState.QUEUED,
        )
    )
    random = ControlledRandomSource(samples=[3, 7, 11], requests=[])
    deleting = DeletingStore(failures=3)
    worker = ObjectLifecycleWorker(
        maintenance=store,
        object_store=deleting,
        retry_policy=ObjectLifecycleRetryPolicyV1(random_source=random),
    )

    assert worker.run_once(worker_id="worker-a").outcome == "retry_scheduled"
    store.advance(timedelta(microseconds=3))
    assert worker.run_once(worker_id="worker-a").outcome == "retry_scheduled"
    store.advance(timedelta(microseconds=7))
    assert worker.run_once(worker_id="worker-a").outcome == "retry_scheduled"
    store.advance(timedelta(microseconds=11))
    assert worker.run_once(worker_id="worker-a").outcome == "succeeded"

    attempts = store.attempts(work_id="work-four-attempts")
    assert [attempt["retry_delay_microseconds"] for attempt in attempts[:3]] == [3, 7, 11]
    assert len(attempts) == 4
    assert attempts[-1]["disposition"] == "succeeded"
    assert random.requests == [5_000_000, 30_000_000, 120_000_000]


def test_worker_reconciles_crash_after_external_delete_without_repeating_delete() -> None:
    maintenance = InMemoryObjectLifecycleMaintenance(lease_duration=timedelta(seconds=1))
    maintenance.enqueue(
        ObjectLifecycleWorkItem(
            work_id="crash-after-delete",
            workspace_id="w1",
            object_key="k1",
            state=LifecycleWorkState.QUEUED,
        )
    )
    external = AlreadyDeletedStore()
    first = maintenance.claim(worker_id="worker-a")
    assert first is not None
    claim = LifecycleClaim("crash-after-delete", "worker-a", 1, first.lease_version)
    generation = maintenance.prepare_delete(claim=claim)
    external.delete(workspace_id="w1", object_key="k1")
    maintenance.advance(timedelta(seconds=2))

    worker = ObjectLifecycleWorker(
        maintenance=maintenance,
        object_store=external,
        retry_policy=ObjectLifecycleRetryPolicyV1(
            random_source=ControlledRandomSource(samples=[], requests=[])
        ),
    )
    result = worker.run_once(worker_id="worker-b")

    assert result.outcome == "succeeded"
    assert external.deletes == 1
    assert maintenance.read(work_id="crash-after-delete").state == LifecycleWorkState.SUCCEEDED
    assert generation != ""


def test_worker_does_not_repeat_delete_when_crash_reconciliation_head_is_indeterminate() -> None:
    maintenance = InMemoryObjectLifecycleMaintenance(lease_duration=timedelta(seconds=1))
    maintenance.enqueue(
        ObjectLifecycleWorkItem(
            work_id="head-failure-reconciliation",
            workspace_id="w1",
            object_key="k1",
            state=LifecycleWorkState.QUEUED,
        )
    )
    first = maintenance.claim(worker_id="worker-a")
    assert first is not None
    claim = LifecycleClaim(
        "head-failure-reconciliation", "worker-a", 1, first.lease_version
    )
    maintenance.prepare_delete(claim=claim)
    maintenance.fence(work_id=claim.work_id)

    external = HeadFailureStore()
    result = ObjectLifecycleWorker(
        maintenance=maintenance,
        object_store=external,
        retry_policy=ObjectLifecycleRetryPolicyV1(
            random_source=ControlledRandomSource(samples=[0], requests=[])
        ),
    ).run_once(worker_id="worker-b", work_id=claim.work_id)

    assert result.outcome == "retry_scheduled"
    assert external.deletes == 0


class AttachBetweenPreparationAndDelete(InMemoryObjectLifecycleMaintenance):
    def revalidate_delete(self, *, claim: LifecycleClaim, delete_generation: str) -> None:
        self.retain(work_id=claim.work_id)
        super().revalidate_delete(claim=claim, delete_generation=delete_generation)


def test_worker_suppresses_delete_when_authoritative_retention_appears_before_effect() -> None:
    maintenance = AttachBetweenPreparationAndDelete()
    maintenance.enqueue(
        ObjectLifecycleWorkItem(
            work_id="attach-race",
            workspace_id="w1",
            object_key="k1",
            state=LifecycleWorkState.QUEUED,
        )
    )
    external = DeletingStore()
    worker = ObjectLifecycleWorker(
        maintenance=maintenance,
        object_store=external,
        retry_policy=ObjectLifecycleRetryPolicyV1(
            random_source=ControlledRandomSource(samples=[], requests=[])
        ),
    )

    result = worker.run_once(worker_id="worker-a")

    assert result.outcome == "suppressed"
    assert external.deletes == 0
    assert maintenance.read(work_id="attach-race").retained
    assert maintenance.read(work_id="attach-race").delete_generation is None


class References:
    def __init__(self, retained: set[str]) -> None:
        self.retained = retained

    def is_authoritatively_retained(self, *, workspace_id: str, object_key: str) -> bool:
        return object_key in self.retained


class Clock:
    def __init__(self, now: datetime) -> None:
        self.value = now

    def now(self) -> datetime:
        return self.value


def test_reconciler_discovers_only_old_unretained_inventory_objects() -> None:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    inventory = SnapshotObjectInventory(
        {"w1": [("old", now - timedelta(days=2)), ("young", now - timedelta(seconds=1))]}
    )
    maintenance = InMemoryObjectLifecycleMaintenance()
    reconciler = ObjectLifecycleReconciler(
        inventory=inventory,
        references=References({"retained"}),
        maintenance=maintenance,
        minimum_age=timedelta(days=1),
        now=Clock(now),
    )

    assert reconciler.reconcile(workspace_id="w1") == 1
    assert maintenance.claim(worker_id="worker-a") is not None


class ReferencesWithInconsistentRecord(References):
    def inconsistent_object_keys(
        self, *, workspace_id: str, observed_object_keys: set[str]
    ) -> tuple[str, ...]:
        del workspace_id, observed_object_keys
        return ("missing-from-inventory",)


def test_reconciler_records_inconsistent_database_object_as_report_only_work() -> None:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    maintenance = InMemoryObjectLifecycleMaintenance()
    reconciler = ObjectLifecycleReconciler(
        inventory=SnapshotObjectInventory({"w1": []}),
        references=ReferencesWithInconsistentRecord(set()),
        maintenance=maintenance,
        minimum_age=timedelta(days=1),
        now=Clock(now),
    )

    assert reconciler.reconcile(workspace_id="w1") == 0
    report = maintenance.read(
        work_id=str(uuid5(NAMESPACE_URL, "inconsistent-record:w1:missing-from-inventory"))
    )
    assert report.artifact_class == "orphan_report"

    result = ObjectLifecycleWorker(
        maintenance=maintenance,
        object_store=DeletingStore(),
        retry_policy=ObjectLifecycleRetryPolicyV1(
            random_source=ControlledRandomSource(samples=[], requests=[])
        ),
    ).run_once(worker_id="worker-a", work_id=report.work_id)

    assert result.outcome == "suppressed"
    assert maintenance.read(work_id=report.work_id).reconciliation_disposition == "reported"


def test_reconciler_can_record_completed_repair_for_report_only_work() -> None:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    maintenance = InMemoryObjectLifecycleMaintenance()
    reconciler = ObjectLifecycleReconciler(
        inventory=SnapshotObjectInventory({"w1": []}),
        references=ReferencesWithInconsistentRecord(set()),
        maintenance=maintenance,
        minimum_age=timedelta(days=1),
        now=Clock(now),
    )

    assert reconciler.reconcile(workspace_id="w1") == 0
    report = maintenance.read(
        work_id=str(uuid5(NAMESPACE_URL, "inconsistent-record:w1:missing-from-inventory"))
    )
    result = ObjectLifecycleWorker(
        maintenance=maintenance,
        object_store=DeletingStore(),
        retry_policy=ObjectLifecycleRetryPolicyV1(
            random_source=ControlledRandomSource(samples=[], requests=[])
        ),
    ).run_once(worker_id="worker-a", work_id=report.work_id)
    assert result.outcome == "suppressed"

    assert maintenance.complete_orphan_reconciliation(
        work_id=report.work_id, disposition="repaired"
    )
    assert not maintenance.complete_orphan_reconciliation(
        work_id=report.work_id, disposition="repaired"
    )
    assert maintenance.read(work_id=report.work_id).reconciliation_disposition == "repaired"
