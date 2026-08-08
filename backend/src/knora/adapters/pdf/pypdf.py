from __future__ import annotations

import ctypes
import hashlib
import logging
import multiprocessing
import os
import re
import sys
import tempfile
import time
import unicodedata
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from itertools import chain
from multiprocessing.connection import Connection
from pathlib import Path
from typing import BinaryIO

import psutil
import tiktoken
from pypdf import PdfReader
from pypdf.errors import (
    DependencyError,
    FileNotDecryptedError,
    LimitReachedError,
    ParseError,
    PdfReadError,
    PyPdfError,
)

from knora.ingestion.pdf import (
    NormalizedPdfPage,
    PdfExtractionConfiguration,
    PdfExtractionError,
    PdfExtractionResult,
    PreparedPdfChunk,
)

_COPY_BUFFER_BYTES = 64 * 1024
_IPC_CHUNK_CHARACTERS = 64 * 1024
_MONITOR_INTERVAL_SECONDS = 0.01
_CONTROL_WHITELIST = {"\n", "\t"}
_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\n]+")
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")
_PYPDF_OUTPUT_LIMITS = (
    "FLATE_MAX_BUFFER_SIZE",
    "JBIG2_MAX_OUTPUT_LENGTH",
    "LZW_MAX_OUTPUT_LENGTH",
    "MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH",
    "RUN_LENGTH_MAX_OUTPUT_LENGTH",
    "ZLIB_MAX_OUTPUT_LENGTH",
)


class _PageStreamBudgetExceeded(Exception):
    """A decompressed page/form stream exceeded a configured inspection budget."""

    def __init__(self, reason: str = "PAGE_STREAM_SIZE") -> None:
        super().__init__(reason)
        self.reason = reason


class _MemoryLimitUnavailable(RuntimeError):
    """The host cannot install the extractor's hard process memory limit."""


@dataclass(frozen=True, slots=True)
class _CgroupMemoryLimit:
    path: Path
    initial_pressure_events: int


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
    hard_limit = (
        memory_limit
        if current_hard == infinity
        else min(current_hard, memory_limit)
    )
    soft_limit = (
        hard_limit
        if current_soft == infinity
        else min(current_soft, hard_limit)
    )
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


@contextmanager
def _pypdf_output_limit(max_output_bytes: int) -> Iterator[None]:
    if max_output_bytes <= 0:
        raise _PageStreamBudgetExceeded
    import pypdf.filters as filters

    previous: dict[str, int] = {}
    try:
        for name in _PYPDF_OUTPUT_LIMITS:
            if not hasattr(filters, name):
                continue
            current = int(getattr(filters, name))
            previous[name] = current
            setattr(
                filters,
                name,
                max_output_bytes if current == 0 else min(current, max_output_bytes),
            )
        yield
    finally:
        for name, value in previous.items():
            setattr(filters, name, value)


def _stream_objects(value: object) -> Iterator[object]:
    if value is None:
        return
    value = value.get_object() if hasattr(value, "get_object") else value
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _stream_objects(item)
        return
    if hasattr(value, "get_data"):
        yield value
        return
    raise AttributeError("PDF content is not a stream")


def _decoded_stream_bytes(value: object, max_output_bytes: int) -> int:
    if max_output_bytes < 0:
        raise _PageStreamBudgetExceeded
    total = 0
    for stream in _stream_objects(value):
        remaining = max_output_bytes - total
        if remaining < 0:
            raise _PageStreamBudgetExceeded
        raw_data = getattr(stream, "_data", None)
        filters = stream.get("/Filter") if hasattr(stream, "get") else None
        if (
            filters is None
            and isinstance(raw_data, (bytes, bytearray, memoryview))
            and len(raw_data) > remaining
        ):
            raise _PageStreamBudgetExceeded
        if (
            filters is None
            and isinstance(raw_data, (bytes, bytearray, memoryview))
            and not raw_data
        ):
            continue
        try:
            with _pypdf_output_limit(max(1, remaining)):
                decoded = stream.get_data()
        except LimitReachedError as error:
            raise _PageStreamBudgetExceeded from error
        if len(decoded) > remaining:
            raise _PageStreamBudgetExceeded
        total += len(decoded)
    return total


