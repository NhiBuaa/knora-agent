import asyncio
import importlib
import multiprocessing
import threading
import time

import pytest


def hanging_worker(connection, _arguments):
    connection.send({"kind": "request", "observation": {"started": True}})
    time.sleep(60)


def completed_worker(connection, _arguments):
    connection.send({"kind": "result", "result": "completed"})


def invalid_worker(connection, stage):
    connection.send(
        {"kind": "error", "error": "GENERATION_OUTPUT_INVALID", "invalid_output_stage": stage}
    )


@pytest.mark.parametrize("stage", ["EXTRACTION_FIELDS", "SOURCE_QUOTE", "PRIVATE_RAW_CANARY"])
def test_error_stage_crosses_spawn_boundary_only_when_allowlisted(stage):
    observed = module().run_process(invalid_worker, stage, deadline_seconds=5)
    assert observed["error"] == "GENERATION_OUTPUT_INVALID"
    assert observed.get("invalid_output_stage") == (
        None if stage == "PRIVATE_RAW_CANARY" else stage
    )
    assert "PRIVATE_RAW_CANARY" not in repr(observed)


def module():
    try:
        return importlib.import_module("evals.runners.process_probe")
    except ModuleNotFoundError:
        pytest.fail("process supervisor is missing")


def test_spawn_supervisor_stops_a_worker_that_does_not_cooperate_with_cancellation():
    before = {child.pid for child in multiprocessing.active_children()}
    observed = module().run_process(hanging_worker, (), deadline_seconds=2)
    assert observed["deadline_expired"] is True
    assert observed["requests"] == [{"started": True}]
    assert observed["elapsed_seconds"] < 3
    assert {child.pid for child in multiprocessing.active_children()} == before


def test_supervisor_returns_a_result_and_reaps_its_owned_child():
    before = {child.pid for child in multiprocessing.active_children()}
    observed = module().run_process(completed_worker, (), deadline_seconds=5)
    assert observed["result"] == "completed", observed
    assert observed["deadline_expired"] is False
    assert {child.pid for child in multiprocessing.active_children()} == before


def test_cancelling_async_supervisor_reaps_the_child_before_returning():
    async def scenario():
        before = {child.pid for child in multiprocessing.active_children()}
        task = asyncio.create_task(
            module().run_process_async(hanging_worker, (), deadline_seconds=10)
        )
        await asyncio.sleep(0.5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert {child.pid for child in multiprocessing.active_children()} == before

    asyncio.run(scenario())


def test_stalled_ipc_receive_does_not_block_supervisor_deadline(monkeypatch):
    released = threading.Event()

    class Receiver:
        def poll(self, _timeout):
            return True

        def recv(self):
            released.wait(1)
            raise EOFError

        def close(self):
            released.set()

    class Sender:
        def close(self):
            pass

    class Process:
        alive = False

        def start(self):
            self.alive = True

        def join(self, **kwargs):
            pass

        def is_alive(self):
            return self.alive

        def terminate(self):
            self.alive = False
            released.set()

        def close(self):
            pass

    class Context:
        def Pipe(self, **kwargs):
            return Receiver(), Sender()

        def Process(self, **kwargs):
            return Process()

    monkeypatch.setattr(multiprocessing, "get_context", lambda _method: Context())
    observed = module().run_process(hanging_worker, (), deadline_seconds=0.05)
    assert observed["deadline_expired"] is True
    assert observed["elapsed_seconds"] < 0.3


def test_repeated_async_cancellation_waits_for_supervisor_cleanup(monkeypatch):
    cleaned = threading.Event()

    def slow_cleanup(*args, cancellation, **kwargs):
        cancellation.wait(2)
        time.sleep(0.15)
        cleaned.set()

    monkeypatch.setattr(module(), "run_process", slow_cleanup)

    async def scenario():
        task = asyncio.create_task(module().run_process_async(hanging_worker, ()))
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.sleep(0.03)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cleaned.is_set()

    asyncio.run(scenario())


def test_startup_exception_closes_both_ipc_endpoints_and_the_process(monkeypatch):
    closed = []

    class Endpoint:
        def __init__(self, name):
            self.name = name

        def close(self):
            closed.append(self.name)

    class Process:
        def start(self):
            raise OSError("PRIVATE_STARTUP_ERROR")

        def close(self):
            closed.append("process")

    class Context:
        def Pipe(self, **kwargs):
            return Endpoint("receiver"), Endpoint("sender")

        def Process(self, **kwargs):
            return Process()

    monkeypatch.setattr(multiprocessing, "get_context", lambda _method: Context())
    result = module().run_process(hanging_worker, (), deadline_seconds=2)
    assert result["error"] == "PROVIDER_REQUEST_FAILED"
    assert set(closed) == {"sender", "receiver", "process"}
    assert "PRIVATE_STARTUP_ERROR" not in repr(result)


def test_unreapable_worker_is_recorded_and_all_resource_closes_are_attempted(monkeypatch):
    closed = []

    class Endpoint:
        def recv(self):
            raise EOFError

        def close(self):
            closed.append("endpoint")

    class Process:
        def start(self):
            pass

        def join(self, **kwargs):
            pass

        def is_alive(self):
            return True

        def terminate(self):
            pass

        def kill(self):
            pass

        def close(self):
            closed.append("process")
            raise ValueError("still running")

    class Context:
        def Pipe(self, **kwargs):
            return Endpoint(), Endpoint()

        def Process(self, **kwargs):
            return Process()

    monkeypatch.setattr(multiprocessing, "get_context", lambda _method: Context())
    observed = module().run_process(hanging_worker, (), deadline_seconds=2)
    assert observed["supervisor_failed"] is True
    assert observed["error"] == "PROVIDER_REQUEST_FAILED"
    assert closed.count("endpoint") >= 2
    assert "process" in closed
