from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import pytest

from knora.ingestion.job_processing import (
    AttemptCompletion,
    AttemptRef,
    AttemptRuntime,
    AttemptSupervisor,
    AttemptTimedOut,
    AttemptTimingV1,
    Cancellation,
    CanonicalFailureV1,
    ClaimedAttempt,
    ClaimOperationId,
    CoordinationOutcomeIndeterminate,
    ExpiredAttemptObservation,
    FailedTerminal,
    FailureCauseV1,
    Fenced,
    FencingToken,
    FinalizationApplied,
    HandlerCompleted,
    HandlerFailureKindV1,
    HeartbeatApplied,
    HeartbeatOperationId,
    IngestionWork,
    LeaseLost,
    ProcessIngestionJob,
    RecoveryFailedExhausted,
    RecoveryResult,
    RecoveryRetryScheduled,
    RetryExhausted,
    RetryPolicyV1,
    RetryScheduleApplied,
    RetryScheduled,
    RetryScheduleResult,
    RunnerCapacityUnavailable,
    ScheduleRetry,
    StaleObservation,
    SupervisorLeaseLost,
    TransitionOperationId,
    WorkFailed,
)


@dataclass
class RecordingStore:
    claim: ClaimedAttempt
    claims: list[tuple[ClaimOperationId, str, AttemptTimingV1]] = field(default_factory=list)
    finalizations: list[tuple[TransitionOperationId, ClaimedAttempt, CanonicalFailureV1]] = (
        field(default_factory=list)
    )
    retry_schedules: list[
        tuple[TransitionOperationId, ClaimedAttempt, CanonicalFailureV1, ScheduleRetry]
    ] = field(default_factory=list)
    terminal_decisions: list[object] = field(default_factory=list)
    retry_schedule_result: RetryScheduleResult | None = None
    heartbeats: list[object] = field(default_factory=list)
    heartbeat_result: object | None = None
    heartbeat_callback: Callable[[], None] | None = None

    expired_observation: ExpiredAttemptObservation | None = None
    recovery_result: RecoveryResult | None = None
    recoveries: list[
        tuple[TransitionOperationId, ExpiredAttemptObservation, CanonicalFailureV1, object]
    ] = field(default_factory=list)

    def heartbeat(self, *, operation_id, token, lease_duration):
        self.heartbeats.append((operation_id, token, lease_duration))
        if self.heartbeat_callback is not None:
            self.heartbeat_callback()
        if isinstance(self.heartbeat_result, BaseException):
            raise self.heartbeat_result
        if self.heartbeat_result is not None:
            return self.heartbeat_result
        return HeartbeatApplied(lease_expires_at=datetime(2026, 8, 9, tzinfo=UTC))

    def claim_next_attempt(
        self,
        *,
        operation_id: ClaimOperationId,
        worker_id: str,
        timing: AttemptTimingV1,
    ) -> ClaimedAttempt:
        self.claims.append((operation_id, worker_id, timing))
        return self.claim

    def finalize_terminal_failure(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision=None,
    ) -> FinalizationApplied:
        self.finalizations.append((operation_id, claim, failure))
        self.terminal_decisions.append(decision)
        return FinalizationApplied(
            attempt=AttemptRef(
                job_id=claim.token.job_id,
                attempt_number=claim.token.attempt_number,
            )
        )

    def schedule_retry(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry,
    ) -> RetryScheduleApplied:
        self.retry_schedules.append((operation_id, claim, failure, decision))
        if self.retry_schedule_result is not None:
            return self.retry_schedule_result
        return RetryScheduleApplied(
            attempt=AttemptRef(job_id=claim.token.job_id, attempt_number=claim.attempt_count),
            next_attempt_at=claim.attempt_started_at,
        )

    def observe_expired_attempt(self) -> ExpiredAttemptObservation | None:
        return self.expired_observation

    def apply_expired_recovery(
        self,
        *,
        operation_id: TransitionOperationId,
        observation: ExpiredAttemptObservation,
        failure: CanonicalFailureV1,
        decision: object,
    ) -> RecoveryRetryScheduled:
        self.recoveries.append((operation_id, observation, failure, decision))
        if self.recovery_result is not None:
            return self.recovery_result
        return RecoveryRetryScheduled(
            attempt=AttemptRef(
                job_id=observation.job_id,
                attempt_number=observation.attempt_number,
            ),
            next_attempt_at=observation.lease_expires_at,
        )


