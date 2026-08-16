from __future__ import annotations

import time
from threading import Event

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
    cancelled = Event()

    def operation() -> None:
        cancelled.wait(timeout=0.5)

    with pytest.raises(ObservationFailure, match="EVALUATION_SEAL_FENCED"):
        _run_with_lease(operation, FailingHeartbeat(), cancel=cancelled.set)

    assert cancelled.is_set()
    assert time.monotonic() - started < 0.5
