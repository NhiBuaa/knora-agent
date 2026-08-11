"""Application-level object lifecycle policy primitives."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from secrets import randbelow
from typing import Protocol
from uuid import NAMESPACE_URL, uuid4, uuid5


class LifecycleRandomSource(Protocol):
    def sample(self, upper_bound_microseconds: int) -> int: ...


def _duration_microseconds(value: timedelta) -> int:
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds


def validate_lifecycle_retry_delay(retry_delay: timedelta | None) -> None:
    if retry_delay is not None and (
        not isinstance(retry_delay, timedelta) or retry_delay < timedelta(0)
    ):
        raise ValueError("lifecycle retry delay must be non-negative")


@dataclass(frozen=True, slots=True)
class LifecycleRetryDecision:
    delay_microseconds: int
    window_upper_bound_microseconds: int
    policy_version: str = "object-lifecycle-retry-v1"


class ObjectLifecycleRetryPolicyV1:
    """Choose one caller-supplied full-jitter sample per retry decision."""

    _WINDOWS = {1: 5_000_000, 2: 30_000_000, 3: 120_000_000}

    def __init__(self, *, random_source: LifecycleRandomSource) -> None:
        self._random_source = random_source

    def schedule(self, *, attempt_number: int) -> LifecycleRetryDecision:
        if (
            isinstance(attempt_number, bool)
            or not isinstance(attempt_number, int)
            or attempt_number not in self._WINDOWS
        ):
            raise ValueError(
                "retry scheduling is valid only for attempts one through three"
            )
        upper_bound = self._WINDOWS[attempt_number]
        delay = self._random_source.sample(upper_bound)
        if (
            isinstance(delay, bool)
            or not isinstance(delay, int)
            or not 0 <= delay <= upper_bound
        ):
            raise ValueError("random source returned a sample outside the retry window")
        return LifecycleRetryDecision(
            delay_microseconds=delay,
            window_upper_bound_microseconds=upper_bound,
        )


class SystemLifecycleRandomSource:
    """Process-local source for production full-jitter samples."""

    def sample(self, upper_bound_microseconds: int) -> int:
        if (
            isinstance(upper_bound_microseconds, bool)
            or not isinstance(upper_bound_microseconds, int)
        ):
            raise ValueError("random-source upper bound must be an integer")
        if upper_bound_microseconds < 0:
            raise ValueError("random-source upper bound must be non-negative")
        return randbelow(upper_bound_microseconds + 1)


class LifecycleWorkState(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class LifecycleRetentionPending(PermissionError):
    """The work is valid but its authoritative retention window has not expired."""


FAILED_UPLOAD_DIAGNOSTIC_RETENTION = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class ObjectLifecycleWorkItem:
    work_id: str
    workspace_id: str
    object_key: str
    state: LifecycleWorkState
    attempt_count: int = 0
    worker_id: str | None = None
    lease_version: int = 0
    lease_expires_at: datetime | None = None
    next_attempt_at: datetime | None = None
    delete_generation: str | None = None
    retained: bool = False
    artifact_class: str = "orphan"
    reconciliation_disposition: str | None = None
    lifecycle_generation: str | None = None
    eligible_at: datetime | None = None
    created: bool = True
    claim_operation_id: str | None = None
    discovery_recorded_at: datetime | None = None


def validate_object_lifecycle_work_item(item: ObjectLifecycleWorkItem) -> None:
    """Validate retention metadata before a lifecycle identity becomes durable.

    Failed-upload diagnostic work is the only lifecycle class with a bounded diagnostic
    retention window.  Its classification timestamp and eligibility timestamp must travel
    together through every maintenance adapter so a caller cannot bypass the 24-hour hold by
    enqueueing directly at a lower seam.
    """

    if (
        isinstance(item.attempt_count, bool)
        or not isinstance(item.attempt_count, int)
        or not 0 <= item.attempt_count <= 4
    ):
        raise ValueError("lifecycle attempt count must be between zero and the four-attempt budget")

    if item.artifact_class != "failed_upload_diagnostic":
        return
    if item.discovery_recorded_at is None or item.eligible_at is None:
        raise ValueError(
            "failed-upload diagnostic retention requires durable classification and eligibility"
        )
    if (
        not isinstance(item.discovery_recorded_at, datetime)
        or item.discovery_recorded_at.tzinfo is None
        or item.discovery_recorded_at.utcoffset() is None
        or not isinstance(item.eligible_at, datetime)
        or item.eligible_at.tzinfo is None
        or item.eligible_at.utcoffset() is None
    ):
        raise ValueError(
            "failed-upload diagnostic retention timestamps must be timezone-aware datetimes"
        )
    try:
        minimum_eligible_at = item.discovery_recorded_at + FAILED_UPLOAD_DIAGNOSTIC_RETENTION
        is_valid = item.eligible_at >= minimum_eligible_at
    except TypeError as error:
        raise ValueError(
            "failed-upload diagnostic retention timestamps must be comparable datetimes"
        ) from error
    if not is_valid:
        raise ValueError(
            "failed-upload diagnostic retention eligibility must be at least 24 hours after"
            " classification"
        )


class ObjectInventory(Protocol):
    def objects(self, *, workspace_id: str) -> list[tuple[str, datetime]]: ...


class ObjectReferenceResolver(Protocol):
    def is_authoritatively_retained(self, *, workspace_id: str, object_key: str) -> bool: ...


class InconsistentObjectResolver(Protocol):
    """Optional read seam for database/object-record reconciliation.

    The inventory is the authoritative observation of objects present in the configured
    Workspace.  Implementations may use the same Workspace-scoped lifecycle gateway to report
    database records that are absent from that observation.  This is deliberately a read/report
    seam: it does not grant the reconciler a new attachment or deletion capability.
    """

    def inconsistent_object_keys(
        self, *, workspace_id: str, observed_object_keys: set[str]
    ) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class LifecycleClaim:
    work_id: str
    worker_id: str
    attempt_number: int
    lease_version: int
    claim_operation_id: str | None = None


@dataclass(frozen=True, slots=True)
class LifecycleCompletion:
    state: LifecycleWorkState
    work_id: str
    attempt_number: int


@dataclass(frozen=True, slots=True)
class OriginalSourceDeleteCapability:
    """Fenced capability for the approved Original Source Object deletion path."""

    workspace_id: str
    object_key: str
    document_version_id: str
    generation: str
    already_deleted: bool = False


class LifecycleClock(Protocol):
    def now(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class LifecycleRunResult:
    outcome: str
    work_id: str | None = None
    attempt_number: int | None = None


class ObjectLifecycleMaintenance(Protocol):
    def claim(
        self,
        *,
        worker_id: str,
        operation_id: str | None = None,
        work_id: str | None = None,
    ) -> ObjectLifecycleWorkItem | None: ...

    def prepare_delete(
        self, *, claim: LifecycleClaim, operation_id: str | None = None
    ) -> str: ...

    def revalidate_delete(self, *, claim: LifecycleClaim, delete_generation: str) -> None: ...

    def complete(
        self,
        *,
        claim: LifecycleClaim,
        delete_generation: str,
        operation_id: str | None = None,
    ) -> LifecycleCompletion: ...

    def fail(
        self,
        *,
        claim: LifecycleClaim,
        retry_delay: timedelta | None,
        operation_id: str | None = None,
        retry_policy_version: str | None = None,
        retry_window_upper_bound_microseconds: int | None = None,
    ) -> LifecycleWorkState: ...

    def suppress(
        self, *, claim: LifecycleClaim, operation_id: str | None = None
    ) -> LifecycleCompletion: ...

    def enqueue(self, item: ObjectLifecycleWorkItem) -> ObjectLifecycleWorkItem: ...

    def complete_orphan_reconciliation(self, *, work_id: str, disposition: str) -> bool: ...

    def prepare_original_source_hard_delete(
        self,
        *,
        workspace_id: str,
        object_key: str,
        operation_id: str | None = None,
    ) -> OriginalSourceDeleteCapability: ...

    def revalidate_original_source_hard_delete(
        self, *, capability: OriginalSourceDeleteCapability
    ) -> None: ...

    def complete_original_source_hard_delete(
        self,
        *,
        capability: OriginalSourceDeleteCapability,
        operation_id: str | None = None,
    ) -> bool: ...


class InMemoryObjectLifecycleMaintenance:
    """Deterministic coordinator adapter used by policy and seam tests."""

    def __init__(self, *, lease_duration: timedelta = timedelta(minutes=2)) -> None:
        self._lease_duration = lease_duration
        self._now = datetime.now().astimezone()
        self._work: dict[str, ObjectLifecycleWorkItem] = {}
        self._attempts: dict[str, list[dict[str, object]]] = {}
        self._original_source_capabilities: dict[
            tuple[str, str], OriginalSourceDeleteCapability
        ] = {}
        self._retained_originals: set[tuple[str, str]] = set()
        self._deleted_originals: set[tuple[str, str]] = set()

    def enqueue(self, item: ObjectLifecycleWorkItem) -> ObjectLifecycleWorkItem:
        validate_object_lifecycle_work_item(item)
        existing = self._work.get(item.work_id)
        if existing is not None:
            return replace(existing, created=False)
        identity = (
            item.workspace_id,
            item.object_key,
            item.artifact_class,
            item.lifecycle_generation or item.work_id,
        )
        for existing in self._work.values():
            existing_identity = (
                existing.workspace_id,
                existing.object_key,
                existing.artifact_class,
                existing.lifecycle_generation or existing.work_id,
            )
            if existing_identity == identity:
                return replace(existing, created=False)
        self._work[item.work_id] = item
        return item

    def advance(self, delta: timedelta) -> None:
        self._now += delta

    def claim(
        self,
        *,
        worker_id: str,
        operation_id: str | None = None,
        work_id: str | None = None,
    ) -> ObjectLifecycleWorkItem | None:
        if operation_id is not None:
            for replay_work_id, attempts in self._attempts.items():
                replay_attempt = next(
                    (
                        attempt
                        for attempt in attempts
                        if attempt.get("operation_id") == operation_id
                    ),
                    None,
                )
                if replay_attempt is None:
                    continue
                if (
                    replay_attempt.get("worker_id") != worker_id
                    or (work_id is not None and replay_work_id != work_id)
                ):
                    raise PermissionError("lifecycle claim operation belongs to another owner")
                return self._work[replay_work_id]
        for candidate_work_id, item in tuple(self._work.items()):
            if (
                item.state == LifecycleWorkState.PROCESSING
                and item.lease_expires_at is not None
                and item.lease_expires_at <= self._now
            ):
                state = (
                    LifecycleWorkState.RETRY_SCHEDULED
                    if item.attempt_count < 4
                    else LifecycleWorkState.FAILED
                )
                self._close_attempt(candidate_work_id, item.attempt_count, "lease_expired")
                self._work[candidate_work_id] = replace(
                    item,
                    state=state,
                    worker_id=None,
                    lease_expires_at=None,
                    next_attempt_at=(
                        self._now if state == LifecycleWorkState.RETRY_SCHEDULED else None
                    ),
                )
        for item in self._work.values():
            if work_id is not None and item.work_id != work_id:
                continue
            due = item.state == LifecycleWorkState.QUEUED or (
                item.state == LifecycleWorkState.RETRY_SCHEDULED
                and item.next_attempt_at is not None
                and item.next_attempt_at <= self._now
            )
            if item.eligible_at is not None and item.eligible_at > self._now:
                continue
            if not due or item.attempt_count >= 4:
                continue
            attempt = item.attempt_count + 1
            claimed = replace(
                item,
                state=LifecycleWorkState.PROCESSING,
                attempt_count=attempt,
                worker_id=worker_id,
                lease_version=item.lease_version + 1,
                lease_expires_at=self._now + self._lease_duration,
                claim_operation_id=operation_id,
            )
            self._work[item.work_id] = claimed
            self._attempts.setdefault(item.work_id, []).append(
                {
                    "attempt_number": attempt,
                    "worker_id": worker_id,
                    "lease_version": claimed.lease_version,
                    "operation_id": operation_id,
                    "closed": False,
                }
            )
            return claimed
        return None

    def prepare_delete(
        self, *, claim: LifecycleClaim, operation_id: str | None = None
    ) -> str:
        item = self._current_claim(claim)
        if item.eligible_at is not None and item.eligible_at > self._now:
            raise LifecycleRetentionPending("lifecycle retention window has not expired")
        if item.retained or item.artifact_class == "orphan_report":
            raise PermissionError("retained object suppresses deletion")
        self._assert_no_other_lifecycle_retention(item)
        for attempt in self._attempts.get(item.work_id, ()):
            if attempt["attempt_number"] != claim.attempt_number:
                continue
            existing_generation = attempt.get("deletion_generation")
            if existing_generation is not None:
                existing_operation = attempt.get("prepare_operation_id")
                if existing_operation not in {None, operation_id}:
                    raise PermissionError("lifecycle preparation operation is already bound")
                return str(existing_generation)
        generation = str(uuid4())
        self._work[item.work_id] = replace(item, delete_generation=generation)
        for attempt in self._attempts.get(item.work_id, ()):
            if attempt["attempt_number"] == claim.attempt_number:
                attempt["prepare_operation_id"] = operation_id
                attempt["deletion_generation"] = generation
        return generation

    def complete(
        self,
        *,
        claim: LifecycleClaim,
        delete_generation: str,
        operation_id: str | None = None,
    ) -> LifecycleCompletion:
        item = self._work.get(claim.work_id)
        if (
            item is not None
            and item.state == LifecycleWorkState.SUCCEEDED
            and item.delete_generation == delete_generation
        ):
            attempt = self._attempt_record(item.work_id, claim.attempt_number)
            if attempt.get("completion_operation_id") not in {None, operation_id}:
                raise PermissionError("lifecycle completion operation is already bound")
            return LifecycleCompletion(
                LifecycleWorkState.SUCCEEDED, item.work_id, claim.attempt_number
            )
        item = self._current_claim(claim)
        if item.delete_generation != delete_generation:
            raise PermissionError("stale delete generation")
        attempt = self._attempt_record(item.work_id, claim.attempt_number)
        if attempt.get("deletion_generation") != delete_generation:
            raise PermissionError("stale delete generation")
        if item.retained or item.artifact_class == "orphan_report":
            raise PermissionError("retained object suppresses deletion")
        self._work[item.work_id] = replace(
            item,
            state=LifecycleWorkState.SUCCEEDED,
            worker_id=None,
            lease_expires_at=None,
            reconciliation_disposition=(
                "deleted" if item.artifact_class == "orphan" else item.reconciliation_disposition
            ),
        )
        self._close_attempt(item.work_id, claim.attempt_number, "succeeded")
        self._set_attempt_operation(
            item.work_id, claim.attempt_number, "completion_operation_id", operation_id
        )
        return LifecycleCompletion(LifecycleWorkState.SUCCEEDED, item.work_id, claim.attempt_number)

    def revalidate_delete(self, *, claim: LifecycleClaim, delete_generation: str) -> None:
        item = self._current_claim(claim)
        if item.delete_generation != delete_generation:
            raise PermissionError("stale delete generation")
        attempt = self._attempt_record(item.work_id, claim.attempt_number)
        if attempt.get("deletion_generation") != delete_generation:
            raise PermissionError("stale delete generation")
        if item.eligible_at is not None and item.eligible_at > self._now:
            raise LifecycleRetentionPending("lifecycle retention window has not expired")
        if item.retained or item.artifact_class == "orphan_report":
            raise PermissionError("retained object suppresses deletion")
        self._assert_no_other_lifecycle_retention(item)

    def fail(
        self,
        *,
        claim: LifecycleClaim,
        retry_delay: timedelta | None,
        operation_id: str | None = None,
        retry_policy_version: str | None = None,
        retry_window_upper_bound_microseconds: int | None = None,
    ) -> LifecycleWorkState:
        validate_lifecycle_retry_delay(retry_delay)
        item = self._work.get(claim.work_id)
        if item is None:
            raise PermissionError("lifecycle claim is fenced")
        attempt_record = self._attempt_record(item.work_id, claim.attempt_number)
        if attempt_record.get("closed"):
            if attempt_record.get("disposition") != LifecycleWorkState.FAILED.value:
                raise PermissionError("lifecycle failure is fenced")
            if attempt_record.get("failure_operation_id") not in {None, operation_id}:
                raise PermissionError("lifecycle failure operation is already bound")
            requested_retry_delay = (
                None
                if retry_delay is None or claim.attempt_number >= 4
                else _duration_microseconds(retry_delay)
            )
            if (
                attempt_record.get("retry_delay_microseconds") != requested_retry_delay
                or attempt_record.get("retry_policy_version") != retry_policy_version
                or attempt_record.get("retry_window_upper_bound_microseconds")
                != retry_window_upper_bound_microseconds
            ):
                raise PermissionError("lifecycle failure operation request does not match replay")
            return item.state
        item = self._current_claim(claim)
        if retry_delay is not None and claim.attempt_number < 4:
            state = LifecycleWorkState.RETRY_SCHEDULED
        else:
            state = LifecycleWorkState.FAILED
        self._work[item.work_id] = replace(
            item,
            state=state,
            worker_id=None,
            lease_expires_at=None,
            next_attempt_at=(self._now + retry_delay if retry_delay is not None else None),
        )
        self._close_attempt(item.work_id, claim.attempt_number, LifecycleWorkState.FAILED.value)
        if retry_delay is not None:
            for attempt in self._attempts.get(item.work_id, ()):
                if attempt["attempt_number"] == claim.attempt_number:
                    attempt["retry_delay_microseconds"] = _duration_microseconds(retry_delay)
                    break
        attempt_record["failure_operation_id"] = operation_id
        attempt_record["retry_policy_version"] = retry_policy_version
        attempt_record["retry_window_upper_bound_microseconds"] = (
            retry_window_upper_bound_microseconds
        )
        return state

    def suppress(
        self, *, claim: LifecycleClaim, operation_id: str | None = None
    ) -> LifecycleCompletion:
        item = self._work.get(claim.work_id)
        if item is not None and item.state == LifecycleWorkState.SUCCEEDED:
            attempt = self._attempt_record(item.work_id, claim.attempt_number)
            if not attempt.get("closed") or attempt.get("disposition") != "suppressed":
                raise PermissionError("lifecycle suppression is fenced")
            if attempt.get("completion_operation_id") not in {None, operation_id}:
                raise PermissionError("lifecycle suppression operation is already bound")
            return LifecycleCompletion(
                LifecycleWorkState.SUCCEEDED, item.work_id, claim.attempt_number
            )
        item = self._current_claim(claim)
        self._work[item.work_id] = replace(
            item,
            state=LifecycleWorkState.SUCCEEDED,
            worker_id=None,
            lease_expires_at=None,
            delete_generation=None,
            reconciliation_disposition=(
                "delete_suppressed"
                if item.artifact_class == "orphan"
                else "reported"
                if item.artifact_class == "orphan_report"
                else item.reconciliation_disposition
            ),
        )
        self._close_attempt(item.work_id, claim.attempt_number, "suppressed")
        self._set_attempt_operation(
            item.work_id, claim.attempt_number, "completion_operation_id", operation_id
        )
        return LifecycleCompletion(LifecycleWorkState.SUCCEEDED, item.work_id, claim.attempt_number)

    def fence(self, *, work_id: str) -> None:
        item = self._work[work_id]
        self._work[work_id] = replace(item, lease_expires_at=self._now - timedelta(microseconds=1))

    def retain(self, *, work_id: str) -> None:
        item = self._work[work_id]
        self._work[work_id] = replace(item, retained=True)

    def read(self, *, work_id: str) -> ObjectLifecycleWorkItem:
        return self._work[work_id]

    def attempts(self, *, work_id: str) -> tuple[dict[str, object], ...]:
        return tuple(dict(attempt) for attempt in self._attempts.get(work_id, ()))

    def complete_orphan_reconciliation(self, *, work_id: str, disposition: str) -> bool:
        if disposition not in {"repaired", "deleted"}:
            raise ValueError("unsupported orphan reconciliation disposition")
        item = self._work.get(work_id)
        if item is None or item.artifact_class not in {"orphan", "orphan_report"}:
            raise ValueError("orphan lifecycle work does not exist")
        if item.artifact_class == "orphan_report" and disposition != "repaired":
            raise ValueError("inconsistent database record cannot be deleted by orphan cleanup")
        if item.reconciliation_disposition is not None:
            if item.reconciliation_disposition == disposition:
                return False
            if not (
                item.artifact_class == "orphan_report"
                and item.reconciliation_disposition == "reported"
                and disposition == "repaired"
            ):
                raise ValueError("orphan corrective disposition is already bound")
        if item.state != LifecycleWorkState.SUCCEEDED:
            raise ValueError("orphan corrective disposition is not complete")
        self._work[work_id] = replace(item, reconciliation_disposition=disposition)
        return True

    def prepare_original_source_hard_delete(
        self,
        *,
        workspace_id: str,
        object_key: str,
        operation_id: str | None = None,
    ) -> OriginalSourceDeleteCapability:
        del operation_id
        identity = (workspace_id, object_key)
        if identity in self._retained_originals:
            raise PermissionError("retained Original Source Object suppresses deletion")
        if identity in self._deleted_originals:
            return OriginalSourceDeleteCapability(
                workspace_id=workspace_id,
                object_key=object_key,
                document_version_id=f"version:{object_key}",
                generation=str(uuid4()),
                already_deleted=True,
            )
        capability = self._original_source_capabilities.get(identity)
        if capability is not None:
            return capability
        capability = OriginalSourceDeleteCapability(
            workspace_id=workspace_id,
            object_key=object_key,
            document_version_id=f"version:{object_key}",
            generation=str(uuid4()),
        )
        self._original_source_capabilities[identity] = capability
        return capability

    def revalidate_original_source_hard_delete(
        self, *, capability: OriginalSourceDeleteCapability
    ) -> None:
        """Fence a prepared hard-delete capability immediately before the effect."""

        identity = (capability.workspace_id, capability.object_key)
        if self._original_source_capabilities.get(identity) != capability:
            raise PermissionError("Original Source Object delete capability is fenced")
        if identity in self._retained_originals:
            raise PermissionError("retained Original Source Object suppresses deletion")

    def complete_original_source_hard_delete(
        self,
        *,
        capability: OriginalSourceDeleteCapability,
        operation_id: str | None = None,
    ) -> bool:
        del operation_id
        identity = (capability.workspace_id, capability.object_key)
        current = self._original_source_capabilities.get(identity)
        if current != capability:
            raise PermissionError("Original Source Object delete capability is fenced")
        if (capability.workspace_id, capability.object_key) in self._retained_originals:
            raise PermissionError("retained Original Source Object suppresses deletion")
        self._original_source_capabilities.pop(identity, None)
        self._deleted_originals.add(identity)
        return True

    def retain_original_source(self, *, workspace_id: str, object_key: str) -> None:
        self._retained_originals.add((workspace_id, object_key))

    def _close_attempt(self, work_id: str, attempt_number: int, disposition: str) -> None:
        for attempt in self._attempts.get(work_id, ()):
            if attempt["attempt_number"] == attempt_number and not attempt["closed"]:
                attempt["closed"] = True
                attempt["disposition"] = disposition
                return

    def _attempt_record(self, work_id: str, attempt_number: int) -> dict[str, object]:
        for attempt in self._attempts.get(work_id, ()):
            if attempt["attempt_number"] == attempt_number:
                return attempt
        raise ValueError("lifecycle attempt is missing")

    def _set_attempt_operation(
        self, work_id: str, attempt_number: int, field: str, operation_id: str | None
    ) -> None:
        attempt = self._attempt_record(work_id, attempt_number)
        current = attempt.get(field)
        if current is not None and current != operation_id:
            raise PermissionError("lifecycle operation is already bound")
        attempt[field] = operation_id

    def _current_claim(self, claim: LifecycleClaim) -> ObjectLifecycleWorkItem:
        item = self._work.get(claim.work_id)
        if (
            item is None
            or item.state != LifecycleWorkState.PROCESSING
            or item.worker_id != claim.worker_id
            or item.attempt_count != claim.attempt_number
            or item.lease_version != claim.lease_version
            or item.lease_expires_at is None
            or item.lease_expires_at <= self._now
        ):
            raise PermissionError("lifecycle claim is fenced")
        return item

    def _assert_no_other_lifecycle_retention(self, item: ObjectLifecycleWorkItem) -> None:
        for other in self._work.values():
            if (
                other.work_id == item.work_id
                or other.workspace_id != item.workspace_id
                or other.object_key != item.object_key
                or other.artifact_class != "failed_upload_diagnostic"
            ):
                continue
            if other.eligible_at is None or other.eligible_at > self._now:
                raise LifecycleRetentionPending(
                    "another failed-upload diagnostic retention window has not expired"
                )


class SnapshotObjectInventory:
    """Inventory adapter for an externally supplied, Workspace-scoped object snapshot."""

    def __init__(self, objects_by_workspace: dict[str, list[tuple[str, datetime]]]) -> None:
        self._objects = objects_by_workspace

    def objects(self, *, workspace_id: str) -> list[tuple[str, datetime]]:
        return list(self._objects.get(workspace_id, ()))


class ObjectLifecycleReconciler:
    def __init__(
        self,
        *,
        inventory: ObjectInventory,
        references: ObjectReferenceResolver,
        maintenance: ObjectLifecycleMaintenance,
        minimum_age: timedelta,
        now: LifecycleClock,
    ) -> None:
        if minimum_age < timedelta(0):
            raise ValueError("orphan minimum age must be non-negative")
        self._inventory = inventory
        self._references = references
        self._maintenance = maintenance
        self._minimum_age = minimum_age
        self._now = now

    def reconcile(self, *, workspace_id: str) -> int:
        inventory = self._inventory.objects(workspace_id=workspace_id)
        observed_object_keys = {object_key for object_key, _ in inventory}
        discovered = 0
        for object_key, created_at in inventory:
            if self._now.now() - created_at < self._minimum_age:
                continue
            if self._references.is_authoritatively_retained(
                workspace_id=workspace_id, object_key=object_key
            ):
                continue
            lifecycle_id = str(uuid5(NAMESPACE_URL, f"orphan:{workspace_id}:{object_key}"))
            queued = self._maintenance.enqueue(
                ObjectLifecycleWorkItem(
                    work_id=lifecycle_id,
                    workspace_id=workspace_id,
                    object_key=object_key,
                    state=LifecycleWorkState.QUEUED,
                    lifecycle_generation=lifecycle_id,
                    eligible_at=created_at + self._minimum_age,
                    discovery_recorded_at=self._now.now(),
                )
            )
            if queued.created:
                discovered += 1

        # Database records for objects absent from the Workspace inventory are inconsistent
        # records, not unreferenced object candidates.  Record them through the existing
        # lifecycle work gateway as report-only work so the worker's normal claim/fencing and
        # idempotency rules apply, while the retained record suppresses any destructive effect.
        inconsistent = getattr(self._references, "inconsistent_object_keys", None)
        if inconsistent is not None:
            for object_key in inconsistent(
                workspace_id=workspace_id, observed_object_keys=observed_object_keys
            ):
                if object_key in observed_object_keys:
                    continue
                lifecycle_id = str(
                    uuid5(NAMESPACE_URL, f"inconsistent-record:{workspace_id}:{object_key}")
                )
                self._maintenance.enqueue(
                    ObjectLifecycleWorkItem(
                        work_id=lifecycle_id,
                        workspace_id=workspace_id,
                        object_key=object_key,
                        state=LifecycleWorkState.QUEUED,
                        artifact_class="orphan_report",
                        lifecycle_generation=lifecycle_id,
                        eligible_at=self._now.now(),
                    )
                )
        return discovered


class ObjectLifecycleWorker:
    def __init__(
        self,
        *,
        maintenance: ObjectLifecycleMaintenance,
        object_store: "ObjectStoreLike",
        retry_policy: ObjectLifecycleRetryPolicyV1,
    ) -> None:
        self._maintenance = maintenance
        self._object_store = object_store
        self._retry_policy = retry_policy

    def run_once(
        self,
        *,
        worker_id: str,
        operation_id: str | None = None,
        work_id: str | None = None,
    ) -> LifecycleRunResult:
        root_operation_id = operation_id or str(uuid4())
        try:
            item = self._maintenance.claim(
                worker_id=worker_id, operation_id=root_operation_id, work_id=work_id
            )
        except PermissionError:
            return LifecycleRunResult("fenced", work_id)
        if item is None:
            return LifecycleRunResult("no_work")
        if (
            item.claim_operation_id == root_operation_id
            and item.state != LifecycleWorkState.PROCESSING
        ):
            return LifecycleRunResult(item.state.value, item.work_id, item.attempt_count)
        claim = LifecycleClaim(
            work_id=item.work_id,
            worker_id=worker_id,
            attempt_number=item.attempt_count,
            lease_version=item.lease_version,
            claim_operation_id=root_operation_id,
        )
        prepare_operation_id = str(uuid5(NAMESPACE_URL, f"{root_operation_id}:prepare"))
        completion_operation_id = str(uuid5(NAMESPACE_URL, f"{root_operation_id}:complete"))
        failure_operation_id = str(uuid5(NAMESPACE_URL, f"{root_operation_id}:failure"))
        head = getattr(self._object_store, "head", None)
        if item.delete_generation is not None and head is not None:
            try:
                head(workspace_id=item.workspace_id, object_key=item.object_key)
            except Exception as error:
                if getattr(error, "code", None) == "OBJECT_NOT_FOUND":
                    try:
                        generation = self._maintenance.prepare_delete(
                            claim=claim, operation_id=prepare_operation_id
                        )
                    except LifecycleRetentionPending:
                        return LifecycleRunResult(
                            "not_eligible", item.work_id, claim.attempt_number
                        )
                    except PermissionError:
                        return self._suppress_or_fenced(
                            claim=claim,
                            work_id=item.work_id,
                            operation_id=completion_operation_id,
                        )
                    try:
                        completion = self._maintenance.complete(
                            claim=claim,
                            delete_generation=generation,
                            operation_id=completion_operation_id,
                        )
                    except PermissionError:
                        return self._suppress_or_fenced(
                            claim=claim,
                            work_id=item.work_id,
                            operation_id=completion_operation_id,
                        )
                    return LifecycleRunResult(
                        "succeeded", completion.work_id, completion.attempt_number
                    )
                # A pre-existing delete generation is crash-reconciliation state.  An
                # indeterminate `head` read must not fall through to another destructive delete.
                return self._record_cleanup_failure(
                    claim=claim,
                    work_id=item.work_id,
                    failure_operation_id=failure_operation_id,
                )
        try:
            generation = self._maintenance.prepare_delete(
                claim=claim, operation_id=prepare_operation_id
            )
        except LifecycleRetentionPending:
            return LifecycleRunResult("not_eligible", item.work_id, claim.attempt_number)
        except PermissionError:
            return self._suppress_or_fenced(
                claim=claim,
                work_id=item.work_id,
                operation_id=completion_operation_id,
            )
        try:
            self._maintenance.revalidate_delete(claim=claim, delete_generation=generation)
        except LifecycleRetentionPending:
            return LifecycleRunResult("not_eligible", item.work_id, claim.attempt_number)
        except PermissionError:
            return self._suppress_or_fenced(
                claim=claim,
                work_id=item.work_id,
                operation_id=completion_operation_id,
            )
        try:
            self._object_store.delete(workspace_id=item.workspace_id, object_key=item.object_key)
        except Exception:
            return self._record_cleanup_failure(
                claim=claim,
                work_id=item.work_id,
                failure_operation_id=failure_operation_id,
            )
        try:
            completion = self._maintenance.complete(
                claim=claim,
                delete_generation=generation,
                operation_id=completion_operation_id,
            )
        except PermissionError:
            return self._suppress_or_fenced(
                claim=claim,
                work_id=item.work_id,
                operation_id=completion_operation_id,
            )
        return LifecycleRunResult("succeeded", completion.work_id, completion.attempt_number)

    def hard_delete_original_source(
        self,
        *,
        workspace_id: str,
        object_key: str,
        operation_id: str | None = None,
    ) -> bool:
        """Execute the approved hard-delete path through the lifecycle gateway."""

        capability = self._maintenance.prepare_original_source_hard_delete(
            workspace_id=workspace_id,
            object_key=object_key,
            operation_id=operation_id,
        )
        if capability.already_deleted:
            return True
        self._maintenance.revalidate_original_source_hard_delete(capability=capability)
        self._object_store.delete(workspace_id=workspace_id, object_key=object_key)
        return self._maintenance.complete_original_source_hard_delete(
            capability=capability,
            operation_id=operation_id,
        )

    def _record_cleanup_failure(
        self, *, claim: LifecycleClaim, work_id: str, failure_operation_id: str
    ) -> LifecycleRunResult:
        retry_delay = None
        retry_policy_version = None
        retry_window_upper_bound_microseconds = None
        if claim.attempt_number < 4:
            decision = self._retry_policy.schedule(attempt_number=claim.attempt_number)
            retry_delay = timedelta(microseconds=decision.delay_microseconds)
            retry_policy_version = decision.policy_version
            retry_window_upper_bound_microseconds = decision.window_upper_bound_microseconds
        try:
            state = self._maintenance.fail(
                claim=claim,
                retry_delay=retry_delay,
                operation_id=failure_operation_id,
                retry_policy_version=retry_policy_version,
                retry_window_upper_bound_microseconds=retry_window_upper_bound_microseconds,
            )
        except PermissionError:
            return LifecycleRunResult("fenced", work_id, claim.attempt_number)
        return LifecycleRunResult(state.value, work_id, claim.attempt_number)

    def _suppress_or_fenced(
        self, *, claim: LifecycleClaim, work_id: str, operation_id: str
    ) -> LifecycleRunResult:
        try:
            completion = self._maintenance.suppress(claim=claim, operation_id=operation_id)
        except PermissionError:
            return LifecycleRunResult("fenced", work_id, claim.attempt_number)
        return LifecycleRunResult("suppressed", completion.work_id, completion.attempt_number)


class ObjectStoreLike(Protocol):
    def delete(self, *, workspace_id: str, object_key: str) -> None: ...

    def head(self, *, workspace_id: str, object_key: str) -> object: ...
