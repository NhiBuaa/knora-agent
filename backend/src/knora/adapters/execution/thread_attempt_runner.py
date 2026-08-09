"""Fixed-capacity thread execution for bounded ingestion attempts."""

from __future__ import annotations

from threading import Event, Lock, Semaphore, Thread

from knora.ingestion.job_processing import (
    AttemptCompletion,
    CancellationToken,
    HandlerRaised,
    IngestionWork,
    MonotonicClock,
    WorkHandler,
)


class FixedCapacityThreadAttemptRunner:
    """Reserve a thread slot before claim and retain it through physical handler exit."""

    def __init__(self, *, max_concurrency: int) -> None:
        if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int):
            raise ValueError("max_concurrency must be a positive integer")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be a positive integer")
        self._permits = Semaphore(max_concurrency)

    def try_reserve(self) -> ThreadExecutionPermit | None:
        if not self._permits.acquire(blocking=False):
            return None
        return ThreadExecutionPermit(self._permits)


class ThreadExecutionPermit:
    def __init__(self, permits: Semaphore) -> None:
        self._permits = permits
        self._released = False
        self._lock = Lock()

    def start(
        self,
        handler: WorkHandler,
        work: IngestionWork,
        cancellation: CancellationToken,
        monotonic_clock: MonotonicClock,
    ) -> ThreadRunningAttempt:
        running = ThreadRunningAttempt()

        def execute() -> None:
            try:
                result = handler.execute(work, cancellation)
            except BaseException:
                result = HandlerRaised()
            running.publish(AttemptCompletion(monotonic_clock.now(), result))
            self.release()

        try:
            Thread(target=execute, daemon=True).start()
        except BaseException:
            raise
        return running

    def release(self) -> None:
        with self._lock:
            if self._released:
                return
            self._released = True
            self._permits.release()


class ThreadRunningAttempt:
    def __init__(self) -> None:
        self._completion: AttemptCompletion | None = None
        self._completed = Event()
        self._lock = Lock()
        self._detached = False

    def publish(self, completion: AttemptCompletion) -> None:
        with self._lock:
            self._completion = completion
            self._completed.set()

    def completion(self) -> AttemptCompletion | None:
        with self._lock:
            return self._completion

    def wait_until(self, deadline: float) -> None:
        # The supervisor scheduler owns deterministic time; this is only wakeable.
        self._completed.wait(timeout=max(0.0, deadline))

    def detach(self) -> None:
        with self._lock:
            self._detached = True


class ThreadAttemptScheduler:
    """Wake a supervisor when a thread completes or its next local deadline arrives."""

    def __init__(self, monotonic_clock: MonotonicClock) -> None:
        self._monotonic_clock = monotonic_clock

    def wait_until(self, attempt: ThreadRunningAttempt, deadline: float) -> None:
        attempt.wait_until(max(0.0, deadline - self._monotonic_clock.now()))
