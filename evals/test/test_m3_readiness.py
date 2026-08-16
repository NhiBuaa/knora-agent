from __future__ import annotations

import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

import pytest
from evals.runners.m3_readiness import _IsolatedHttpRequest, _run_with_lease
from evals.runners.milestone_3 import ObservationFailure


class FailingHeartbeat:
    def __init__(self) -> None:
        self._checks = 0

    def raise_if_failed(self) -> None:
        self._checks += 1
        if self._checks > 1:
            raise ObservationFailure("EVALUATION_SEAL_FENCED")


class ToggleHeartbeat:
    def __init__(self, failed: Event) -> None:
        self.failed = failed

    def raise_if_failed(self) -> None:
        if self.failed.is_set():
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


def test_blocking_http_request_process_is_terminated_on_lease_loss() -> None:
    started = Event()
    release = Event()
    heartbeat_failed = Event()

    class BlockingHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            started.set()
            heartbeat_failed.set()
            release.wait(timeout=5)
            try:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            except BrokenPipeError:
                pass

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), BlockingHandler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    request = _IsolatedHttpRequest(
        "GET", f"http://127.0.0.1:{server.server_port}/blocked", timeout=30
    )
    try:
        with pytest.raises(ObservationFailure, match="EVALUATION_SEAL_FENCED"):
            _run_with_lease(
                request,
                ToggleHeartbeat(heartbeat_failed),
                cancel=request.cancel,
            )
        assert started.is_set()
        assert not request.is_alive()
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)


def test_isolated_http_cleanup_escalates_to_kill() -> None:
    class StubbornProcess:
        def __init__(self) -> None:
            self.killed = False

        def join(self, timeout: float | None = None) -> None:
            del timeout

        def is_alive(self) -> bool:
            return not self.killed

        def terminate(self) -> None:
            pass

        def kill(self) -> None:
            self.killed = True

    request = _IsolatedHttpRequest("GET", "http://127.0.0.1:1", timeout=1)
    process = StubbornProcess()
    request.process = process  # type: ignore[assignment]

    request._cleanup()

    assert process.killed
