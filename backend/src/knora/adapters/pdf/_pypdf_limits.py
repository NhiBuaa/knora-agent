from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from itertools import chain

from pypdf import PdfReader
from pypdf.errors import LimitReachedError, PdfReadError

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
