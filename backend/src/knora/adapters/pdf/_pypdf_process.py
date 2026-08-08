from __future__ import annotations

import ctypes
import multiprocessing
import os
import sys
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from multiprocessing.connection import Connection
from pathlib import Path

import psutil

from knora.ingestion.pdf import PdfExtractionConfiguration, PdfExtractionError

_IPC_CHUNK_CHARACTERS = 64 * 1024
_MONITOR_INTERVAL_SECONDS = 0.01


class _MemoryLimitUnavailable(RuntimeError):
    """The host cannot install the extractor's hard process memory limit."""


@dataclass(frozen=True, slots=True)
class _CgroupMemoryLimit:
    path: Path
    initial_pressure_events: int


@dataclass(frozen=True, slots=True)
class _RawPage:
    page_number: int
    text: str


if os.name == "nt":
    _PROCESS_SET_QUOTA = 0x0100
    _PROCESS_TERMINATE = 0x0001
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x0100

    class _JobObjectBasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("per_process_user_time_limit", ctypes.c_longlong),
            ("per_job_user_time_limit", ctypes.c_longlong),
            ("limit_flags", ctypes.c_uint32),
            ("minimum_working_set_size", ctypes.c_size_t),
            ("maximum_working_set_size", ctypes.c_size_t),
            ("active_process_limit", ctypes.c_uint32),
            ("affinity", ctypes.c_size_t),
            ("priority_class", ctypes.c_uint32),
            ("scheduling_class", ctypes.c_uint32),
        ]

    class _JobObjectExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("basic_limit_information", _JobObjectBasicLimitInformation),
            ("io_info", ctypes.c_ulonglong * 6),
            ("process_memory_limit", ctypes.c_size_t),
            ("job_memory_limit", ctypes.c_size_t),
            ("peak_process_memory_used", ctypes.c_size_t),
            ("peak_job_memory_used", ctypes.c_size_t),
        ]


def _install_windows_memory_limit_for_pid(
    process_id: int,
    memory_limit: int,
) -> int | None:
    if os.name != "nt":
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    open_process.restype = ctypes.c_void_p
    create_job = kernel32.CreateJobObjectW
    create_job.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    create_job.restype = ctypes.c_void_p
    set_information = kernel32.SetInformationJobObject
    set_information.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    set_information.restype = ctypes.c_int
    assign_process = kernel32.AssignProcessToJobObject
    assign_process.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    assign_process.restype = ctypes.c_int
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_int

    process_handle = open_process(
        _PROCESS_SET_QUOTA
        | _PROCESS_TERMINATE
        | _PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        process_id,
    )
    if not process_handle:
        error = ctypes.get_last_error()
        raise OSError(error, "OpenProcess failed")
    job_handle = create_job(None, None)
    if not job_handle:
        error = ctypes.get_last_error()
        close_handle(process_handle)
        raise OSError(error, "CreateJobObjectW failed")
    try:
        information = _JobObjectExtendedLimitInformation()
        information.basic_limit_information.limit_flags = _JOB_OBJECT_LIMIT_PROCESS_MEMORY
        information.process_memory_limit = memory_limit
        if not set_information(
            job_handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            error = ctypes.get_last_error()
            raise OSError(error, "SetInformationJobObject failed")
        if not assign_process(job_handle, process_handle):
            error = ctypes.get_last_error()
            raise OSError(error, "AssignProcessToJobObject failed")
        return int(job_handle)
    except BaseException:
        close_handle(job_handle)
        raise
    finally:
        close_handle(process_handle)


def _install_windows_memory_limit(
    process: multiprocessing.Process,
    memory_limit: int,
) -> int | None:
    if process.pid is None:
        raise _MemoryLimitUnavailable("child process has no PID")
    return _install_windows_memory_limit_for_pid(process.pid, memory_limit)


def _close_windows_handle(handle: int | None) -> None:
    if handle is None or os.name != "nt":
        return
    with suppress(Exception):
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)


def _windows_job_memory_limit_triggered(handle: int, memory_limit: int) -> bool:
    if os.name != "nt":
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    query_information = kernel32.QueryInformationJobObject
    query_information.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    query_information.restype = ctypes.c_int
    information = _JobObjectExtendedLimitInformation()
    returned_length = ctypes.c_uint32()
    if not query_information(
        handle,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(information),
        ctypes.sizeof(information),
        ctypes.byref(returned_length),
    ):
        return False
    return information.peak_process_memory_used >= memory_limit


def _cgroup_memory_pressure_events(path: Path) -> int:
    try:
        values = {}
        for line in (path / "memory.events").read_text(encoding="ascii").splitlines():
            name, value = line.split(maxsplit=1)
            values[name] = int(value)
    except (OSError, ValueError):
        return 0
    return sum(values.get(name, 0) for name in ("max", "oom", "oom_kill", "oom_group_kill"))