@dataclass(frozen=True, slots=True)
class _RawPage:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class _Block:
    start: int
    end: int
    token_count: int


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
    target,
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


def _object_identity(value: object) -> tuple[str, int]:
    reference = getattr(value, "indirect_reference", None)
    identifier = getattr(reference, "idnum", None)
    return ("reference", identifier) if identifier is not None else ("object", id(value))


def _nested_form_streams(
    resources: object,
    visited: set[tuple[str, int]],
) -> Iterator[object]:
    if resources is None:
        return
    resources = resources.get_object() if hasattr(resources, "get_object") else resources
    xobjects = resources.get("/XObject") if hasattr(resources, "get") else None
    if xobjects is None:
        return
    xobjects = xobjects.get_object() if hasattr(xobjects, "get_object") else xobjects
    for reference in xobjects.values():
        form = reference.get_object() if hasattr(reference, "get_object") else reference
        if form.get("/Subtype") != "/Form":
            continue
        identity = _object_identity(form)
        if identity in visited:
            continue
        visited.add(identity)
        yield form
        yield from _nested_form_streams(form.get("/Resources"), visited)


def _page_stream_bytes(
    page: object,
    max_page_stream_bytes: int,
    remaining_total_stream_bytes: int,
) -> int:
    total = 0
    streams = chain(
        _stream_objects(page.get("/Contents")),
        _nested_form_streams(page.get("/Resources"), set()),
    )
    for stream in streams:
        remaining_page = max_page_stream_bytes - total
        remaining_total = remaining_total_stream_bytes - total
        if remaining_page < 0:
            raise _PageStreamBudgetExceeded("PAGE_STREAM_SIZE")
        if remaining_total < 0:
            raise _PageStreamBudgetExceeded("TOTAL_STREAM_SIZE")
        try:
            decoded_size = _decoded_stream_bytes(
                stream,
                min(remaining_page, remaining_total),
            )
        except _PageStreamBudgetExceeded:
            reason = (
                "PAGE_STREAM_SIZE"
                if remaining_page <= remaining_total
                else "TOTAL_STREAM_SIZE"
            )
            raise _PageStreamBudgetExceeded(reason) from None
        total += decoded_size
    return total


def _bounded_page_tree_count(node: object, maximum: int, visiting: set[tuple[str, int]]) -> int:
    node = node.get_object() if hasattr(node, "get_object") else node
    if not hasattr(node, "get"):
        raise PdfReadError("Invalid page-tree node")
    if node.get("/Type") == "/Page" or "/Kids" not in node:
        return 1
    identity = _object_identity(node)
    if identity in visiting:
        raise PdfReadError("Detected cyclic page references.")
    visiting.add(identity)
    try:
        kids = node["/Kids"]
        kids = kids.get_object() if hasattr(kids, "get_object") else kids
        if not isinstance(kids, (list, tuple)):
            raise PdfReadError("Expected /Kids to be an array")
        total = 0
        for child in kids:
            total += _bounded_page_tree_count(child, maximum - total, visiting)
            if total > maximum:
                return total
        return total
    finally:
        visiting.remove(identity)


def _page_count(reader: PdfReader, maximum: int) -> int:
    pages = reader.root_object.get("/Pages")
    if pages is None:
        raise PdfReadError("Missing page tree")
    return _bounded_page_tree_count(pages, maximum, set())


