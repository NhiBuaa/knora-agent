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
        super().__post_init__()
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
        raw_bytes = stream.read()
        if len(raw_bytes) > configuration.max_raw_bytes:
            raise PdfExtractionError("PDF_RESOURCE_LIMIT_EXCEEDED", reason="RAW_FILE_SIZE")

        raw_source_hash = hashlib.sha256(raw_bytes).hexdigest()

        if self._cf_provider is None:
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason="CLOUDFLARE_PROVIDER_UNCONFIGURED",
                retryable=True,
            )

        conversion = self._cf_provider.convert_to_markdown(raw_bytes)
        markdown_text = conversion.content.strip()

        if len(markdown_text) < configuration.minimum_extracted_characters:
            raise PdfExtractionError(
                "PDF_TEXT_INSUFFICIENT",
                reason="INSUFFICIENT_EXTRACTABLE_TEXT",
            )

        # Parse markdown into structured canonical blocks
        canonical_pages = self._parse_markdown_into_pages(markdown_text, configuration)
        canonical_doc = CanonicalDocument(
            raw_source_hash=raw_source_hash,
            derivation_identity=configuration.derivation_identity,
            parser_version=configuration.parser_version,
            pages=canonical_pages,
            is_complete=True,
            completeness_status="COMPLETE",
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
            block = CanonicalBlock(
                block_id=f"p{page_number}_b1",
                page_number=page_number,
                block_type=BlockType.PARAGRAPH,
                start_offset=0,
                end_offset=len(page_text),
                text=page_text,
                source_origin=SourceOrigin.OCR,
                confidence=ocr_resp.confidence,
            )
            return CanonicalPage(
                page_number=page_number,
                text=page_text,
                content_checksum=hashlib.sha256(page_text.encode()).hexdigest(),
                blocks=(block,),
                completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
            )

        page_text = native_text.strip()
        block = CanonicalBlock(
            block_id=f"p{page_number}_b1",
            page_number=page_number,
            block_type=BlockType.PARAGRAPH,
            start_offset=0,
            end_offset=len(page_text),
            text=page_text,
            source_origin=SourceOrigin.NATIVE_TEXT,
        )
        return CanonicalPage(
            page_number=page_number,
            text=page_text,
            content_checksum=hashlib.sha256(page_text.encode()).hexdigest(),
            blocks=(block,),
            completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
        )

    def _parse_markdown_into_pages(
        self,
        markdown_text: str,
        config: DoclingExtractionConfiguration,
    ) -> tuple[CanonicalPage, ...]:
        # Split into blocks based on blank lines
        raw_sections = [s.strip() for s in re.split(r"\n{2,}", markdown_text) if s.strip()]
        page_text = "\n\n".join(raw_sections)

        blocks: list[CanonicalBlock] = []
        heading_stack: list[str] = []
        current_offset = 0

        for idx, section in enumerate(raw_sections, start=1):
            start = current_offset
            end = start + len(section)
            block_type = BlockType.PARAGRAPH
            heading_level = None

            # Detect headings
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", section)
            if heading_match:
                block_type = BlockType.HEADING
                level = len(heading_match.group(1))
                heading_level = level
                title = heading_match.group(2).strip()
                # Maintain heading stack for hierarchy
                heading_stack = heading_stack[: level - 1] + [title]
                clean_text = section
            elif section.startswith("|") and section.endswith("|"):
                block_type = BlockType.TABLE
                clean_text = section
            else:
                clean_text = section

            blocks.append(
                CanonicalBlock(
                    block_id=f"p1_b{idx}",
                    page_number=1,
                    block_type=block_type,
                    start_offset=start,
                    end_offset=end,
                    text=clean_text,
                    heading_level=heading_level,
                    heading_path=tuple(heading_stack),
                    source_origin=SourceOrigin.NATIVE_TEXT,
                )
            )
            current_offset = end + 2  # account for "\n\n"

        page = CanonicalPage(
            page_number=1,
            text=page_text,
            content_checksum=hashlib.sha256(page_text.encode()).hexdigest(),
            blocks=tuple(blocks),
            completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
        )
        return (page,)