@dataclass
class FailingHandler:
    received: list[IngestionWork] = field(default_factory=list)

    def execute(self, work: IngestionWork, cancellation) -> WorkFailed:
        self.received.append(work)
        return WorkFailed(
            failure_kind=HandlerFailureKindV1.INVALID_INPUT,
            safe_code="invalid_input",
        )


@dataclass
class RetryableFailingHandler:
    def execute(self, work: IngestionWork, cancellation) -> WorkFailed:
        return WorkFailed(
            failure_kind=HandlerFailureKindV1.PROVIDER_TRANSIENT,
            safe_code="provider_transient",
        )


@dataclass
class FixedRandom:
    delay_microseconds: int

    def next_int_inclusive(self, upper_bound_microseconds: int) -> int:
        assert upper_bound_microseconds == 5_000_000
        return self.delay_microseconds


class NoRandom:
    def next_int_inclusive(self, upper_bound_microseconds: int) -> int:
        raise AssertionError(f"unexpected jitter sample for {upper_bound_microseconds}")


class NoCapacityRunner:
    def try_reserve(self):
        return None


class FixedMonotonicClock:
    value: float = 0.0

    def now(self) -> float:
        return self.value


class NoopScheduler:
    def wait_until(self, attempt, deadline: float) -> None:
        raise AssertionError("runtime construction must not schedule work")


@dataclass
class CompletedAttempt:
    completion_value: AttemptCompletion | None = None

    def completion(self):
        return self.completion_value

    def wait_until(self, deadline: float) -> None:
        return None

    def detach(self) -> None:
        raise AssertionError("completed attempt must not detach")


@dataclass
class PendingAttempt:
    detached: bool = False

    def completion(self):
        return None

    def wait_until(self, deadline: float) -> None:
        return None

    def detach(self) -> None:
        self.detached = True


@dataclass
class AdvancingScheduler:
    clock: FixedMonotonicClock
    attempt: CompletedAttempt

    def wait_until(self, attempt, deadline: float) -> None:
        self.clock.value = deadline
        self.attempt.completion_value = AttemptCompletion(
            completed_at=deadline + 0.1,
            result=WorkFailed(HandlerFailureKindV1.INVALID_INPUT, "invalid_input"),
        )


@dataclass
class ClockScheduler:
    clock: FixedMonotonicClock

    def wait_until(self, attempt, deadline: float) -> None:
        self.clock.value = deadline


@dataclass
class RecordingPermit:
    released: bool = False

    def release(self) -> None:
        self.released = True

    def start(self, handler, work, cancellation, monotonic_clock):
        return CompletedAttempt(
            AttemptCompletion(monotonic_clock.now(), handler.execute(work, cancellation))
        )


@dataclass
class AvailableRunner:
    permits: list[RecordingPermit] = field(default_factory=list)

    def try_reserve(self) -> RecordingPermit:
        permit = RecordingPermit()
        self.permits.append(permit)
        return permit


class StartFailPermit(RecordingPermit):
    def start(self, handler, work, cancellation, monotonic_clock):
        raise RuntimeError("runner start failed")


class StartFailRunner:
    def try_reserve(self):
        return StartFailPermit()


class PendingPermit(RecordingPermit):
    def start(self, handler, work, cancellation, monotonic_clock):
        return PendingAttempt()


@dataclass
class PendingRunner:
    permit: PendingPermit = field(default_factory=PendingPermit)

    def try_reserve(self):
        return self.permit


def test_attempt_runtime_binds_one_runner_clock_and_scheduler() -> None:
    runner = AvailableRunner()
    clock = FixedMonotonicClock()
    scheduler = NoopScheduler()

    runtime = AttemptRuntime(
        runner=runner,
        monotonic_clock=clock,
        scheduler=scheduler,
    )

    assert runtime.runner is runner
    assert runtime.monotonic_clock is clock
    assert runtime.scheduler is scheduler


def test_supervisor_treats_completion_at_the_deadline_as_timeout() -> None:
    supervisor = AttemptSupervisor(
        AttemptRuntime(
            runner=AvailableRunner(),
            monotonic_clock=FixedMonotonicClock(),
            scheduler=NoopScheduler(),
        ),
        RecordingStore(claimed_attempt()),
        FixedOperationIds(),
        AttemptTimingV1.standard(),
    )

    assert supervisor.resolve_completion(completed_at=14.99, deadline_at=15.0) is None
    assert supervisor.resolve_completion(completed_at=15.0, deadline_at=15.0) == AttemptTimedOut()