def _child_extract(
    pdf_path: str,
    configuration: PdfExtractionConfiguration,
    connection: Connection,
) -> None:
    logging.getLogger("pypdf").disabled = True
    try:
        reader = PdfReader(pdf_path, strict=True)
        if reader.is_encrypted:
            connection.send(("error", "PDF_ENCRYPTED", "ENCRYPTED", False))
            return
        if _page_count(reader, configuration.max_pages) > configuration.max_pages:
            _child_send(
                connection,
                ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "PAGE_COUNT", False)
            )
            return

        total_stream_bytes = 0
        pages = reader.pages
        if len(pages) > configuration.max_pages:
            _child_send(
                connection,
                ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "PAGE_COUNT", False),
            )
            return
        _child_send(connection, ("ok_start", len(pages)))
        for page_number, page in enumerate(pages, start=1):
            try:
                stream_bytes = _page_stream_bytes(
                    page,
                    configuration.max_page_stream_bytes,
                    configuration.max_total_stream_bytes - total_stream_bytes,
                )
            except _PageStreamBudgetExceeded as error:
                _child_send(
                    connection,
                    ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", error.reason, False),
                )
                return
            if stream_bytes > configuration.max_page_stream_bytes:
                _child_send(
                    connection,
                    ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "PAGE_STREAM_SIZE", False)
                )
                return
            total_stream_bytes += stream_bytes
            if total_stream_bytes > configuration.max_total_stream_bytes:
                _child_send(
                    connection,
                    ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "TOTAL_STREAM_SIZE", False)
                )
                return
            _child_send_page(
                connection,
                _RawPage(page_number, page.extract_text(extraction_mode="plain") or ""),
            )
        _child_send(connection, ("ok_end",), wait_for_ack=True)
    except FileNotDecryptedError:
        _child_send(connection, ("error", "PDF_ENCRYPTED", "ENCRYPTED", False))
    except (DependencyError, NotImplementedError):
        _child_send(connection, ("error", "PDF_UNSUPPORTED", "UNSUPPORTED_FEATURE", False))
    except LimitReachedError:
        _child_send(connection, ("error", "PDF_MALFORMED", "MALFORMED", False))
    except MemoryError:
        _child_send(
            connection,
            ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "EXTRACTOR_MEMORY", False),
        )
    except (
        PdfReadError,
        ParseError,
        PyPdfError,
        AttributeError,
        KeyError,
        IndexError,
        ValueError,
        TypeError,
    ):
        _child_send(connection, ("error", "PDF_MALFORMED", "MALFORMED", False))
    except OSError:
        _child_send(connection, ("error", "PDF_EXTRACTOR_UNAVAILABLE", "CHILD_CRASH", True))
    except BaseException:
        _child_send(connection, ("error", "PDF_EXTRACTOR_UNAVAILABLE", "CHILD_CRASH", True))
    finally:
        connection.close()


