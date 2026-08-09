"""Typed orchestration for one durable Ingestion Job attempt.

Ticket #26 deliberately implements only the first vertical path:
``queued -> processing -> failed``. Retry, recovery, supervision, success and supersession are
added by their approved follow-up tickets.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import NewType, Protocol, TypeVar
from uuid import uuid4

SuccessT = TypeVar("SuccessT")

ClaimOperationId = NewType("ClaimOperationId", str)
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
class Fenced:
    pass


@dataclass(frozen=True, slots=True)
class InvalidTransition:
    pass


ClaimResult = ClaimedAttempt | NoEligibleClaim
FinalizationResult = FinalizationApplied | Fenced | InvalidTransition
RetryScheduleResult = RetryScheduleApplied | Fenced | InvalidTransition


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


class WorkHandler(Protocol[SuccessT]):
    def execute(self, work: IngestionWork) -> WorkOutcome[SuccessT]: ...


class IngestionJobCoordinationStore(Protocol):
    def claim_next_attempt(
        self,
        *,
        operation_id: ClaimOperationId,
        worker_id: str,
        timing: AttemptTimingV1,
    ) -> ClaimResult: ...

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

    def new_transition_id(self) -> TransitionOperationId: ...


class UuidOperationIds:
    def new_claim_id(self) -> ClaimOperationId:
        return ClaimOperationId(str(uuid4()))

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
    ) -> None:
        self._store = store
        self._handler = handler
        self._operation_ids = operation_ids
        self._timing = timing
        self._retry_policy = retry_policy

    def run_once(self, worker_id: str) -> RunOnceResult:
        claim = self._store.claim_next_attempt(
            operation_id=self._operation_ids.new_claim_id(),
            worker_id=worker_id,
            timing=self._timing,
        )
        if isinstance(claim, NoEligibleClaim):
            return NoEligibleJob()
        if claim.token.worker_id != worker_id:
            raise CoordinationInvariantError("claim worker does not match run_once worker")

        outcome = self._handler.execute(claim.work)
        if not isinstance(outcome, WorkFailed):
            raise CoordinationInvariantError(
                "Ticket #26 only finalizes deterministic WorkFailed outcomes"
            )
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
