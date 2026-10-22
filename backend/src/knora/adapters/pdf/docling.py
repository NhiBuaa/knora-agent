from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import BinaryIO

from knora.ingestion.pdf import (
    NormalizedPdfPage,
    PdfExtractionConfiguration,
    PdfExtractionError,
    PdfExtractionResult,
)
from knora.ingestion.pdf_chunking import chunk_canonical_document
from knora.ingestion.pdf_structure import (
    BlockType,
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    PageCompleteness,
    SourceOrigin,
    validate_canonical_document,
)
from knora.providers.cloudflare.pdf_understanding import (
    CloudflarePdfUnderstandingProvider,
)


@dataclass(frozen=True, slots=True)
class DoclingExtractionConfiguration(PdfExtractionConfiguration):
    cloudflare_ocr_model: str = "@cf/moondream/moondream3.1-9B-A2B"
    enable_local_models: bool = False

    def __post_init__(self) -> None:
        PdfExtractionConfiguration.__post_init__(self)
        if self.enable_local_models:
            raise ValueError(
                "local models and weights downloads are strictly prohibited under Q3/G3"
            )

    @classmethod
    def cloudflare_native_v1(cls) -> DoclingExtractionConfiguration:
        return cls(
            parser_version="docling-native-cf-v1",
            extraction_options_version="cf-tomarkdown-moondream-v1",
            normalizer_version="pdf-normalizer-m2-v1",
            tokenizer_name="cl100k_base",
            tokenizer_version="tiktoken-0.12.0",
            chunking_policy_version="page-block-v1",
            target_tokens=500,
            overlap_tokens=75,
            max_tokens=650,
            max_raw_bytes=25 * 1024 * 1024,
            max_pages=500,
            max_page_stream_bytes=4 * 1024 * 1024,
            max_total_stream_bytes=64 * 1024 * 1024,
            extraction_timeout_seconds=60.0,
            extractor_memory_bytes=512 * 1024 * 1024,
            minimum_extracted_characters=1,
            cloudflare_ocr_model="@cf/moondream/moondream3.1-9B-A2B",
            enable_local_models=False,
        )