def _install_posix_memory_limit(
    process: multiprocessing.Process,
    memory_limit: int,
) -> _CgroupMemoryLimit:
    if os.name == "nt" or sys.platform != "linux":
        raise _MemoryLimitUnavailable("Linux cgroup v2 memory limits are unavailable")
    if process.pid is None:
        raise _MemoryLimitUnavailable("child process has no PID")

    root = Path("/sys/fs/cgroup")
    try:
        controllers = (root / "cgroup.controllers").read_text(encoding="ascii").split()
        if "memory" not in controllers or not (root / "memory.max").is_file():
            raise _MemoryLimitUnavailable("Linux cgroup v2 memory controller is unavailable")
    except _MemoryLimitUnavailable:
        raise
    except (OSError, UnicodeError) as error:
        raise _MemoryLimitUnavailable("Linux cgroup v2 memory controller is unavailable") from error

    cgroup = root / f"knora-pdf-{os.getpid()}-{process.pid}-{uuid.uuid4().hex}"
    try:
        cgroup.mkdir()
        memory_max = cgroup / "memory.max"
        if not memory_max.is_file():
            raise _MemoryLimitUnavailable("Linux cgroup v2 memory controller is not delegated")
        memory_max.write_text(str(memory_limit), encoding="ascii")
        if memory_max.read_text(encoding="ascii").strip() != str(memory_limit):
            raise _MemoryLimitUnavailable("Linux cgroup v2 memory limit was not enforced")
        swap_max = cgroup / "memory.swap.max"
        if swap_max.is_file():
            swap_max.write_text("0", encoding="ascii")
        initial_pressure_events = _cgroup_memory_pressure_events(cgroup)
        (cgroup / "cgroup.procs").write_text(str(process.pid), encoding="ascii")
        return _CgroupMemoryLimit(cgroup, initial_pressure_events)
    except _MemoryLimitUnavailable:
        with suppress(OSError):
            cgroup.rmdir()
        raise
    except (OSError, UnicodeError, ValueError) as error:
        with suppress(OSError):
            cgroup.rmdir()
        raise _MemoryLimitUnavailable(
            "Linux cgroup v2 memory limit could not be installed"
        ) from error


def _install_child_posix_memory_limit(memory_limit: int) -> None:
    if os.name == "nt":
        return
    try:
        import resource

        current_soft, current_hard = resource.getrlimit(resource.RLIMIT_AS)
    except (ImportError, AttributeError, OSError, ValueError) as error:
        raise _MemoryLimitUnavailable("POSIX address-space limits are unavailable") from error
    infinity = getattr(resource, "RLIM_INFINITY", -1)
    hard_limit = memory_limit if current_hard == infinity else min(current_hard, memory_limit)
    soft_limit = hard_limit if current_soft == infinity else min(current_soft, hard_limit)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (soft_limit, hard_limit))
        installed_soft, installed_hard = resource.getrlimit(resource.RLIMIT_AS)
    except (OSError, ValueError) as error:
        raise _MemoryLimitUnavailable("POSIX address-space limit could not be installed") from error
    if installed_soft > memory_limit or installed_hard > memory_limit:
        raise _MemoryLimitUnavailable("POSIX address-space limit was not enforced")


def _install_hard_memory_limit(
    process: multiprocessing.Process,
    memory_limit: int,
) -> int | _CgroupMemoryLimit | None:
    if os.name == "nt":
        return _install_windows_memory_limit(process, memory_limit)
    return _install_posix_memory_limit(process, memory_limit)


def _hard_memory_limit_triggered(
    handle: int | _CgroupMemoryLimit | None,
    memory_limit: int,
) -> bool:
    if isinstance(handle, _CgroupMemoryLimit):
        return _cgroup_memory_pressure_events(handle.path) > handle.initial_pressure_events
    if isinstance(handle, int) and os.name == "nt":
        return _windows_job_memory_limit_triggered(handle, memory_limit)
    return False


def _close_memory_limit(handle: int | _CgroupMemoryLimit | None) -> None:
    if isinstance(handle, _CgroupMemoryLimit):
        with suppress(OSError):
            handle.path.rmdir()
        return
    _close_windows_handle(handle)


def _child_send(connection: Connection, message: tuple, *, wait_for_ack: bool = False) -> None:
    connection.send(message)
    if not wait_for_ack:
        return
    try:
        connection.recv()
    except (EOFError, OSError):
        return


def _child_send_page(connection: Connection, page: _RawPage) -> None:
    text = page.text
    if not text:
        connection.send(("page", page.page_number, 0, "", True))
        return
    for offset in range(0, len(text), _IPC_CHUNK_CHARACTERS):
        end = min(offset + _IPC_CHUNK_CHARACTERS, len(text))
        connection.send(("page", page.page_number, offset, text[offset:end], end == len(text)))


