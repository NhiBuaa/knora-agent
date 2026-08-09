"""Typed orchestration for one durable Ingestion Job attempt.

Ticket #26 introduced ``queued -> processing -> failed`` and Ticket #27 added scheduled retry.
Ticket #28 adds optimistic expired-attempt recovery. Supervision, success and supersession remain
approved follow-up work.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from threading import Event
from typing import NewType, Protocol, TypeVar
from uuid import uuid4

SuccessT = TypeVar("SuccessT")

ClaimOperationId = NewType("ClaimOperationId", str)
HeartbeatOperationId = NewType("HeartbeatOperationId", str)
TransitionOperationId = NewType("TransitionOperationId", str)


class CoordinationInvariantError(RuntimeError):
    """Signals impossible coordination input or a slice not yet delivered."""


class HandlerFailureKindV1(StrEnum):
    INVALID_INPUT = "invalid_input"
    UNSUPPORTED_INPUT = "unsupported_input"
    CONFIGURATION_INVALID = "configuration_invalid"
    RESOURCE_LIMIT = "resource_limit"
    VECTOR_MISMATCH = "vector_mismatch"
    PROVIDER_TRANSIENT = "provider_transient"
    DATABASE_TRANSIENT = "database_transient"
    STORAGE_TRANSIENT = "storage_transient"
    WORKER_UNEXPECTED = "worker_unexpected"


class FailureCauseV1(StrEnum):
    PROVIDER_TRANSIENT = "provider_transient"
    DATABASE_TRANSIENT = "database_transient"
    STORAGE_TRANSIENT = "storage_transient"
    WORKER_UNEXPECTED = "worker_unexpected"
    ATTEMPT_TIMEOUT = "attempt_timeout"
    LEASE_EXPIRED = "lease_expired"
    INVALID_INPUT = "invalid_input"
    UNSUPPORTED_INPUT = "unsupported_input"
    CONFIGURATION_INVALID = "configuration_invalid"
    RESOURCE_LIMIT = "resource_limit"
    VECTOR_MISMATCH = "vector_mismatch"


_SAFE_CODES_BY_KIND: dict[HandlerFailureKindV1, frozenset[str]] = {
    HandlerFailureKindV1.INVALID_INPUT: frozenset({"invalid_input"}),
    HandlerFailureKindV1.UNSUPPORTED_INPUT: frozenset({"unsupported_input"}),
    HandlerFailureKindV1.CONFIGURATION_INVALID: frozenset({"configuration_invalid"}),
    HandlerFailureKindV1.RESOURCE_LIMIT: frozenset({"resource_limit"}),
    HandlerFailureKindV1.VECTOR_MISMATCH: frozenset({"vector_mismatch"}),
    HandlerFailureKindV1.PROVIDER_TRANSIENT: frozenset({"provider_transient"}),
    HandlerFailureKindV1.DATABASE_TRANSIENT: frozenset({"database_transient"}),
    HandlerFailureKindV1.STORAGE_TRANSIENT: frozenset({"storage_transient"}),
    HandlerFailureKindV1.WORKER_UNEXPECTED: frozenset({"worker_unexpected"}),
}

_TERMINAL_REASONS: dict[FailureCauseV1, str] = {
    FailureCauseV1.INVALID_INPUT: "terminal_input",
    FailureCauseV1.UNSUPPORTED_INPUT: "terminal_input",
    FailureCauseV1.CONFIGURATION_INVALID: "terminal_config",
    FailureCauseV1.RESOURCE_LIMIT: "resource_limit",
    FailureCauseV1.VECTOR_MISMATCH: "terminal_config",
}

_RETRYABLE_CAUSES = frozenset(
    {
        FailureCauseV1.PROVIDER_TRANSIENT,
        FailureCauseV1.DATABASE_TRANSIENT,
        FailureCauseV1.STORAGE_TRANSIENT,
        FailureCauseV1.WORKER_UNEXPECTED,
        FailureCauseV1.ATTEMPT_TIMEOUT,
        FailureCauseV1.LEASE_EXPIRED,
    }
)

_RETRY_WINDOWS_MICROSECONDS = {
    1: 5_000_000,
    2: 30_000_000,
    3: 120_000_000,
}


class RandomSource(Protocol):
    def next_int_inclusive(self, upper_bound_microseconds: int) -> int: ...


class SystemRandomSource:
    """Process-local full-jitter source over inclusive integer microsecond windows."""

    def next_int_inclusive(self, upper_bound_microseconds: int) -> int:
        if upper_bound_microseconds < 0:
            raise ValueError("retry jitter upper bound must be non-negative")
        return secrets.randbelow(upper_bound_microseconds + 1)


@dataclass(frozen=True, slots=True)
class ScheduleRetry:
    delay_microseconds: int
    window_upper_bound_microseconds: int
    policy_version: str = "retry-policy-v1"
    jitter_version: str = "full-jitter-v1"

    def __post_init__(self) -> None:
        if (
            isinstance(self.delay_microseconds, bool)
            or isinstance(self.window_upper_bound_microseconds, bool)
            or not isinstance(self.delay_microseconds, int)
            or not isinstance(self.window_upper_bound_microseconds, int)
            or self.delay_microseconds < 0
            or self.window_upper_bound_microseconds < self.delay_microseconds
        ):
            raise ValueError("retry delay must be an integer within its inclusive jitter window")


@dataclass(frozen=True, slots=True)
class RetryExhausted:
    policy_version: str = "retry-policy-v1"


@dataclass(frozen=True, slots=True)
class FailTerminal:
    policy_version: str = "retry-policy-v1"


RetryDecision = ScheduleRetry | RetryExhausted | FailTerminal


class RetryPolicyV1:
    """Classify canonical observed facts without leaking retryability into causes."""

    def __init__(self, random_source: RandomSource) -> None:
        self._random_source = random_source

    def decide(
        self,
        cause: FailureCauseV1,
        attempt_count: int,
        max_attempts: int,
    ) -> RetryDecision:
        if cause not in _RETRYABLE_CAUSES:
            return FailTerminal()
        if attempt_count >= max_attempts:
            return RetryExhausted()
        upper_bound = _RETRY_WINDOWS_MICROSECONDS[attempt_count]
        delay = self._random_source.next_int_inclusive(upper_bound)
        if delay < 0 or delay > upper_bound:
            raise CoordinationInvariantError(
                "RandomSource returned a retry delay outside the window"
            )
        return ScheduleRetry(
            delay_microseconds=delay,
            window_upper_bound_microseconds=upper_bound,
        )


@dataclass(frozen=True, slots=True)
class AttemptRef:
    job_id: str
    attempt_number: int


@dataclass(frozen=True, slots=True)
class FencingToken:
    job_id: str
    attempt_number: int
    worker_id: str
    lease_version: int


class CoordinationOutcomeIndeterminate(RuntimeError):
    """A heartbeat outcome could not be authoritatively reconciled."""

    def __init__(self, *, operation_id: HeartbeatOperationId, token: FencingToken) -> None:
        self.operation_id = operation_id
        self.attempt = AttemptRef(token.job_id, token.attempt_number)
        super().__init__("heartbeat coordination outcome is indeterminate")


@dataclass(frozen=True, slots=True)
class IngestionWork:
    workspace_id: str
    document_id: str
    document_version_id: str
    source_object_id: str
    source_object_key: str
    source_media_type: str
    parser_configuration_id: str
    normalizer_configuration_id: str
    chunking_configuration_id: str
    embedding_configuration_id: str


@dataclass(frozen=True, slots=True)
class ClaimedAttempt:
    token: FencingToken
    work: IngestionWork
    attempt_count: int
    max_attempts: int
    attempt_started_at: datetime
    initial_lease_expires_at: datetime
    deadline_at: datetime


@dataclass(frozen=True, slots=True)
class ExpiredAttemptObservation:
    """An optimistic database-time observation that grants no processing ownership."""

    job_id: str
    attempt_number: int
    worker_id: str
    lease_version: int
    attempt_count: int
    max_attempts: int
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class AttemptTimingV1:
    lease_duration: timedelta
    max_attempt_runtime: timedelta

    @classmethod
    def standard(cls) -> AttemptTimingV1:
        return cls(lease_duration=timedelta(minutes=2), max_attempt_runtime=timedelta(minutes=15))


@dataclass(frozen=True, slots=True)
class WorkSucceeded[SuccessT]:
    payload: SuccessT


@dataclass(frozen=True, slots=True)
class WorkSuperseded:
    safe_code: str


@dataclass(frozen=True, slots=True)
class WorkFailed:
    failure_kind: HandlerFailureKindV1
    safe_code: str

    def __post_init__(self) -> None:
        if self.safe_code not in _SAFE_CODES_BY_KIND[self.failure_kind]:
            raise ValueError("safe_code is not allowlisted for failure_kind")


WorkOutcome = WorkSucceeded[SuccessT] | WorkSuperseded | WorkFailed


@dataclass(frozen=True, slots=True)
class CanonicalFailureV1:
    cause: FailureCauseV1
    safe_code: str
    failure_reason: str | None
    cause_version: str
    mapping_version: str


class CauseMappingV1:
    """The closed, pure V1 mapping from observed handler facts to canonical facts."""

    _causes: dict[HandlerFailureKindV1, FailureCauseV1] = {
        HandlerFailureKindV1.INVALID_INPUT: FailureCauseV1.INVALID_INPUT,
        HandlerFailureKindV1.UNSUPPORTED_INPUT: FailureCauseV1.UNSUPPORTED_INPUT,
        HandlerFailureKindV1.CONFIGURATION_INVALID: FailureCauseV1.CONFIGURATION_INVALID,
        HandlerFailureKindV1.RESOURCE_LIMIT: FailureCauseV1.RESOURCE_LIMIT,
        HandlerFailureKindV1.VECTOR_MISMATCH: FailureCauseV1.VECTOR_MISMATCH,
        HandlerFailureKindV1.PROVIDER_TRANSIENT: FailureCauseV1.PROVIDER_TRANSIENT,
        HandlerFailureKindV1.DATABASE_TRANSIENT: FailureCauseV1.DATABASE_TRANSIENT,
        HandlerFailureKindV1.STORAGE_TRANSIENT: FailureCauseV1.STORAGE_TRANSIENT,
        HandlerFailureKindV1.WORKER_UNEXPECTED: FailureCauseV1.WORKER_UNEXPECTED,
    }

    @classmethod
    def map(cls, failed: WorkFailed) -> CanonicalFailureV1:
        return CanonicalFailureV1(
            cause=cls._causes[failed.failure_kind],
            safe_code=failed.safe_code,
            failure_reason=None,
            cause_version="failure-causes-v1",
            mapping_version="cause-mapping-v1",
        )

    @classmethod
    def map_terminal(cls, failed: WorkFailed) -> CanonicalFailureV1:
        return cls.terminalize(cls.map(failed))

    @classmethod
    def terminalize(cls, observed: CanonicalFailureV1) -> CanonicalFailureV1:
        cause = observed.cause
        failure_reason = _TERMINAL_REASONS.get(cause)
        if failure_reason is None:
            raise CoordinationInvariantError(
                "retryable cause cannot be terminalized without exhaustion"
            )
        return CanonicalFailureV1(
            cause=cause,
            safe_code=observed.safe_code,
            failure_reason=failure_reason,
            cause_version=observed.cause_version,
            mapping_version=observed.mapping_version,
        )


@dataclass(frozen=True, slots=True)
class NoEligibleClaim:
    pass


@dataclass(frozen=True, slots=True)
class FinalizationApplied:
    attempt: AttemptRef


@dataclass(frozen=True, slots=True)
class RetryScheduleApplied:
    attempt: AttemptRef
    next_attempt_at: datetime


@dataclass(frozen=True, slots=True)
class RecoveryRetryScheduled:
    attempt: AttemptRef
    next_attempt_at: datetime


@dataclass(frozen=True, slots=True)
class RecoveryFailedExhausted:
    attempt: AttemptRef


@dataclass(frozen=True, slots=True)
class StaleObservation:
    pass


@dataclass(frozen=True, slots=True)
class NotExpired:
    pass


@dataclass(frozen=True, slots=True)
class Fenced:
    pass


@dataclass(frozen=True, slots=True)
class HeartbeatApplied:
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class InvalidTransition:
    pass


ClaimResult = ClaimedAttempt | NoEligibleClaim
FinalizationResult = FinalizationApplied | Fenced | InvalidTransition
RetryScheduleResult = RetryScheduleApplied | Fenced | InvalidTransition
HeartbeatResult = HeartbeatApplied | Fenced
RecoveryResult = RecoveryRetryScheduled | RecoveryFailedExhausted | StaleObservation | NotExpired


@dataclass(frozen=True, slots=True)
class NoEligibleJob:
    pass


@dataclass(frozen=True, slots=True)
class FailedTerminal:
    attempt: AttemptRef
    failure_reason: str
    safe_code: str


@dataclass(frozen=True, slots=True)
class LeaseLost:
    attempt: AttemptRef


@dataclass(frozen=True, slots=True)
class RetryScheduled:
    attempt: AttemptRef
    safe_code: str


RunOnceResult = NoEligibleJob | RetryScheduled | FailedTerminal | LeaseLost


class CancellationToken(Protocol):
    def cancel(self) -> None: ...

    def is_cancelled(self) -> bool: ...


class Cancellation:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


class WorkHandler(Protocol[SuccessT]):
    def execute(
        self, work: IngestionWork, cancellation: CancellationToken
    ) -> WorkOutcome[SuccessT]: ...


@dataclass(frozen=True, slots=True)
class HandlerRaised:
    pass


@dataclass(frozen=True, slots=True)
class AttemptCompletion[SuccessT]:
    completed_at: float
    result: WorkOutcome[SuccessT] | HandlerRaised


class RunningAttempt(Protocol[SuccessT]):
    def completion(self) -> AttemptCompletion[SuccessT] | None: ...

    def wait_until(self, deadline: float) -> None: ...

    def detach(self) -> None: ...


class RunnerCapacityUnavailable(RuntimeError):
    """Signals that execution admission failed before any durable claim."""


class ExecutionPermit(Protocol):
    def start(
        self,
        handler: WorkHandler[SuccessT],
        work: IngestionWork,
        cancellation: CancellationToken,
        monotonic_clock: MonotonicClock,
    ) -> RunningAttempt[SuccessT]: ...

    def release(self) -> None: ...


class AttemptRunner(Protocol):
    def try_reserve(self) -> ExecutionPermit | None: ...


class MonotonicClock(Protocol):
    def now(self) -> float: ...


class AttemptScheduler(Protocol):
    def wait_until(self, attempt: RunningAttempt[SuccessT], deadline: float) -> None: ...


@dataclass(frozen=True, slots=True)
class AttemptRuntime:
    """One coherent local runtime for bounded attempt supervision."""

    runner: AttemptRunner
    monotonic_clock: MonotonicClock
    scheduler: AttemptScheduler


@dataclass(frozen=True, slots=True)
class AttemptTimedOut:
    pass


@dataclass(frozen=True, slots=True)
class SupervisorLeaseLost:
    pass


@dataclass(frozen=True, slots=True)
class HandlerCompleted[SuccessT]:
    completion: AttemptCompletion[SuccessT]


class AttemptSupervisor:
    """Owns local deadline precedence for one bounded attempt."""

    def __init__(
        self,
        runtime: AttemptRuntime,
        store: IngestionJobCoordinationStore,
        operation_ids: OperationIdFactory,
        timing: AttemptTimingV1,
    ) -> None:
        self._runtime = runtime
        self._store = store
        self._operation_ids = operation_ids
        self._timing = timing

    def resolve_completion(
        self, *, completed_at: float, deadline_at: float
    ) -> AttemptTimedOut | None:
        if completed_at >= deadline_at:
            return AttemptTimedOut()
        return None

    @staticmethod
    def resolve_heartbeat(result: HeartbeatResult) -> SupervisorLeaseLost | None:
        if isinstance(result, Fenced):
            return SupervisorLeaseLost()
        return None

    def supervise(
        self,
        *,
        claim: ClaimedAttempt,
        attempt: RunningAttempt[SuccessT],
        cancellation: CancellationToken,
    ) -> HandlerCompleted[SuccessT] | AttemptTimedOut | SupervisorLeaseLost:
        started_at = self._runtime.monotonic_clock.now()
        deadline_at = started_at + self._timing.max_attempt_runtime.total_seconds()
        next_heartbeat_at = started_at + 30.0
        while True:
            completion = attempt.completion()
            now = self._runtime.monotonic_clock.now()
            if now >= next_heartbeat_at and now < deadline_at:
                operation_id = self._operation_ids.new_heartbeat_id()
                try:
                    heartbeat = self._store.heartbeat(
                        operation_id=operation_id,
                        token=claim.token,
                        lease_duration=self._timing.lease_duration,
                    )
                except CoordinationOutcomeIndeterminate:
                    cancellation.cancel()
                    attempt.detach()
                    raise
                if self.resolve_heartbeat(heartbeat) is not None:
                    cancellation.cancel()
                    attempt.detach()
                    return SupervisorLeaseLost()
                next_heartbeat_at += 30.0
                continue
            if completion is not None and self.resolve_completion(
                completed_at=completion.completed_at, deadline_at=deadline_at
            ) is None:
                return HandlerCompleted(completion)
            if now >= deadline_at or completion is not None:
                cancellation.cancel()
                attempt.detach()
                return AttemptTimedOut()
            self._runtime.scheduler.wait_until(attempt, min(next_heartbeat_at, deadline_at))


class IngestionJobCoordinationStore(Protocol):
    def observe_expired_attempt(self) -> ExpiredAttemptObservation | None: ...

    def apply_expired_recovery(
        self,
        *,
        operation_id: TransitionOperationId,
        observation: ExpiredAttemptObservation,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry | RetryExhausted,
    ) -> RecoveryResult: ...

    def claim_next_attempt(
        self,
        *,
        operation_id: ClaimOperationId,
        worker_id: str,
        timing: AttemptTimingV1,
    ) -> ClaimResult: ...

    def heartbeat(
        self,
        *,
        operation_id: HeartbeatOperationId,
        token: FencingToken,
        lease_duration: timedelta,
    ) -> HeartbeatResult: ...

    def finalize_terminal_failure(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: RetryExhausted | FailTerminal | None = None,
    ) -> FinalizationResult: ...

    def schedule_retry(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry,
    ) -> RetryScheduleResult: ...


class OperationIdFactory(Protocol):
    def new_claim_id(self) -> ClaimOperationId: ...

    def new_heartbeat_id(self) -> HeartbeatOperationId: ...

    def new_transition_id(self) -> TransitionOperationId: ...


class UuidOperationIds:
    def new_claim_id(self) -> ClaimOperationId:
        return ClaimOperationId(str(uuid4()))

    def new_heartbeat_id(self) -> HeartbeatOperationId:
        return HeartbeatOperationId(str(uuid4()))

    def new_transition_id(self) -> TransitionOperationId:
        return TransitionOperationId(str(uuid4()))


class ProcessIngestionJob[SuccessT]:
    """Own the single-attempt lifecycle exposed by this tracer bullet."""

    def __init__(
        self,
        *,
        store: IngestionJobCoordinationStore,
        handler: WorkHandler[SuccessT],
        operation_ids: OperationIdFactory,
        timing: AttemptTimingV1,
        retry_policy: RetryPolicyV1,
        runtime: AttemptRuntime | None = None,
        runner: AttemptRunner | None = None,
    ) -> None:
        self._store = store
        self._handler = handler
        self._operation_ids = operation_ids
        self._timing = timing
        self._retry_policy = retry_policy
        self._runtime = runtime
        if runtime is None and runner is None:
            raise ValueError("ProcessIngestionJob needs a runner or AttemptRuntime")
        self._runner = runtime.runner if runtime is not None else runner

    def run_once(self, worker_id: str) -> RunOnceResult:
        recovered = self._recover_expired_attempt()
        if recovered is not None:
            return recovered

        permit = self._runner.try_reserve()
        if permit is None:
            raise RunnerCapacityUnavailable("no bounded execution capacity is available")
        retain_permit = False
        try:
            claim = self._store.claim_next_attempt(
                operation_id=self._operation_ids.new_claim_id(),
                worker_id=worker_id,
                timing=self._timing,
            )
            if isinstance(claim, NoEligibleClaim):
                return NoEligibleJob()
            if claim.token.worker_id != worker_id:
                raise CoordinationInvariantError("claim worker does not match run_once worker")

            timed_out = False
            if self._runtime is None:
                outcome = self._handler.execute(claim.work, Cancellation())
            else:
                cancellation = Cancellation()
                try:
                    running = permit.start(
                        self._handler,
                        claim.work,
                        cancellation,
                        self._runtime.monotonic_clock,
                    )
                except BaseException:
                    outcome = WorkFailed(
                        HandlerFailureKindV1.WORKER_UNEXPECTED, "worker_unexpected"
                    )
                else:
                    try:
                        supervised = AttemptSupervisor(
                            self._runtime, self._store, self._operation_ids, self._timing
                        ).supervise(claim=claim, attempt=running, cancellation=cancellation)
                    except CoordinationOutcomeIndeterminate:
                        retain_permit = True
                        raise
                    if isinstance(supervised, SupervisorLeaseLost):
                        retain_permit = True
                        return LeaseLost(
                            attempt=AttemptRef(claim.token.job_id, claim.token.attempt_number)
                        )
                    if isinstance(supervised, AttemptTimedOut) or isinstance(
                        supervised.completion.result, HandlerRaised
                    ):
                        retain_permit = isinstance(supervised, AttemptTimedOut)
                        timed_out = isinstance(supervised, AttemptTimedOut)
                        outcome = WorkFailed(
                            HandlerFailureKindV1.WORKER_UNEXPECTED, "worker_unexpected"
                        )
                    else:
                        outcome = supervised.completion.result
        finally:
            if not retain_permit:
                permit.release()
        if not isinstance(outcome, WorkFailed):
            raise CoordinationInvariantError(
                "Ticket #26 only finalizes deterministic WorkFailed outcomes"
            )
        if timed_out:
            observed_failure = CanonicalFailureV1(
                cause=FailureCauseV1.ATTEMPT_TIMEOUT,
                safe_code="attempt_timeout",
                failure_reason=None,
                cause_version="failure-causes-v1",
                mapping_version="supervisor-v1",
            )
        else:
            observed_failure = CauseMappingV1.map(outcome)
        decision = self._retry_policy.decide(
            observed_failure.cause,
            attempt_count=claim.attempt_count,
            max_attempts=claim.max_attempts,
        )
        operation_id = self._operation_ids.new_transition_id()
        if isinstance(decision, ScheduleRetry):
            scheduled = self._store.schedule_retry(
                operation_id=operation_id,
                claim=claim,
                failure=observed_failure,
                decision=decision,
            )
            if isinstance(scheduled, RetryScheduleApplied):
                return RetryScheduled(
                    attempt=scheduled.attempt,
                    safe_code=observed_failure.safe_code,
                )
            if isinstance(scheduled, Fenced):
                return LeaseLost(attempt=AttemptRef(claim.token.job_id, claim.token.attempt_number))
            raise CoordinationInvariantError("retry scheduling was not applicable")

        if isinstance(decision, RetryExhausted):
            failure = CanonicalFailureV1(
                cause=observed_failure.cause,
                safe_code=observed_failure.safe_code,
                failure_reason="retry_exhausted",
                cause_version=observed_failure.cause_version,
                mapping_version=observed_failure.mapping_version,
            )
        else:
            failure = CauseMappingV1.terminalize(observed_failure)

        finalization = self._store.finalize_terminal_failure(
            operation_id=operation_id,
            claim=claim,
            failure=failure,
            decision=decision,
        )
        if isinstance(finalization, FinalizationApplied):
            if failure.failure_reason is None:
                raise CoordinationInvariantError(
                    "terminal finalization did not have a failure reason"
                )
            return FailedTerminal(
                attempt=finalization.attempt,
                failure_reason=failure.failure_reason,
                safe_code=failure.safe_code,
            )
        if isinstance(finalization, Fenced):
            return LeaseLost(attempt=AttemptRef(claim.token.job_id, claim.token.attempt_number))
        raise CoordinationInvariantError("terminal finalization was not applicable")

    def _recover_expired_attempt(self) -> RunOnceResult | None:
        observation = self._store.observe_expired_attempt()
        if observation is None:
            return None

        failure = CanonicalFailureV1(
            cause=FailureCauseV1.LEASE_EXPIRED,
            safe_code="lease_expired",
            failure_reason=None,
            cause_version="failure-causes-v1",
            mapping_version="cause-mapping-v1",
        )
        decision = self._retry_policy.decide(
            failure.cause,
            attempt_count=observation.attempt_count,
            max_attempts=observation.max_attempts,
        )
        if not isinstance(decision, (ScheduleRetry, RetryExhausted)):
            raise CoordinationInvariantError(
                "lease-expiry recovery requires a retry policy decision"
            )

        recovery = self._store.apply_expired_recovery(
            operation_id=self._operation_ids.new_transition_id(),
            observation=observation,
            failure=failure,
            decision=decision,
        )
        if isinstance(recovery, RecoveryRetryScheduled):
            return RetryScheduled(attempt=recovery.attempt, safe_code=failure.safe_code)
        if isinstance(recovery, RecoveryFailedExhausted):
            return FailedTerminal(
                attempt=recovery.attempt,
                failure_reason="retry_exhausted",
                safe_code=failure.safe_code,
            )
        if isinstance(recovery, (StaleObservation, NotExpired)):
            return None
        raise CoordinationInvariantError("expired-attempt recovery was not applicable")
