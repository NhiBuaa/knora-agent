from __future__ import annotations

import time

import pytest
from evals.runners.m3_readiness import _run_with_lease
from evals.runners.milestone_3 import ObservationFailure


class FailingHeartbeat:
    def __init__(self) -> None:
        self._checks = 0

    def raise_if_failed(self) -> None:
        self._checks += 1
        if self._checks > 1:
            raise ObservationFailure("EVALUATION_SEAL_FENCED")


def test_readiness_guard_aborts_when_heartbeat_fails_during_operation() -> None:
    started = time.monotonic()

    with pytest.raises(ObservationFailure, match="EVALUATION_SEAL_FENCED"):
        _run_with_lease(lambda: time.sleep(0.5), FailingHeartbeat())

    assert time.monotonic() - started < 0.5
