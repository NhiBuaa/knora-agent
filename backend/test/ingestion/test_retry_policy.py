from dataclasses import dataclass

from knora.ingestion.job_processing import (
    FailTerminal,
    FailureCauseV1,
    RetryExhausted,
    RetryPolicyV1,
    ScheduleRetry,
    SystemRandomSource,
)


@dataclass
class RecordingRandom:
    values: list[int]
    bounds: list[int]

    def next_int_inclusive(self, upper_bound_microseconds: int) -> int:
        self.bounds.append(upper_bound_microseconds)
        return self.values.pop(0)


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
