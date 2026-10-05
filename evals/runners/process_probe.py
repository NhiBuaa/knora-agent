"""Evaluation-only supervisor; terminate only the child created for this call."""

import asyncio
import multiprocessing
import queue
import threading
from contextlib import suppress
from time import monotonic

INVALID_OUTPUT_STAGES = frozenset(
    {
        "EXTRACTION_CONTRACT",
        "EXTRACTION_FIELDS",
        "SOURCE_ALIAS",
        "SOURCE_QUOTE",
        "RESPONSE_ENVELOPE",
        "EXTRACTION_JSON",
    }
)


def safe_invalid_output_stage(value):
    return value if isinstance(value, str) and value in INVALID_OUTPUT_STAGES else None


def run_process(worker, arguments, *, deadline_seconds=240, cancellation=None):
    if isinstance(deadline_seconds, bool) or not 0 < deadline_seconds <= 240:
        raise ValueError("invalid process deadline")
    cancellation = cancellation if cancellation is not None else threading.Event()
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=worker, args=(sender, arguments), daemon=True)
    observed = {
        "result": None,
        "error": "PROVIDER_REQUEST_FAILED",
        "requests": [],
        "deadline_expired": False,
        "supervisor_failed": False,
        "runtime_sources": None,
    }
    started = monotonic()
    process_started = False
    messages = queue.Queue(maxsize=4)
    reader = None

    def receive():
        try:
            while True:
                messages.put(receiver.recv(), timeout=0.05)
        except (EOFError, OSError, queue.Full):
            with suppress(queue.Full):
                messages.put(None, timeout=0.05)

    try:
        process.start()
        process_started = True
        sender.close()
        reader = threading.Thread(target=receive, daemon=True)
        reader.start()
        while not cancellation.is_set():
            remaining = deadline_seconds - (monotonic() - started)
            if remaining <= 0:
                observed["deadline_expired"] = True
                break
            try:
                message = messages.get(timeout=min(remaining, 0.05))
            except queue.Empty:
                continue
            if message is None:
                break
            if message["kind"] == "runtime":
                observed["runtime_sources"] = message["runtime_sources"]
            elif message["kind"] == "request":
                observed["requests"].append(message["observation"])
            elif message["kind"] == "result":
                observed.update(result=message["result"], error=None)
                break
            elif message["kind"] == "error":
                observed["error"] = (
                    "GENERATION_OUTPUT_INVALID"
                    if message.get("error") == "GENERATION_OUTPUT_INVALID"
                    else "PROVIDER_REQUEST_FAILED"
                )
                if observed["error"] == "GENERATION_OUTPUT_INVALID":
                    observed["invalid_output_stage"] = safe_invalid_output_stage(
                        message.get("invalid_output_stage")
                    )
                break
    except (EOFError, OSError, KeyError, TypeError):
        pass
    finally:
        try:
            if process_started:
                process.join(timeout=0.05)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=0.2)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=0.2)
                observed["supervisor_failed"] = process.is_alive()
        except Exception:
            observed["supervisor_failed"] = True
        finally:
            for endpoint in (sender, receiver):
                try:
                    endpoint.close()
                except Exception:
                    observed["supervisor_failed"] = True
            try:
                if reader is not None:
                    reader.join(timeout=0.2)
                    if reader.is_alive():
                        observed["supervisor_failed"] = True
            finally:
                try:
                    process.close()
                except Exception:
                    observed["supervisor_failed"] = True
    observed["elapsed_seconds"] = monotonic() - started
    if observed["elapsed_seconds"] > deadline_seconds:
        observed.update(deadline_expired=True, result=None, error="PROVIDER_REQUEST_FAILED")
    if observed["supervisor_failed"]:
        observed.update(result=None, error="PROVIDER_REQUEST_FAILED")
    return observed


async def run_process_async(worker, arguments, *, deadline_seconds=240):
    cancellation = threading.Event()
    task = asyncio.create_task(
        asyncio.to_thread(
            run_process,
            worker,
            arguments,
            deadline_seconds=deadline_seconds,
            cancellation=cancellation,
        )
    )
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        cancellation.set()
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        task.result()
        raise
