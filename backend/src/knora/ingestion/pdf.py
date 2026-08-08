from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import BinaryIO, Protocol

from knora.domain.errors import KnoraError


@dataclass(frozen=True, slots=True)
class PdfExtractionConfiguration:
    parser_version: str
    extraction_options_version: str
    normalizer_version: str
    tokenizer_name: str
    tokenizer_version: str
    chunking_policy_version: str
    target_tokens: int
    overlap_tokens: int
    max_tokens: int
    max_raw_bytes: int
    max_pages: int
    max_page_stream_bytes: int
    max_total_stream_bytes: int
    extraction_timeout_seconds: float
    extractor_memory_bytes: int
    minimum_extracted_characters: int

    def __post_init__(self) -> None:
        if not 0 <= self.overlap_tokens < self.target_tokens <= self.max_tokens:
            raise ValueError("invalid PDF chunk token limits")
        if min(
            self.max_raw_bytes,
            self.max_pages,
            self.max_page_stream_bytes,
            self.max_total_stream_bytes,
            self.extractor_memory_bytes,
            self.minimum_extracted_characters,
        ) <= 0:
            raise ValueError("PDF extraction limits must be positive")
        if self.extraction_timeout_seconds <= 0:
            raise ValueError("PDF extraction timeout must be positive")

    @classmethod
    def milestone_two(cls) -> PdfExtractionConfiguration:
        return cls(
            parser_version="pypdf-6.14.2-plain-v1",
            extraction_options_version="pypdf-plain-layout-v1",
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
            extraction_timeout_seconds=30.0,
            extractor_memory_bytes=256 * 1024 * 1024,
            minimum_extracted_characters=1,
        )

    @property
    def derivation_identity(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class NormalizedPdfPage:
    page_number: int
    text: str
    content_checksum: str


@dataclass(frozen=True, slots=True)
class PreparedPdfChunk:
    ordinal: int
    page_number: int
    page_start: int
    page_end: int
    start_offset: int
    end_offset: int
    content: str
    content_checksum: str
    token_count: int


@dataclass(frozen=True, slots=True)
class PdfExtractionResult:
    pages: tuple[NormalizedPdfPage, ...]
    chunks: tuple[PreparedPdfChunk, ...]
    parser_version: str
    extraction_options_version: str
    normalizer_version: str
    tokenizer_name: str
    tokenizer_version: str
    chunking_policy_version: str
    derivation_identity: str


class PdfExtractionError(KnoraError):
    def __init__(self, code: str, *, reason: str, retryable: bool = False) -> None:
        super().__init__(code)
        self.reason = reason
        self.retryable = retryable


class PdfTextExtractor(Protocol):
    def extract(
        self,
        stream: BinaryIO,
        configuration: PdfExtractionConfiguration,
    ) -> PdfExtractionResult: ...