def _child_entrypoint(
    target: Callable[[str, PdfExtractionConfiguration, Connection], None],
    pdf_path: str,
    configuration: PdfExtractionConfiguration,
    connection: Connection,
) -> None:
    try:
        _install_child_posix_memory_limit(configuration.extractor_memory_bytes)
        try:
            command = connection.recv()
        except (EOFError, OSError):
            return
        if command != ("start",):
            _child_send(
                connection,
                ("error", "PDF_EXTRACTOR_UNAVAILABLE", "CHILD_CRASH", True),
            )
            return
        target(pdf_path, configuration, connection)
    except MemoryError:
        _child_send(
            connection,
            ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "EXTRACTOR_MEMORY", False),
        )
    except (_MemoryLimitUnavailable, OSError):
        _child_send(
            connection,
            ("error", "PDF_EXTRACTOR_UNAVAILABLE", "CHILD_CRASH", True),
        )
    finally:
        with suppress(Exception):
            connection.close()


def _extract_in_child(
    path: Path,
    configuration: PdfExtractionConfiguration,
    child_target: Callable[[str, PdfExtractionConfiguration, Connection], None],
) -> tuple[_RawPage, ...]:
    context = multiprocessing.get_context("spawn")
    parent: Connection | None = None
    child: Connection | None = None
    process: multiprocessing.Process | None = None
    memory_limit_handle: int | _CgroupMemoryLimit | None = None
    raw_pages: tuple[_RawPage, ...] | None = None
    terminal_error: tuple | None = None
    peak_memory = 0
    try:
        parent, child = context.Pipe(duplex=True)
        process = context.Process(
            target=_child_entrypoint,
            args=(child_target, str(path), configuration, child),
            daemon=True,
        )
        started = time.monotonic()
        deadline = started + configuration.extraction_timeout_seconds
        process.start()
        child.close()
        child = None
        monitored = psutil.Process(process.pid)

        def heartbeat() -> int:
            nonlocal peak_memory
            peak_memory = max(peak_memory, _check_memory(monitored, process, configuration))
            return peak_memory

        heartbeat()
        memory_limit_handle = _install_hard_memory_limit(
            process,
            configuration.extractor_memory_bytes,
        )
        try:
            parent.send(("start",))
        except (BrokenPipeError, EOFError, OSError) as error:
            _stop(process)
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason="CHILD_CRASH",
                retryable=True,
            ) from error
        message = _receive_message(parent, deadline, process, heartbeat=heartbeat)
        if message[0] == "error":
            terminal_error = message
        elif message[0] == "ok_start":
            raw_pages = _receive_pages(parent, message, deadline, heartbeat)
            heartbeat()
            try:
                parent.send(True)
            except (BrokenPipeError, EOFError, OSError) as error:
                _stop(process)
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CHILD_CRASH",
                    retryable=True,
                ) from error
        else:
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason="CHILD_CRASH",
                retryable=True,
            )
    except PdfExtractionError as error:
        if (
            error.code == "PDF_EXTRACTOR_UNAVAILABLE"
            and error.reason == "CHILD_CRASH"
            and (
                peak_memory >= int(configuration.extractor_memory_bytes * 0.9)
                or _hard_memory_limit_triggered(
                    memory_limit_handle,
                    configuration.extractor_memory_bytes,
                )
            )
        ):
            raise PdfExtractionError(
                "PDF_RESOURCE_LIMIT_EXCEEDED",
                reason="EXTRACTOR_MEMORY",
            ) from error
        raise
    except Exception as error:
        if process is not None:
            _stop(process)
        raise PdfExtractionError(
            "PDF_EXTRACTOR_UNAVAILABLE",
            reason="CHILD_CRASH",
            retryable=True,
        ) from error
    finally:
        if child is not None:
            with suppress(Exception):
                child.close()
        if parent is not None:
            with suppress(Exception):
                parent.close()
        if process is not None and process.pid is not None:
            process.join(timeout=1)
            if process.is_alive():
                _stop(process)
        _close_memory_limit(memory_limit_handle)

    if terminal_error is not None:
        _raise_child_error(terminal_error)
    if raw_pages is None:
        raise PdfExtractionError(
            "PDF_EXTRACTOR_UNAVAILABLE",
            reason="CHILD_CRASH",
            retryable=True,
        )
    return raw_pages


def _raise_child_error(message: tuple) -> None:
    if (
        len(message) != 4
        or not isinstance(message[1], str)
        or not isinstance(message[2], str)
        or not isinstance(message[3], bool)
    ):
        raise PdfExtractionError(
            "PDF_EXTRACTOR_UNAVAILABLE",
            reason="CHILD_CRASH",
            retryable=True,
        )
    _, code, reason, retryable = message
    raise PdfExtractionError(code, reason=reason, retryable=retryable)