def test_supervisor_gives_fencing_precedence_over_completion() -> None:
    supervisor = AttemptSupervisor(
        AttemptRuntime(AvailableRunner(), FixedMonotonicClock(), NoopScheduler()),
        RecordingStore(claimed_attempt()),
        FixedOperationIds(),
        AttemptTimingV1.standard(),
    )

    assert supervisor.resolve_heartbeat(Fenced()) == SupervisorLeaseLost()


def test_supervisor_heartbeats_before_accepting_a_later_completion() -> None:
    clock = FixedMonotonicClock()
    attempt = CompletedAttempt()
    store = RecordingStore(claimed_attempt())
    supervisor = AttemptSupervisor(
        AttemptRuntime(AvailableRunner(), clock, AdvancingScheduler(clock, attempt)),
        store,
        FixedOperationIds(),
        AttemptTimingV1.standard(),
    )

    result = supervisor.supervise(
        claim=claimed_attempt(), attempt=attempt, cancellation=Cancellation()
    )

    assert isinstance(result, HandlerCompleted)
    assert len(store.heartbeats) == 1


def test_supervisor_accepts_completion_only_after_heartbeat_readback_returns() -> None:
    clock = FixedMonotonicClock()
    attempt = CompletedAttempt()

    def complete_during_heartbeat() -> None:
        attempt.completion_value = AttemptCompletion(
            completed_at=clock.now(),
            result=WorkFailed(HandlerFailureKindV1.INVALID_INPUT, "invalid_input"),
        )

    store = RecordingStore(claimed_attempt(), heartbeat_callback=complete_during_heartbeat)
    supervisor = AttemptSupervisor(
        AttemptRuntime(AvailableRunner(), clock, ClockScheduler(clock)),
        store,
        FixedOperationIds(),
        AttemptTimingV1.standard(),
    )

    result = supervisor.supervise(
        claim=claimed_attempt(), attempt=attempt, cancellation=Cancellation()
    )

    assert isinstance(result, HandlerCompleted)
    assert len(store.heartbeats) == 1


def test_supervisor_timeout_cancels_and_detaches_without_waiting_for_exit() -> None:
    clock = FixedMonotonicClock()
    attempt = PendingAttempt()
    cancellation = Cancellation()
    supervisor = AttemptSupervisor(
        AttemptRuntime(AvailableRunner(), clock, ClockScheduler(clock)),
        RecordingStore(claimed_attempt()),
        FixedOperationIds(),
        AttemptTimingV1(
            lease_duration=timedelta(minutes=2), max_attempt_runtime=timedelta(seconds=1)
        ),
    )

    result = supervisor.supervise(
        claim=claimed_attempt(), attempt=attempt, cancellation=cancellation
    )

    assert result == AttemptTimedOut()
    assert cancellation.is_cancelled()
    assert attempt.detached


def test_supervisor_fencing_cancels_and_detaches_before_finalization() -> None:
    clock = FixedMonotonicClock()
    attempt = PendingAttempt()
    cancellation = Cancellation()
    store = RecordingStore(claimed_attempt(), heartbeat_result=Fenced())
    supervisor = AttemptSupervisor(
        AttemptRuntime(AvailableRunner(), clock, ClockScheduler(clock)),
        store,
        FixedOperationIds(),
        AttemptTimingV1.standard(),
    )

    result = supervisor.supervise(
        claim=claimed_attempt(), attempt=attempt, cancellation=cancellation
    )

    assert result == SupervisorLeaseLost()
    assert cancellation.is_cancelled()
    assert attempt.detached


def test_supervisor_cancels_detaches_and_reraises_an_indeterminate_heartbeat() -> None:
    clock = FixedMonotonicClock()
    attempt = PendingAttempt()
    cancellation = Cancellation()
    claim = claimed_attempt()
    store = RecordingStore(
        claim,
        heartbeat_result=CoordinationOutcomeIndeterminate(
            operation_id=HeartbeatOperationId("heartbeat-op-1"), token=claim.token
        ),
    )
    supervisor = AttemptSupervisor(
        AttemptRuntime(AvailableRunner(), clock, ClockScheduler(clock)),
        store,
        FixedOperationIds(),
        AttemptTimingV1.standard(),
    )

    with pytest.raises(CoordinationOutcomeIndeterminate) as error:
        supervisor.supervise(claim=claim, attempt=attempt, cancellation=cancellation)

    assert error.value.operation_id == HeartbeatOperationId("heartbeat-op-1")
    assert error.value.attempt == AttemptRef("job-1", 1)
    assert cancellation.is_cancelled()
    assert attempt.detached
    assert len(store.heartbeats) == 1


