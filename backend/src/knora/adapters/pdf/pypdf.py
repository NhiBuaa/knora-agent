from __future__ import annotations

import logging
import tempfile
from contextlib import suppress
from multiprocessing.connection import Connection
from pathlib import Path
from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import (
    DependencyError,
    FileNotDecryptedError,
    LimitReachedError,
    ParseError,
    PdfReadError,
    PyPdfError,
)

from knora.adapters.pdf._pypdf_chunking import _chunk_pages, _normalize_page
from knora.adapters.pdf._pypdf_limits import (
    _page_count,
    _page_stream_bytes,
    _PageStreamBudgetExceeded,
)
from knora.adapters.pdf._pypdf_process import (
    _child_send,
    _child_send_page,
    _extract_in_child,
    _RawPage,
)
from knora.ingestion.pdf import (
    PdfExtractionConfiguration,
    PdfExtractionError,
    PdfExtractionResult,
)

_COPY_BUFFER_BYTES = 64 * 1024


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
            _child_send(connection, ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "PAGE_COUNT", False))
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
                    connection, ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "PAGE_STREAM_SIZE", False)
                )
                return
            total_stream_bytes += stream_bytes
            if total_stream_bytes > configuration.max_total_stream_bytes:
                _child_send(
                    connection, ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "TOTAL_STREAM_SIZE", False)
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
            raw_pages = _extract_in_child(path, configuration, self._child_target)
        finally:
            with suppress(OSError):
                path.unlink(missing_ok=True)

        pages = tuple(_normalize_page(page) for page in raw_pages)
        extracted_characters = sum(len(page.text.strip()) for page in pages)
        if extracted_characters < configuration.minimum_extracted_characters:
            raise PdfExtractionError(
                "PDF_TEXT_INSUFFICIENT",
                reason="INSUFFICIENT_EXTRACTABLE_TEXT",
            )
        chunks = _chunk_pages(pages, configuration)
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