class DoclingTextExtractor:
    """Document understanding extractor leveraging native parser + Cloudflare Workers AI.

    Never loads local neural weights, VLMs or HuggingFace models (strictly Cloudflare-only).
    """

    def __init__(
        self,
        cf_provider: CloudflarePdfUnderstandingProvider | None = None,
    ) -> None:
        self._cf_provider = cf_provider

    def extract(
        self,
        stream: BinaryIO,
        configuration: DoclingExtractionConfiguration,
    ) -> PdfExtractionResult:
        raw_bytes = stream.read(configuration.max_raw_bytes + 1)
        if len(raw_bytes) > configuration.max_raw_bytes:
            raise PdfExtractionError("PDF_RESOURCE_LIMIT_EXCEEDED", reason="RAW_FILE_SIZE")

        raw_source_hash = hashlib.sha256(raw_bytes).hexdigest()

        # Try physical page-aware parsing using pypdf
        canonical_pages: list[CanonicalPage] = []
        is_pdf_stream = False
        try:
            from io import BytesIO

            from pypdf import PdfReader

            from knora.adapters.pdf._pypdf_limits import (
                _page_count,
                _page_stream_bytes,
                _PageStreamBudgetExceeded,
            )

            reader = PdfReader(BytesIO(raw_bytes), strict=False)
            if reader.is_encrypted:
                raise PdfExtractionError("PDF_ENCRYPTED", reason="ENCRYPTED")
            if _page_count(reader, configuration.max_pages) > configuration.max_pages:
                raise PdfExtractionError("PDF_RESOURCE_LIMIT_EXCEEDED", reason="PAGE_COUNT")
            num_pages = len(reader.pages)
            if num_pages > configuration.max_pages:
                raise PdfExtractionError("PDF_RESOURCE_LIMIT_EXCEEDED", reason="PAGE_COUNT")
            is_pdf_stream = True

            total_stream_bytes = 0
            for page_idx, page in enumerate(reader.pages, start=1):
                try:
                    stream_bytes = _page_stream_bytes(
                        page,
                        configuration.max_page_stream_bytes,
                        configuration.max_total_stream_bytes - total_stream_bytes,
                    )
                except _PageStreamBudgetExceeded as error:
                    raise PdfExtractionError(
                        "PDF_RESOURCE_LIMIT_EXCEEDED", reason=error.reason
                    ) from error
                if stream_bytes > configuration.max_page_stream_bytes:
                    raise PdfExtractionError(
                        "PDF_RESOURCE_LIMIT_EXCEEDED", reason="PAGE_STREAM_SIZE"
                    )
                total_stream_bytes += stream_bytes
                if total_stream_bytes > configuration.max_total_stream_bytes:
                    raise PdfExtractionError(
                        "PDF_RESOURCE_LIMIT_EXCEEDED", reason="TOTAL_STREAM_SIZE"
                    )

                native_text = (page.extract_text() or "").strip()
                if len(native_text) >= configuration.minimum_extracted_characters:
                    blocks = self._parse_page_blocks(
                        page_idx, native_text, SourceOrigin.NATIVE_TEXT
                    )
                    canonical_pages.append(
                        CanonicalPage(
                            page_number=page_idx,
                            text=native_text,
                            content_checksum=hashlib.sha256(native_text.encode()).hexdigest(),
                            blocks=tuple(blocks),
                            completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
                        )
                    )
                else:
                    ocr_applied = False
                    if self._cf_provider is not None:
                        try:
                            if hasattr(page, "images") and len(page.images) > 0:
                                img_data = page.images[0].data
                                ocr_resp = self._cf_provider.ocr_page_image(img_data)
                                ocr_text = ocr_resp.text.strip()
                                if ocr_text:
                                    blocks = self._parse_page_blocks(
                                        page_idx,
                                        ocr_text,
                                        SourceOrigin.OCR,
                                        confidence=ocr_resp.confidence,
                                    )
                                    canonical_pages.append(
                                        CanonicalPage(
                                            page_number=page_idx,
                                            text=ocr_text,
                                            content_checksum=hashlib.sha256(
                                                ocr_text.encode()
                                            ).hexdigest(),
                                            blocks=tuple(blocks),
                                            completeness=PageCompleteness(
                                                is_complete=True, status="COMPLETE"
                                            ),
                                        )
                                    )
                                    ocr_applied = True
                        except Exception:
                            ocr_applied = False

                    if not ocr_applied:
                        canonical_pages.append(
                            CanonicalPage(
                                page_number=page_idx,
                                text="",
                                content_checksum=hashlib.sha256(b"").hexdigest(),
                                blocks=(),
                                completeness=PageCompleteness(is_complete=False, status="EMPTY"),
                            )
                        )
        except PdfExtractionError:
            raise
        except Exception:
            is_pdf_stream = False

        if not is_pdf_stream or not canonical_pages:
            if self._cf_provider is None:
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CLOUDFLARE_PROVIDER_UNCONFIGURED",
                    retryable=True,
                )

            conversion = self._cf_provider.convert_to_markdown(raw_bytes)
            if conversion.format == "error":
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CLOUDFLARE_CONVERSION_FAILED",
                    retryable=True,
                )
            markdown_text = conversion.content.strip()

            if len(markdown_text) < configuration.minimum_extracted_characters:
                raise PdfExtractionError(
                    "PDF_TEXT_INSUFFICIENT",
                    reason="INSUFFICIENT_EXTRACTABLE_TEXT",
                )

            canonical_pages = list(
                self._parse_markdown_into_pages(
                    markdown_text, configuration, is_complete=is_pdf_stream
                )
            )

        total_extracted_chars = sum(len(p.text) for p in canonical_pages)
        if total_extracted_chars < configuration.minimum_extracted_characters:
            raise PdfExtractionError(
                "PDF_TEXT_INSUFFICIENT",
                reason="INSUFFICIENT_EXTRACTABLE_TEXT",
            )

        doc_is_complete = all(p.completeness.is_complete for p in canonical_pages) and is_pdf_stream
        canonical_doc = CanonicalDocument(
            raw_source_hash=raw_source_hash,
            derivation_identity=configuration.derivation_identity,
            parser_version=configuration.parser_version,
            pages=tuple(canonical_pages),
            is_complete=doc_is_complete,
            completeness_status="COMPLETE" if doc_is_complete else "INCOMPLETE",
        )
        validate_canonical_document(canonical_doc)

        chunks = chunk_canonical_document(canonical_doc, configuration)
        normalized_pages = tuple(
            NormalizedPdfPage(
                page_number=p.page_number,
                text=p.text,
                content_checksum=p.content_checksum,
            )
            for p in canonical_pages
        )

        return PdfExtractionResult(
            pages=normalized_pages,
            chunks=chunks,
            parser_version=configuration.parser_version,
            extraction_options_version=configuration.extraction_options_version,
            normalizer_version=configuration.normalizer_version,
            tokenizer_name=configuration.tokenizer_name,
            tokenizer_version=configuration.tokenizer_version,
            chunking_policy_version=configuration.chunking_policy_version,
            derivation_identity=configuration.derivation_identity,
            structure=canonical_doc,
        )

    def _parse_page_blocks(
        self,
        page_number: int,
        page_text: str,
        source_origin: SourceOrigin,
        confidence: float | None = None,
    ) -> list[CanonicalBlock]:
        raw_sections = [s.strip() for s in re.split(r"(?:\r?\n){2,}", page_text) if s.strip()]
        if not raw_sections:
            return []

        blocks: list[CanonicalBlock] = []
        heading_stack: list[str] = []
        current_search_idx = 0

        for idx, section in enumerate(raw_sections, start=1):
            start = page_text.find(section, current_search_idx)
            if start == -1:
                start = current_search_idx
            end = start + len(section)
            current_search_idx = end

            block_type = BlockType.PARAGRAPH
            heading_level = None

            heading_match = re.match(r"^(#{1,6})\s+(.*)$", section)
            if heading_match:
                block_type = BlockType.HEADING
                level = len(heading_match.group(1))
                heading_level = level
                title = heading_match.group(2).strip()
                heading_stack = heading_stack[: level - 1] + [title]
                clean_text = section
            elif section.startswith("|") and section.endswith("|"):
                block_type = BlockType.TABLE
                clean_text = section
            else:
                clean_text = section

            blocks.append(
                CanonicalBlock(
                    block_id=f"p{page_number}_b{idx}",
                    page_number=page_number,
                    block_type=block_type,
                    start_offset=start,
                    end_offset=end,
                    text=clean_text,
                    heading_level=heading_level,
                    heading_path=tuple(heading_stack),
                    source_origin=source_origin,
                    confidence=confidence,
                )
            )
        return blocks

    def _process_single_page(
        self,
        page_number: int,
        native_text: str,
        page_image_bytes: bytes | None,
        config: DoclingExtractionConfiguration,
    ) -> CanonicalPage:
        """Process a single page, triggering selective OCR if native text is absent."""
        if (
            len(native_text.strip()) < config.minimum_extracted_characters
            and page_image_bytes
            and self._cf_provider is not None
        ):
            ocr_resp = self._cf_provider.ocr_page_image(page_image_bytes)
            page_text = ocr_resp.text.strip()
            blocks = self._parse_page_blocks(
                page_number, page_text, SourceOrigin.OCR, confidence=ocr_resp.confidence
            )
            return CanonicalPage(
                page_number=page_number,
                text=page_text,
                content_checksum=hashlib.sha256(page_text.encode()).hexdigest(),
                blocks=tuple(blocks),
                completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
            )

        page_text = native_text.strip()
        blocks = self._parse_page_blocks(page_number, page_text, SourceOrigin.NATIVE_TEXT)
        return CanonicalPage(
            page_number=page_number,
            text=page_text,
            content_checksum=hashlib.sha256(page_text.encode()).hexdigest(),
            blocks=tuple(blocks),
            completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
        )

    def _parse_markdown_into_pages(
        self,
        markdown_text: str,
        config: DoclingExtractionConfiguration,
        is_complete: bool = True,
    ) -> tuple[CanonicalPage, ...]:
        if "\x0c" in markdown_text:
            raw_pages = markdown_text.split("\x0c")
        elif "\n<!-- pagebreak -->\n" in markdown_text:
            raw_pages = markdown_text.split("\n<!-- pagebreak -->\n")
        else:
            raw_pages = [markdown_text]

        pages: list[CanonicalPage] = []
        for page_idx, page_content in enumerate(raw_pages, start=1):
            p_text = page_content.strip()
            if not p_text:
                continue
            blocks = self._parse_page_blocks(page_idx, p_text, SourceOrigin.NATIVE_TEXT)
            pages.append(
                CanonicalPage(
                    page_number=page_idx,
                    text=p_text,
                    content_checksum=hashlib.sha256(p_text.encode()).hexdigest(),
                    blocks=tuple(blocks),
                    completeness=PageCompleteness(
                        is_complete=is_complete,
                        status="COMPLETE" if is_complete else "INCOMPLETE",
                        reason=None if is_complete else "PHYSICAL_STRUCTURE_UNRESOLVED",
                    ),
                )
            )
        return (
            tuple(pages)
            if pages
            else (
                CanonicalPage(
                    page_number=1,
                    text="",
                    content_checksum=hashlib.sha256(b"").hexdigest(),
                    blocks=(),
                    completeness=PageCompleteness(is_complete=False, status="EMPTY"),
                ),
            )
        )
