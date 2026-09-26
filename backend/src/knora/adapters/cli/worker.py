"""Run the durable PDF ingestion worker in the configured local runtime."""

from __future__ import annotations

import argparse
import asyncio
import multiprocessing
import os
import socket
import sys
from pathlib import Path
from uuid import uuid4

import psutil

from knora.ingestion.job_processing import NoEligibleJob

DEV_RESTART_EXIT_CODE = 75


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process queued Knora PDF ingestion jobs")
    parser.add_argument("--once", action="store_true", help="Process one eligible job and exit")
    parser.add_argument(
        "--profile-id", action="store_true", help="Print the resolved embedding profile ID and exit"
    )
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument(
        "--dev-watch",
        action="store_true",
        help="Restart cleanly after Python source changes, but only between ingestion jobs",
    )
    parser.add_argument(
        "--watch-seconds",
        type=float,
        default=0.25,
        help="Polling interval for --dev-watch source detection",
    )
    parser.add_argument(
        "--watch-root",
        type=Path,
        help="Override the Python source root watched by --dev-watch",
    )
    parser.add_argument(
        "--check-pdf-isolation",
        action="store_true",
        help="Verify the Windows PDF child memory limit before starting work",
    )
    return parser


def _allocate_over_limit(connection) -> None:
    """Child used only by the local hard-limit preflight."""
    try:
        connection.send("ready")
        if connection.recv() != "start":
            return
        payload = bytearray(384 * 1024 * 1024)
        for offset in range(0, len(payload), 4096):
            payload[offset] = 1
        connection.send("allocated")
    except MemoryError:
        connection.send("limited")
    except (BrokenPipeError, EOFError, OSError):
        pass
    finally:
        connection.close()


def prove_windows_pdf_memory_limit() -> bool:
    """Prove that a Job Object blocks a child exceeding the PDF 256 MiB budget."""
    if os.name != "nt" or psutil.virtual_memory().available < 768 * 1024 * 1024:
        return False
    from knora.adapters.pdf import _pypdf_process
    from knora.ingestion.pdf import PdfExtractionConfiguration

    limit = PdfExtractionConfiguration.milestone_two().extractor_memory_bytes
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    process = context.Process(target=_allocate_over_limit, args=(child,), daemon=True)
    handle = None
    try:
        process.start()
        child.close()
        if not parent.poll(10) or parent.recv() != "ready":
            return False
        handle = _pypdf_process._install_windows_memory_limit(process, limit)
        if handle is None:
            return False
        parent.send("start")
        result = None
        try:
            if parent.poll(20):
                result = parent.recv()
        except (EOFError, OSError):
            pass
        process.join(timeout=2)
        return result == "limited" or (
            result is None and _pypdf_process._hard_memory_limit_triggered(handle, limit)
        )
    except (OSError, ValueError):
        return False
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
        parent.close()
        child.close()
        _pypdf_process._close_windows_handle(handle)


def check_pdf_isolation() -> bool:
    """Exercise the real extractor path, including its hard child memory limit."""
    if os.name != "nt":
        return False
    if not prove_windows_pdf_memory_limit():
        return False
    from io import BytesIO

    from pypdf import PdfWriter

    from knora.adapters.pdf.pypdf import PypdfTextExtractor
    from knora.ingestion.pdf import PdfExtractionConfiguration, PdfExtractionError

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    source = BytesIO()
    writer.write(source)
    source.seek(0)
    try:
        PypdfTextExtractor().extract(source, PdfExtractionConfiguration.milestone_two())
    except PdfExtractionError as error:
        return error.code == "PDF_TEXT_INSUFFICIENT"
    return True


def _default_watch_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _python_source_snapshot(root: Path) -> tuple[tuple[str, int, int], ...]:
    """Return a stable source fingerprint without reading source contents."""
    entries: list[tuple[str, int, int]] = []
    for path in root.rglob("*.py"):
        try:
            stat = path.stat()
        except OSError:
            continue
        entries.append((path.relative_to(root).as_posix(), stat.st_mtime_ns, stat.st_size))
    return tuple(sorted(entries))


async def _watch_python_sources(
    *,
    root: Path,
    baseline: tuple[tuple[str, int, int], ...],
    restart_requested: asyncio.Event,
    watch_seconds: float,
) -> None:
    while not restart_requested.is_set():
        await asyncio.sleep(watch_seconds)
        if _python_source_snapshot(root) != baseline:
            print("WORKER_RESTART_REQUESTED", flush=True)
            restart_requested.set()
            return


async def run_worker(
    *,
    once: bool,
    poll_seconds: float,
    dev_watch: bool = False,
    watch_seconds: float = 0.25,
    watch_root: Path | None = None,
    application=None,
) -> bool:
    """Run jobs and return True only when a dev source change requests restart."""
    if poll_seconds <= 0:
        raise ValueError("poll interval must be positive")
    if dev_watch and watch_seconds <= 0:
        raise ValueError("watch interval must be positive")

    if application is None:
        from knora.main import app as application

    root = (watch_root or _default_watch_root()).resolve()
    baseline = _python_source_snapshot(root) if dev_watch else ()
    restart_requested = asyncio.Event()
    watch_task: asyncio.Task[None] | None = None
    if dev_watch:
        watch_task = asyncio.create_task(
            _watch_python_sources(
                root=root,
                baseline=baseline,
                restart_requested=restart_requested,
                watch_seconds=watch_seconds,
            )
        )

    worker_id = f"{socket.gethostname()}:{uuid4().hex[:8]}"
    try:
        async with application.router.lifespan_context(application):
            while True:
                result = await asyncio.to_thread(application.state.ingestion_worker.run_once, worker_id)
                if once:
                    return False

                if dev_watch:
                    # Recheck synchronously at the safe job boundary so a busy worker never
                    # claims another job after code has changed but before the watcher wakes.
                    if _python_source_snapshot(root) != baseline:
                        if not restart_requested.is_set():
                            print("WORKER_RESTART_REQUESTED", flush=True)
                        restart_requested.set()
                    if restart_requested.is_set():
                        print("WORKER_DRAINED_FOR_RESTART", flush=True)
                        return True

                if isinstance(result, NoEligibleJob):
                    if dev_watch:
                        try:
                            await asyncio.wait_for(restart_requested.wait(), timeout=poll_seconds)
                        except TimeoutError:
                            continue
                        print("WORKER_DRAINED_FOR_RESTART", flush=True)
                        return True
                    await asyncio.sleep(poll_seconds)
    finally:
        if watch_task is not None:
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass


def main() -> int:
    args = build_parser().parse_args()
    if args.check_pdf_isolation:
        if not check_pdf_isolation():
            print("PDF_ISOLATION_UNAVAILABLE", file=sys.stderr)
            return 2
        print("PDF_ISOLATION_OK")
        return 0
    if args.profile_id:
        from knora.main import app

        print(app.state.embedding_configuration.id)
        return 0
    restart_requested = asyncio.run(
        run_worker(
            once=args.once,
            poll_seconds=args.poll_seconds,
            dev_watch=args.dev_watch,
            watch_seconds=args.watch_seconds,
            watch_root=args.watch_root,
        )
    )
    return DEV_RESTART_EXIT_CODE if restart_requested else 0


if __name__ == "__main__":
    raise SystemExit(main())
