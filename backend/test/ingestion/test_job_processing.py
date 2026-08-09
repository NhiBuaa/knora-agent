from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

from knora.ingestion.job_processing import (
    AttemptRef,
    AttemptTimingV1,
    CanonicalFailureV1,
    ClaimedAttempt,
    ClaimOperationId,
    FailedTerminal,
    FailureCauseV1,
    Fenced,
    FencingToken,
    FinalizationApplied,
    HandlerFailureKindV1,
    IngestionWork,
    LeaseLost,
    ProcessIngestionJob,
    RetryExhausted,
    RetryPolicyV1,
    RetryScheduleApplied,
    RetryScheduled,
    RetryScheduleResult,
    ScheduleRetry,
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


@dataclass
class FailingHandler:
    received: list[IngestionWork] = field(default_factory=list)

    def execute(self, work: IngestionWork) -> WorkFailed:
        self.received.append(work)
        return WorkFailed(
            failure_kind=HandlerFailureKindV1.INVALID_INPUT,
            safe_code="invalid_input",
        )


@dataclass
class RetryableFailingHandler:
    def execute(self, work: IngestionWork) -> WorkFailed:
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


@dataclass
class FixedOperationIds:
    claim_id: ClaimOperationId = ClaimOperationId("claim-op-1")
    transition_id: TransitionOperationId = TransitionOperationId("terminal-op-1")

    def new_claim_id(self) -> ClaimOperationId:
        return self.claim_id

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


def test_run_once_maps_handler_failure_then_reports_scheduled_retry() -> None:
    claim = claimed_attempt()
    store = RecordingStore(claim=claim)
    processor = ProcessIngestionJob(
        store=store,
        handler=RetryableFailingHandler(),
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(FixedRandom(delay_microseconds=5_000_000)),
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
    )

    result = processor.run_once("worker-a")

    assert result == LeaseLost(attempt=AttemptRef(job_id="job-1", attempt_number=1))
    assert len(store.claims) == 1
    assert len(store.retry_schedules) == 1
