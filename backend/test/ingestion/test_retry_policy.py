from dataclasses import dataclass

import pytest

from knora.ingestion.job_processing import (
    CauseMappingV1,
    FailTerminal,
    FailureCauseV1,
    HandlerFailureKindV1,
    RetryExhausted,
    RetryPolicyV1,
    ScheduleRetry,
    SystemRandomSource,
    WorkFailed,
)


@dataclass
class RecordingRandom:
    values: list[int]
    bounds: list[int]

    def next_int_inclusive(self, upper_bound_microseconds: int) -> int:
        self.bounds.append(upper_bound_microseconds)
        return self.values.pop(0)


@pytest.mark.parametrize(
    ("failure_kind", "safe_code", "expected_cause"),
    [
        (HandlerFailureKindV1.INVALID_INPUT, "invalid_input", FailureCauseV1.INVALID_INPUT),
        (
            HandlerFailureKindV1.UNSUPPORTED_INPUT,
            "unsupported_input",
            FailureCauseV1.UNSUPPORTED_INPUT,
        ),
        (
            HandlerFailureKindV1.CONFIGURATION_INVALID,
            "configuration_invalid",
            FailureCauseV1.CONFIGURATION_INVALID,
        ),
        (HandlerFailureKindV1.RESOURCE_LIMIT, "resource_limit", FailureCauseV1.RESOURCE_LIMIT),
        (HandlerFailureKindV1.VECTOR_MISMATCH, "vector_mismatch", FailureCauseV1.VECTOR_MISMATCH),
        (
            HandlerFailureKindV1.PROVIDER_TRANSIENT,
            "provider_transient",
            FailureCauseV1.PROVIDER_TRANSIENT,
        ),
        (
            HandlerFailureKindV1.DATABASE_TRANSIENT,
            "database_transient",
            FailureCauseV1.DATABASE_TRANSIENT,
        ),
        (
            HandlerFailureKindV1.STORAGE_TRANSIENT,
            "storage_transient",
            FailureCauseV1.STORAGE_TRANSIENT,
        ),
        (
            HandlerFailureKindV1.WORKER_UNEXPECTED,
            "worker_unexpected",
            FailureCauseV1.WORKER_UNEXPECTED,
        ),
    ],
)
def test_cause_mapping_is_closed_and_preserves_observed_failure_facts(
    failure_kind: HandlerFailureKindV1,
    safe_code: str,
    expected_cause: FailureCauseV1,
) -> None:
    mapped = CauseMappingV1.map(WorkFailed(failure_kind=failure_kind, safe_code=safe_code))

    assert mapped.cause is expected_cause
    assert mapped.safe_code == safe_code
    assert mapped.failure_reason is None
    assert mapped.cause_version == "failure-causes-v1"
    assert mapped.mapping_version == "cause-mapping-v1"


def test_retry_policy_uses_exact_full_jitter_once_for_retryable_attempts() -> None:
    random = RecordingRandom(values=[5_000_000, 30_000_000, 120_000_000], bounds=[])
    policy = RetryPolicyV1(random)

    decisions = [
        policy.decide(FailureCauseV1.PROVIDER_TRANSIENT, attempt_count, max_attempts=4)
        for attempt_count in (1, 2, 3)
    ]

    assert decisions == [
        ScheduleRetry(delay_microseconds=5_000_000, window_upper_bound_microseconds=5_000_000),
        ScheduleRetry(delay_microseconds=30_000_000, window_upper_bound_microseconds=30_000_000),
        ScheduleRetry(delay_microseconds=120_000_000, window_upper_bound_microseconds=120_000_000),
    ]
    assert random.bounds == [5_000_000, 30_000_000, 120_000_000]


def test_retry_policy_accepts_zero_delay() -> None:
    random = RecordingRandom(values=[0], bounds=[])

    decision = RetryPolicyV1(random).decide(
        FailureCauseV1.PROVIDER_TRANSIENT,
        attempt_count=1,
        max_attempts=4,
    )

    assert decision == ScheduleRetry(
        delay_microseconds=0,
        window_upper_bound_microseconds=5_000_000,
    )


def test_system_random_source_translates_inclusive_upper_bound_for_exclusive_rng(
    monkeypatch,
) -> None:
    observed_bounds: list[int] = []

    def exclusive_randbelow(upper_bound: int) -> int:
        observed_bounds.append(upper_bound)
        return upper_bound - 1

    monkeypatch.setattr("knora.ingestion.job_processing.secrets.randbelow", exclusive_randbelow)

    assert SystemRandomSource().next_int_inclusive(120_000_000) == 120_000_000
    assert observed_bounds == [120_000_001]


def test_retry_policy_does_not_consume_random_for_exhaustion_or_terminal_failure() -> None:
    random = RecordingRandom(values=[5_000_000], bounds=[])
    policy = RetryPolicyV1(random)

    exhausted = policy.decide(FailureCauseV1.PROVIDER_TRANSIENT, attempt_count=4, max_attempts=4)
    terminal = policy.decide(FailureCauseV1.INVALID_INPUT, attempt_count=4, max_attempts=4)

    assert exhausted == RetryExhausted()
    assert terminal == FailTerminal()
    assert random.values == [5_000_000]
    assert random.bounds == []


def test_deterministic_failure_is_terminal_before_and_at_the_attempt_limit() -> None:
    random = RecordingRandom(values=[5_000_000], bounds=[])
    policy = RetryPolicyV1(random)

    first = policy.decide(FailureCauseV1.INVALID_INPUT, attempt_count=1, max_attempts=4)
    fourth = policy.decide(FailureCauseV1.INVALID_INPUT, attempt_count=4, max_attempts=4)

    assert first == FailTerminal()
    assert fourth == FailTerminal()
    assert random.values == [5_000_000]
    assert random.bounds == []