def test_run_once_propagates_indeterminate_heartbeat_without_finalizing_or_releasing() -> None:
    clock = FixedMonotonicClock()
    claim = claimed_attempt()
    store = RecordingStore(
        claim,
        heartbeat_result=CoordinationOutcomeIndeterminate(
            operation_id=HeartbeatOperationId("heartbeat-op-1"), token=claim.token
        ),
    )
    runner = PendingRunner()
    processor = ProcessIngestionJob(
        store=store,
        handler=FailingHandler(),
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(NoRandom()),
        runtime=AttemptRuntime(runner, clock, ClockScheduler(clock)),
    )

    with pytest.raises(CoordinationOutcomeIndeterminate):
        processor.run_once("worker-a")

    assert store.finalizations == []
    assert store.retry_schedules == []
    assert not runner.permit.released


def test_run_once_maps_a_definite_heartbeat_fence_to_lease_lost() -> None:
    clock = FixedMonotonicClock()
    claim = claimed_attempt()
    store = RecordingStore(claim, heartbeat_result=Fenced())
    runner = PendingRunner()
    processor = ProcessIngestionJob(
        store=store,
        handler=FailingHandler(),
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(NoRandom()),
        runtime=AttemptRuntime(runner, clock, ClockScheduler(clock)),
    )

    assert processor.run_once("worker-a") == LeaseLost(AttemptRef("job-1", 1))
    assert store.finalizations == []
    assert store.retry_schedules == []
    assert not runner.permit.released


@dataclass
class FixedOperationIds:
    claim_id: ClaimOperationId = ClaimOperationId("claim-op-1")
    transition_id: TransitionOperationId = TransitionOperationId("terminal-op-1")

    def new_claim_id(self) -> ClaimOperationId:
        return self.claim_id

    def new_heartbeat_id(self) -> HeartbeatOperationId:
        return HeartbeatOperationId("heartbeat-op-1")

    def new_transition_id(self) -> TransitionOperationId:
        return self.transition_id


def claimed_attempt() -> ClaimedAttempt:
    started = datetime(2026, 8, 9, 6, 0, tzinfo=UTC)
    return ClaimedAttempt(
        token=FencingToken(
            job_id="job-1",
            attempt_number=1,
            worker_id="worker-a",
            lease_version=1,
        ),
        work=IngestionWork(
            workspace_id="workspace-1",
            document_id="document-1",
            document_version_id="version-1",
            source_object_id="object-1",
            source_object_key="opaque/object-1",
            source_media_type="application/pdf",
            parser_configuration_id="parser-v1",
            normalizer_configuration_id="normalizer-v1",
            chunking_configuration_id="chunking-v1",
            embedding_configuration_id="embedding-v1",
        ),
        attempt_count=1,
        max_attempts=4,
        attempt_started_at=started,
        initial_lease_expires_at=started + timedelta(minutes=2),
        deadline_at=started + timedelta(minutes=15),
    )


def test_run_once_claims_then_fenced_finalizes_non_retryable_failure() -> None:
    claim = claimed_attempt()
    store = RecordingStore(claim=claim)
    handler = FailingHandler()
    processor = ProcessIngestionJob(
        store=store,
        handler=handler,
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(FixedRandom(delay_microseconds=0)),
        runner=AvailableRunner(),
    )

    result = processor.run_once("worker-a")

    assert result == FailedTerminal(
        attempt=AttemptRef(job_id="job-1", attempt_number=1),
        failure_reason="terminal_input",
        safe_code="invalid_input",
    )
    assert handler.received == [claim.work]
    assert store.claims == [
        (ClaimOperationId("claim-op-1"), "worker-a", AttemptTimingV1.standard())
    ]
    assert store.finalizations == [
        (
            TransitionOperationId("terminal-op-1"),
            claim,
            CanonicalFailureV1(
                cause=FailureCauseV1.INVALID_INPUT,
                safe_code="invalid_input",
                failure_reason="terminal_input",
                cause_version="failure-causes-v1",
                mapping_version="cause-mapping-v1",
            ),
        )
    ]