def _receive_message(
    connection: Connection,
    deadline: float | None = None,
    process: multiprocessing.Process | None = None,
    heartbeat: Callable[[], object] | None = None,
) -> tuple:
    if deadline is None:
        try:
            return connection.recv()
        except (EOFError, OSError) as error:
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason="CHILD_CRASH",
                retryable=True,
            ) from error
    while True:
        if heartbeat is not None:
            heartbeat()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PdfExtractionError(
                "PDF_RESOURCE_LIMIT_EXCEEDED",
                reason="EXTRACTION_TIMEOUT",
            )
        try:
            available = connection.poll(min(_MONITOR_INTERVAL_SECONDS, remaining))
        except (EOFError, OSError) as error:
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason="CHILD_CRASH",
                retryable=True,
            ) from error
        if available:
            if heartbeat is not None:
                heartbeat()
            if time.monotonic() >= deadline:
                raise PdfExtractionError(
                    "PDF_RESOURCE_LIMIT_EXCEEDED",
                    reason="EXTRACTION_TIMEOUT",
                )
            try:
                message = connection.recv()
            except (EOFError, OSError) as error:
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CHILD_CRASH",
                    retryable=True,
                ) from error
            if heartbeat is not None:
                heartbeat()
            if time.monotonic() >= deadline:
                raise PdfExtractionError(
                    "PDF_RESOURCE_LIMIT_EXCEEDED",
                    reason="EXTRACTION_TIMEOUT",
                )
            return message
        if process is not None and not process.is_alive():
            try:
                if not connection.poll(0):
                    raise PdfExtractionError(
                        "PDF_EXTRACTOR_UNAVAILABLE",
                        reason="CHILD_CRASH",
                        retryable=True,
                    )
            except (EOFError, OSError) as error:
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CHILD_CRASH",
                    retryable=True,
                ) from error


def _receive_pages(
    connection: Connection,
    start_message: tuple,
    deadline: float,
    heartbeat: Callable[[], object],
) -> tuple[_RawPage, ...]:
    if len(start_message) != 2 or not isinstance(start_message[1], int):
        raise PdfExtractionError(
            "PDF_EXTRACTOR_UNAVAILABLE",
            reason="CHILD_CRASH",
            retryable=True,
        )
    expected_pages = start_message[1]
    pages: list[_RawPage] = []
    current_page: int | None = None
    current_offset = 0
    current_chunks: list[str] = []
    while True:
        heartbeat()
        message = _receive_message(connection, deadline, heartbeat=heartbeat)
        if message[0] == "error":
            _raise_child_error(message)
        if message[0] == "page":
            if len(message) != 5 or not isinstance(message[1], int):
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CHILD_CRASH",
                    retryable=True,
                )
            _, page_number, offset, text, is_last = message
            if (
                not isinstance(offset, int)
                or not isinstance(text, str)
                or not isinstance(is_last, bool)
                or page_number < 1
                or offset != current_offset
                or (current_page is None and page_number != len(pages) + 1)
                or (current_page is not None and page_number != current_page)
            ):
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CHILD_CRASH",
                    retryable=True,
                )
            if current_page is None:
                current_page = page_number
                current_chunks = []
            current_chunks.append(text)
            current_offset += len(text)
            if is_last:
                pages.append(_RawPage(current_page, "".join(current_chunks)))
                current_page = None
                current_offset = 0
                current_chunks = []
            continue
        if message[0] == "ok_end":
            if current_page is not None or len(pages) != expected_pages:
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CHILD_CRASH",
                    retryable=True,
                )
            return tuple(pages)
        raise PdfExtractionError(
            "PDF_EXTRACTOR_UNAVAILABLE",
            reason="CHILD_CRASH",
            retryable=True,
        )


def _check_memory(
    monitored: psutil.Process,
    process: multiprocessing.Process,
    configuration: PdfExtractionConfiguration,
) -> int:
    try:
        info = monitored.memory_info()
    except psutil.NoSuchProcess:
        return 0
    high_water = max(info.rss, getattr(info, "peak_wset", 0))
    if high_water > configuration.extractor_memory_bytes:
        _stop(process)
        raise PdfExtractionError(
            "PDF_RESOURCE_LIMIT_EXCEEDED",
            reason="EXTRACTOR_MEMORY",
        )
    return high_water


def _stop(process: multiprocessing.Process) -> None:
    try:
        alive = process.is_alive()
    except AssertionError:
        return
    if alive:
        process.terminate()
        process.join(timeout=1)
    if process.is_alive():
        process.kill()
        process.join(timeout=1)