class PypdfTextExtractor:
    _child_target = staticmethod(_child_extract)

    def extract(
        self,
        stream: BinaryIO,
        configuration: PdfExtractionConfiguration,
    ) -> PdfExtractionResult:
        try:
            path = self._copy_to_temporary_file(stream, configuration.max_raw_bytes)
        except PdfExtractionError:
            raise
        except OSError as error:
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason="CHILD_CRASH",
                retryable=True,
            ) from error
        try:
            raw_pages = self._extract_in_child(path, configuration)
        finally:
            with suppress(OSError):
                path.unlink(missing_ok=True)

        pages = tuple(self._normalize_page(page) for page in raw_pages)
        extracted_characters = sum(len(page.text.strip()) for page in pages)
        if extracted_characters < configuration.minimum_extracted_characters:
            raise PdfExtractionError(
                "PDF_TEXT_INSUFFICIENT",
                reason="INSUFFICIENT_EXTRACTABLE_TEXT",
            )
        chunks = self._chunk_pages(pages, configuration)
        return PdfExtractionResult(
            pages=pages,
            chunks=chunks,
            parser_version=configuration.parser_version,
            extraction_options_version=configuration.extraction_options_version,
            normalizer_version=configuration.normalizer_version,
            tokenizer_name=configuration.tokenizer_name,
            tokenizer_version=configuration.tokenizer_version,
            chunking_policy_version=configuration.chunking_policy_version,
            derivation_identity=configuration.derivation_identity,
        )

    @staticmethod
    def _copy_to_temporary_file(stream: BinaryIO, max_raw_bytes: int) -> Path:
        total = 0
        path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary:
                path = Path(temporary.name)
                while chunk := stream.read(_COPY_BUFFER_BYTES):
                    total += len(chunk)
                    if total > max_raw_bytes:
                        raise PdfExtractionError(
                            "PDF_RESOURCE_LIMIT_EXCEEDED",
                            reason="RAW_FILE_SIZE",
                        )
                    temporary.write(chunk)
            return path
        except BaseException:
            if path is not None:
                with suppress(OSError):
                    path.unlink(missing_ok=True)
            raise

    def _extract_in_child(
        self,
        path: Path,
        configuration: PdfExtractionConfiguration,
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
                args=(self._child_target, str(path), configuration, child),
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
                peak_memory = max(
                    peak_memory,
                    self._check_memory(monitored, process, configuration),
                )
                return peak_memory

            heartbeat()
            memory_limit_handle = _install_hard_memory_limit(
                process,
                configuration.extractor_memory_bytes,
            )
            try:
                parent.send(("start",))
            except (BrokenPipeError, EOFError, OSError) as error:
                self._stop(process)
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CHILD_CRASH",
                    retryable=True,
                ) from error
            message = self._receive_message(
                parent,
                deadline,
                process,
                heartbeat=heartbeat,
            )
            if message[0] == "error":
                terminal_error = message
            elif message[0] == "ok_start":
                raw_pages = self._receive_pages(
                    parent,
                    message,
                    deadline,
                    heartbeat,
                )
                heartbeat()
                try:
                    parent.send(True)
                except (BrokenPipeError, EOFError, OSError) as error:
                    self._stop(process)
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
                self._stop(process)
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
                    self._stop(process)
            _close_memory_limit(memory_limit_handle)

        if terminal_error is not None:
            self._raise_child_error(terminal_error)
        if raw_pages is None:
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason="CHILD_CRASH",
                retryable=True,
            )
        return raw_pages

    @staticmethod
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

    @staticmethod
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
        self,
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
            message = self._receive_message(
                connection,
                deadline,
                heartbeat=heartbeat,
            )
            if message[0] == "error":
                self._raise_child_error(message)
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

    @staticmethod
    def _check_memory(
        monitored: psutil.Process,
        process: multiprocessing.Process,
        configuration: PdfExtractionConfiguration,
    ) -> int:
        try:
            info = monitored.memory_info()
        except psutil.NoSuchProcess:
            return 0
        high_water = max(
            info.rss,
            getattr(info, "peak_wset", 0),
        )
        if high_water > configuration.extractor_memory_bytes:
            PypdfTextExtractor._stop(process)
            raise PdfExtractionError(
                "PDF_RESOURCE_LIMIT_EXCEEDED",
                reason="EXTRACTOR_MEMORY",
            )
        return high_water

    @staticmethod
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

    @staticmethod
    def _normalize_page(page: _RawPage) -> NormalizedPdfPage:
        value = unicodedata.normalize("NFC", page.text)
        value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
        value = "".join(
            character
            for character in value
            if character in _CONTROL_WHITELIST or unicodedata.category(character) != "Cc"
        )
        lines = [_HORIZONTAL_WHITESPACE.sub(" ", line).strip() for line in value.split("\n")]
        value = _EXCESS_BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()
        return NormalizedPdfPage(
            page_number=page.page_number,
            text=value,
            content_checksum=hashlib.sha256(value.encode()).hexdigest(),
        )

    @staticmethod
    def _encode(tokenizer, text: str) -> list[int]:
        return tokenizer.encode(text, disallowed_special=())

    @staticmethod
    def _chunk_pages(
        pages: tuple[NormalizedPdfPage, ...],
        configuration: PdfExtractionConfiguration,
    ) -> tuple[PreparedPdfChunk, ...]:
        tokenizer = tiktoken.get_encoding(configuration.tokenizer_name)
        chunks: list[PreparedPdfChunk] = []
        for page in pages:
            if not page.text:
                continue
            blocks = PypdfTextExtractor._blocks(page.text, tokenizer)
            current: list[_Block] = []
            for block in blocks:
                if block.token_count > configuration.max_tokens:
                    if current:
                        PypdfTextExtractor._append_chunk(chunks, page, current, tokenizer)
                        current = []
                    PypdfTextExtractor._hard_split_block(
                        chunks,
                        page,
                        block,
                        tokenizer,
                        configuration,
                    )
                    continue
                if not current:
                    current = [block]
                    continue
                candidate_count = len(
                    PypdfTextExtractor._encode(
                        tokenizer,
                        page.text[current[0].start : block.end],
                    )
                )
                if candidate_count <= configuration.target_tokens:
                    current.append(block)
                    continue

                PypdfTextExtractor._append_chunk(chunks, page, current, tokenizer)
                overlap: list[_Block] = []
                for previous in reversed(current):
                    proposed = [previous, *overlap]
                    overlap_count = len(
                        PypdfTextExtractor._encode(
                            tokenizer,
                            page.text[proposed[0].start : proposed[-1].end],
                        )
                    )
                    if overlap_count > configuration.overlap_tokens:
                        break
                    overlap = proposed
                current = [*overlap, block]
                while (
                    len(
                        PypdfTextExtractor._encode(
                            tokenizer,
                            page.text[current[0].start : current[-1].end],
                        )
                    )
                    > configuration.max_tokens
                    and len(current) > 1
                ):
                    current.pop(0)
            if current:
                PypdfTextExtractor._append_chunk(chunks, page, current, tokenizer)
        return tuple(chunks)

    @staticmethod
    def _blocks(text: str, tokenizer) -> tuple[_Block, ...]:
        blocks: list[_Block] = []
        for match in re.finditer(r"\S(?:.*?\S)?(?=\n{2,}|\Z)", text, re.DOTALL):
            blocks.append(
                _Block(
                    start=match.start(),
                    end=match.end(),
                    token_count=len(PypdfTextExtractor._encode(tokenizer, match.group())),
                )
            )
        return tuple(blocks)

    @staticmethod
    def _append_chunk(
        chunks: list[PreparedPdfChunk],
        page: NormalizedPdfPage,
        blocks: list[_Block],
        tokenizer,
    ) -> None:
        start = blocks[0].start
        end = blocks[-1].end
        PypdfTextExtractor._append_range(chunks, page, start, end, tokenizer)

    @staticmethod
    def _hard_split_block(
        chunks: list[PreparedPdfChunk],
        page: NormalizedPdfPage,
        block: _Block,
        tokenizer,
        configuration: PdfExtractionConfiguration,
    ) -> None:
        start = block.start
        while start < block.end:
            remaining = page.text[start:block.end]
            tokens = PypdfTextExtractor._encode(tokenizer, remaining)
            if len(tokens) <= configuration.max_tokens:
                end = block.end
            else:
                offsets = tokenizer.decode_with_offsets(tokens)[1]
                candidate = offsets[configuration.max_tokens]
                end = min(block.end, start + max(candidate, 1))
                end = PypdfTextExtractor._bounded_token_range(
                    page.text,
                    start,
                    end,
                    tokenizer,
                    configuration.max_tokens,
                )[1]
                if end <= start:
                    raise ValueError("PDF text cannot be represented within token limit")
            start, end = PypdfTextExtractor._bounded_token_range(
                page.text, start, end, tokenizer, configuration.max_tokens
            )
            PypdfTextExtractor._append_range(chunks, page, start, end, tokenizer)
            if end == block.end:
                break
            overlap_start = PypdfTextExtractor._overlap_start(
                page.text,
                start,
                end,
                tokenizer,
                configuration.overlap_tokens,
            )
            start = overlap_start if overlap_start > start else end

    @staticmethod
    def _overlap_start(
        text: str,
        start: int,
        end: int,
        tokenizer,
        overlap_tokens: int,
    ) -> int:
        if overlap_tokens <= 0:
            return end
        overlap_start = end
        for boundary in range(end - 1, start, -1):
            if len(PypdfTextExtractor._encode(tokenizer, text[boundary:end])) > overlap_tokens:
                break
            overlap_start = boundary
        return overlap_start

    @staticmethod
    def _bounded_token_range(
        text: str,
        start: int,
        end: int,
        tokenizer,
        max_tokens: int,
    ) -> tuple[int, int]:
        while (
            end > start
            and len(PypdfTextExtractor._encode(tokenizer, text[start:end])) > max_tokens
        ):
            end -= 1
        return start, end

    @staticmethod
    def _append_range(
        chunks: list[PreparedPdfChunk],
        page: NormalizedPdfPage,
        start: int,
        end: int,
        tokenizer,
    ) -> None:
        content = page.text[start:end]
        chunks.append(
            PreparedPdfChunk(
                ordinal=len(chunks),
                page_number=page.page_number,
                page_start=page.page_number,
                page_end=page.page_number,
                start_offset=start,
                end_offset=end,
                content=content,
                content_checksum=hashlib.sha256(content.encode()).hexdigest(),
                token_count=len(PypdfTextExtractor._encode(tokenizer, content)),
            )
        )