def test_run_once_supervises_a_completed_attempt_before_finalization() -> None:
    claim = claimed_attempt()
    store = RecordingStore(claim=claim)
    processor = ProcessIngestionJob(
        store=store,
        handler=FailingHandler(),
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(FixedRandom(delay_microseconds=0)),
        runtime=AttemptRuntime(AvailableRunner(), FixedMonotonicClock(), NoopScheduler()),
    )

    result = processor.run_once("worker-a")

    assert result == FailedTerminal(
        attempt=AttemptRef(job_id="job-1", attempt_number=1),
        failure_reason="terminal_input",
        safe_code="invalid_input",
    )


def test_run_once_schedules_retry_when_runner_start_fails_after_claim() -> None:
    claim = claimed_attempt()
    store = RecordingStore(claim=claim)
    processor = ProcessIngestionJob(
        store=store,
        handler=FailingHandler(),
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(FixedRandom(delay_microseconds=0)),
        runtime=AttemptRuntime(StartFailRunner(), FixedMonotonicClock(), NoopScheduler()),
    )

    result = processor.run_once("worker-a")

    assert isinstance(result, RetryScheduled)
    assert len(store.retry_schedules) == 1


def test_run_once_maps_timeout_to_the_timeout_failure_cause() -> None:
    claim = claimed_attempt()
    store = RecordingStore(claim=claim)
    clock = FixedMonotonicClock()
    timing = AttemptTimingV1(timedelta(minutes=2), timedelta(seconds=1))
    runner = PendingRunner()
    processor = ProcessIngestionJob(
        store=store,
        handler=FailingHandler(),
        operation_ids=FixedOperationIds(),
        timing=timing,
        retry_policy=RetryPolicyV1(FixedRandom(delay_microseconds=0)),
        runtime=AttemptRuntime(runner, clock, ClockScheduler(clock)),
    )

    result = processor.run_once("worker-a")

    assert isinstance(result, RetryScheduled)
    assert store.retry_schedules[0][2].cause == FailureCauseV1.ATTEMPT_TIMEOUT
    assert not runner.permit.released


def test_run_once_does_not_claim_when_runner_capacity_is_unavailable() -> None:
    store = RecordingStore(claim=claimed_attempt())
    processor = ProcessIngestionJob(
        store=store,
        handler=FailingHandler(),
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(FixedRandom(delay_microseconds=0)),
        runner=NoCapacityRunner(),
    )

    with pytest.raises(RunnerCapacityUnavailable):
        processor.run_once("worker-a")

    assert store.claims == []


def test_run_once_maps_handler_failure_then_reports_scheduled_retry() -> None:
    claim = claimed_attempt()
    store = RecordingStore(claim=claim)
    processor = ProcessIngestionJob(
        store=store,
        handler=RetryableFailingHandler(),
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(FixedRandom(delay_microseconds=5_000_000)),
        runner=AvailableRunner(),
    )

    result = processor.run_once("worker-a")

    assert result == RetryScheduled(
        attempt=AttemptRef(job_id="job-1", attempt_number=1),
        safe_code="provider_transient",
    )
    assert store.retry_schedules == [
        (
            TransitionOperationId("terminal-op-1"),
            claim,
            CanonicalFailureV1(
                cause=FailureCauseV1.PROVIDER_TRANSIENT,
                safe_code="provider_transient",
                failure_reason=None,
                cause_version="failure-causes-v1",
                mapping_version="cause-mapping-v1",
            ),
            ScheduleRetry(
                delay_microseconds=5_000_000,
                window_upper_bound_microseconds=5_000_000,
            ),
        )
    ]
    assert len(store.claims) == 1
    assert store.finalizations == []


def test_run_once_exhausts_the_fourth_retryable_attempt_without_sampling() -> None:
    initial_claim = claimed_attempt()
    claim = replace(
        initial_claim,
        token=replace(initial_claim.token, attempt_number=4),
        attempt_count=4,
    )
    store = RecordingStore(claim=claim)
    processor = ProcessIngestionJob(
        store=store,
        handler=RetryableFailingHandler(),
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(NoRandom()),
        runner=AvailableRunner(),
    )

    result = processor.run_once("worker-a")

    assert result == FailedTerminal(
        attempt=AttemptRef(job_id="job-1", attempt_number=4),
        failure_reason="retry_exhausted",
        safe_code="provider_transient",
    )
    assert store.terminal_decisions == [RetryExhausted()]
    assert store.retry_schedules == []


