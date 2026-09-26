"""Run the durable PDF ingestion worker in the configured local runtime."""

from __future__ import annotations

import argparse
import asyncio
import multiprocessing
import os
import socket
import sys
from uuid import uuid4

import psutil

from knora.ingestion.job_processing import NoEligibleJob


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process queued Knora PDF ingestion jobs")
    parser.add_argument("--once", action="store_true", help="Process one eligible job and exit")
    parser.add_argument(
        "--profile-id", action="store_true", help="Print the resolved embedding profile ID and exit"
    )
    parser.add_argument("--poll-seconds", type=float, default=2.0)
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


async def run_worker(*, once: bool, poll_seconds: float) -> None:
    if poll_seconds <= 0:
        raise ValueError("poll interval must be positive")
    from knora.main import app

    worker_id = f"{socket.gethostname()}:{uuid4().hex[:8]}"
    async with app.router.lifespan_context(app):
        while True:
            result = await asyncio.to_thread(app.state.ingestion_worker.run_once, worker_id)
            if once:
                return
            if isinstance(result, NoEligibleJob):
                await asyncio.sleep(poll_seconds)


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
    asyncio.run(run_worker(once=args.once, poll_seconds=args.poll_seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
