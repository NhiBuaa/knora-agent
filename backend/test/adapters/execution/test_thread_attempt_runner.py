from threading import Event

from knora.adapters.execution.thread_attempt_runner import FixedCapacityThreadAttemptRunner
from knora.ingestion.job_processing import Cancellation, HandlerRaised


class FixedClock:
    def now(self) -> float:
        return 7.0


class RaisingHandler:
    def execute(self, work, cancellation):
        raise RuntimeError("late failure")


class BlockingHandler:
    def __init__(self, release: Event) -> None:
        self._release = release

    def execute(self, work, cancellation):
        self._release.wait()
        raise RuntimeError("late failure")


def test_runner_denies_a_second_reservation_until_the_first_is_released() -> None:
    runner = FixedCapacityThreadAttemptRunner(max_concurrency=1)

    first = runner.try_reserve()

    assert first is not None
    assert runner.try_reserve() is None

    first.release()
    second = runner.try_reserve()

    assert second is not None
    second.release()


def test_releasing_a_permit_twice_does_not_create_extra_capacity() -> None:
    runner = FixedCapacityThreadAttemptRunner(max_concurrency=1)
    first = runner.try_reserve()

    assert first is not None
    first.release()
    first.release()

    second = runner.try_reserve()

    assert second is not None
    assert runner.try_reserve() is None
    second.release()


def test_runner_publishes_handler_exception_and_releases_after_thread_exit() -> None:
    runner = FixedCapacityThreadAttemptRunner(max_concurrency=1)
    permit = runner.try_reserve()

    assert permit is not None
    running = permit.start(RaisingHandler(), None, Cancellation(), FixedClock())
    running.wait_until(1.0)

    completion = running.completion()
    assert completion is not None
    assert completion.completed_at == 7.0
    assert completion.result == HandlerRaised()
    assert runner.try_reserve() is not None


def test_detached_work_retains_capacity_until_its_thread_physically_exits() -> None:
    runner = FixedCapacityThreadAttemptRunner(max_concurrency=1)
    release = Event()
    permit = runner.try_reserve()

    assert permit is not None
    running = permit.start(BlockingHandler(release), None, Cancellation(), FixedClock())
    running.detach()
    assert runner.try_reserve() is None

    release.set()
    running.wait_until(1.0)

    assert running.completion() is not None
    assert runner.try_reserve() is not None
