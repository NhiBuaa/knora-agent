import asyncio
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from knora.adapters.cli.worker import _python_source_snapshot, run_worker
from knora.ingestion.job_processing import NoEligibleJob


class _FakeRunner:
    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = 0

    def run_once(self, worker_id: str):
        self.calls += 1
        return self.behavior(worker_id, self.calls)


def _fake_app(runner: _FakeRunner):
    @asynccontextmanager
    async def lifespan(_app):
        yield

    return SimpleNamespace(
        router=SimpleNamespace(lifespan_context=lifespan),
        state=SimpleNamespace(ingestion_worker=runner),
    )


async def _wait_until(predicate, *, timeout: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("condition was not reached before timeout")
        await asyncio.sleep(0.01)


def test_python_source_snapshot_changes_for_add_modify_and_delete(tmp_path: Path) -> None:
    source = tmp_path / "worker_source.py"
    baseline = _python_source_snapshot(tmp_path)

    source.write_text("value = 1\n", encoding="utf-8")
    added = _python_source_snapshot(tmp_path)
    assert added != baseline

    source.write_text("value = 200\n", encoding="utf-8")
    modified = _python_source_snapshot(tmp_path)
    assert modified != added

    source.unlink()
    assert _python_source_snapshot(tmp_path) == baseline


@pytest.mark.asyncio
async def test_idle_worker_restarts_without_claiming_a_second_job(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")
    first_call = threading.Event()

    def behavior(_worker_id: str, _calls: int):
        first_call.set()
        return NoEligibleJob()

    runner = _FakeRunner(behavior)
    task = asyncio.create_task(
        run_worker(
            once=False,
            poll_seconds=0.5,
            dev_watch=True,
            watch_seconds=0.01,
            watch_root=tmp_path,
            application=_fake_app(runner),
        )
    )

    await asyncio.to_thread(first_call.wait, 1)
    await asyncio.sleep(0.05)
    source.write_text("value = 2\n", encoding="utf-8")

    assert await asyncio.wait_for(task, timeout=1.0) is True
    assert runner.calls == 1


@pytest.mark.asyncio
async def test_busy_worker_finishes_current_job_before_restart(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")
    started = threading.Event()
    release = threading.Event()

    def behavior(_worker_id: str, _calls: int):
        started.set()
        if not release.wait(timeout=1):
            raise RuntimeError("test did not release the fake job")
        return object()

    runner = _FakeRunner(behavior)
    task = asyncio.create_task(
        run_worker(
            once=False,
            poll_seconds=0.5,
            dev_watch=True,
            watch_seconds=0.01,
            watch_root=tmp_path,
            application=_fake_app(runner),
        )
    )

    await asyncio.to_thread(started.wait, 1)
    source.write_text("value = 2\n", encoding="utf-8")
    await asyncio.sleep(0.05)

    assert runner.calls == 1
    assert not task.done()

    release.set()
    assert await asyncio.wait_for(task, timeout=1.0) is True
    assert runner.calls == 1


@pytest.mark.asyncio
async def test_multiple_changes_coalesce_into_one_restart(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")
    started = threading.Event()
    release = threading.Event()

    def behavior(_worker_id: str, _calls: int):
        started.set()
        release.wait(timeout=1)
        return object()

    runner = _FakeRunner(behavior)
    task = asyncio.create_task(
        run_worker(
            once=False,
            poll_seconds=0.5,
            dev_watch=True,
            watch_seconds=0.01,
            watch_root=tmp_path,
            application=_fake_app(runner),
        )
    )

    await asyncio.to_thread(started.wait, 1)
    for value in (2, 3, 4):
        source.write_text(f"value = {value}\n", encoding="utf-8")
        await asyncio.sleep(0.02)

    release.set()
    assert await asyncio.wait_for(task, timeout=1.0) is True
    assert runner.calls == 1


@pytest.mark.asyncio
async def test_unexpected_worker_failure_is_not_hidden_by_restart_loop(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")

    def behavior(_worker_id: str, _calls: int):
        raise RuntimeError("worker exploded")

    runner = _FakeRunner(behavior)
    with pytest.raises(RuntimeError, match="worker exploded"):
        await run_worker(
            once=False,
            poll_seconds=0.1,
            dev_watch=True,
            watch_seconds=0.01,
            watch_root=tmp_path,
            application=_fake_app(runner),
        )