def test_run_once_reports_lease_loss_when_fenced_while_scheduling_retry() -> None:
    claim = claimed_attempt()
    store = RecordingStore(claim=claim, retry_schedule_result=Fenced())
    processor = ProcessIngestionJob(
        store=store,
        handler=RetryableFailingHandler(),
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(FixedRandom(delay_microseconds=0)),
        runner=AvailableRunner(),
    )

    result = processor.run_once("worker-a")

    assert result == LeaseLost(attempt=AttemptRef(job_id="job-1", attempt_number=1))
    assert len(store.claims) == 1
    assert len(store.retry_schedules) == 1


def test_run_once_recovers_an_expired_attempt_before_claiming_or_executing_work() -> None:
    claim = claimed_attempt()
    observation = ExpiredAttemptObservation(
        job_id=claim.token.job_id,
        attempt_number=claim.token.attempt_number,
        worker_id=claim.token.worker_id,
        lease_version=claim.token.lease_version,
        attempt_count=claim.attempt_count,
        max_attempts=claim.max_attempts,
        lease_expires_at=claim.initial_lease_expires_at,
    )
    store = RecordingStore(claim=claim, expired_observation=observation)
    handler = FailingHandler()
    processor = ProcessIngestionJob(
        store=store,
        handler=handler,
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(FixedRandom(delay_microseconds=0)),
        runner=AvailableRunner(),
    )

    result = processor.run_once("worker-a")

    assert result == RetryScheduled(
        attempt=AttemptRef(job_id="job-1", attempt_number=1),
        safe_code="lease_expired",
    )
    assert handler.received == []
    assert store.claims == []
    assert store.recoveries == [
        (
            TransitionOperationId("terminal-op-1"),
            observation,
            CanonicalFailureV1(
                cause=FailureCauseV1.LEASE_EXPIRED,
                safe_code="lease_expired",
                failure_reason=None,
                cause_version="failure-causes-v1",
                mapping_version="cause-mapping-v1",
            ),
            ScheduleRetry(
                delay_microseconds=0,
                window_upper_bound_microseconds=5_000_000,
            ),
        )
    ]


def test_run_once_falls_through_once_after_a_stale_expiry_observation() -> None:
    claim = claimed_attempt()
    observation = ExpiredAttemptObservation(
        job_id=claim.token.job_id,
        attempt_number=claim.token.attempt_number,
        worker_id=claim.token.worker_id,
        lease_version=claim.token.lease_version,
        attempt_count=claim.attempt_count,
        max_attempts=claim.max_attempts,
        lease_expires_at=claim.initial_lease_expires_at,
    )
    store = RecordingStore(
        claim=claim,
        expired_observation=observation,
        recovery_result=StaleObservation(),
    )
    handler = FailingHandler()
    processor = ProcessIngestionJob(
        store=store,
        handler=handler,
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(FixedRandom(delay_microseconds=0)),
        runner=AvailableRunner(),
    )

    result = processor.run_once("worker-a")

    assert result == FailedTerminal(
        attempt=AttemptRef(job_id="job-1", attempt_number=1),
        failure_reason="terminal_input",
        safe_code="invalid_input",
    )
    assert handler.received == [claim.work]
    assert len(store.recoveries) == 1
    assert len(store.claims) == 1


def test_run_once_reports_expiry_retry_exhaustion_without_claiming_or_executing_work() -> None:
    initial_claim = claimed_attempt()
    claim = replace(
        initial_claim,
        token=replace(initial_claim.token, attempt_number=4),
        attempt_count=4,
    )
    observation = ExpiredAttemptObservation(
        job_id=claim.token.job_id,
        attempt_number=claim.token.attempt_number,
        worker_id=claim.token.worker_id,
        lease_version=claim.token.lease_version,
        attempt_count=claim.attempt_count,
        max_attempts=claim.max_attempts,
        lease_expires_at=claim.initial_lease_expires_at,
    )
    store = RecordingStore(
        claim=claim,
        expired_observation=observation,
        recovery_result=RecoveryFailedExhausted(
            attempt=AttemptRef(job_id="job-1", attempt_number=4)
        ),
    )
    handler = FailingHandler()
    processor = ProcessIngestionJob(
        store=store,
        handler=handler,
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(NoRandom()),
        runner=AvailableRunner(),
    )

    result = processor.run_once("worker-a")

    assert result == FailedTerminal(
        attempt=AttemptRef(job_id="job-1", attempt_number=4),
        failure_reason="retry_exhausted",
        safe_code="lease_expired",
    )
    assert handler.received == []
    assert store.claims == []
    assert store.recoveries[0][3] == RetryExhausted()
