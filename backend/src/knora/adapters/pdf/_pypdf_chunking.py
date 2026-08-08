from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

import tiktoken

from knora.adapters.pdf._pypdf_process import _RawPage
from knora.ingestion.pdf import (
    NormalizedPdfPage,
    PdfExtractionConfiguration,
    PreparedPdfChunk,
)

_CONTROL_WHITELIST = {"\n", "\t"}
_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\n]+")
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True, slots=True)
class _Block:
    start: int
    end: int
    token_count: int


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


def _encode(tokenizer, text: str) -> list[int]:
    return tokenizer.encode(text, disallowed_special=())


def _chunk_pages(
    pages: tuple[NormalizedPdfPage, ...],
    configuration: PdfExtractionConfiguration,
) -> tuple[PreparedPdfChunk, ...]:
    tokenizer = tiktoken.get_encoding(configuration.tokenizer_name)
    chunks: list[PreparedPdfChunk] = []
    for page in pages:
        if not page.text:
            continue
        blocks = _blocks(page.text, tokenizer)
        current: list[_Block] = []
        for block in blocks:
            if block.token_count > configuration.max_tokens:
                if current:
                    _append_chunk(chunks, page, current, tokenizer)
                    current = []
                _hard_split_block(chunks, page, block, tokenizer, configuration)
                continue
            if not current:
                current = [block]
                continue
            candidate_count = len(_encode(tokenizer, page.text[current[0].start : block.end]))
            if candidate_count <= configuration.target_tokens:
                current.append(block)
                continue

            _append_chunk(chunks, page, current, tokenizer)
            overlap: list[_Block] = []
            for previous in reversed(current):
                proposed = [previous, *overlap]
                overlap_count = len(
                    _encode(tokenizer, page.text[proposed[0].start : proposed[-1].end])
                )
                if overlap_count > configuration.overlap_tokens:
                    break
                overlap = proposed
            current = [*overlap, block]
            while (
                len(_encode(tokenizer, page.text[current[0].start : current[-1].end]))
                > configuration.max_tokens
                and len(current) > 1
            ):
                current.pop(0)
        if current:
            _append_chunk(chunks, page, current, tokenizer)
    return tuple(chunks)


def _blocks(text: str, tokenizer) -> tuple[_Block, ...]:
    blocks: list[_Block] = []
    for match in re.finditer(r"\S(?:.*?\S)?(?=\n{2,}|\Z)", text, re.DOTALL):
        blocks.append(
            _Block(
                start=match.start(),
                end=match.end(),
                token_count=len(_encode(tokenizer, match.group())),
            )
        )
    return tuple(blocks)


def _append_chunk(
    chunks: list[PreparedPdfChunk],
    page: NormalizedPdfPage,
    blocks: list[_Block],
    tokenizer,
) -> None:
    _append_range(chunks, page, blocks[0].start, blocks[-1].end, tokenizer)


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
        tokens = _encode(tokenizer, remaining)
        if len(tokens) <= configuration.max_tokens:
            end = block.end
        else:
            offsets = tokenizer.decode_with_offsets(tokens)[1]
            candidate = offsets[configuration.max_tokens]
            end = min(block.end, start + max(candidate, 1))
            end = _bounded_token_range(
                page.text,
                start,
                end,
                tokenizer,
                configuration.max_tokens,
            )[1]
            if end <= start:
                raise ValueError("PDF text cannot be represented within token limit")
        start, end = _bounded_token_range(
            page.text,
            start,
            end,
            tokenizer,
            configuration.max_tokens,
        )
        _append_range(chunks, page, start, end, tokenizer)
        if end == block.end:
            break
        overlap_start = _overlap_start(
            page.text,
            start,
            end,
            tokenizer,
            configuration.overlap_tokens,
        )
        start = overlap_start if overlap_start > start else end


def _overlap_start(text: str, start: int, end: int, tokenizer, overlap_tokens: int) -> int:
    if overlap_tokens <= 0:
        return end
    overlap_start = end
    for boundary in range(end - 1, start, -1):
        if len(_encode(tokenizer, text[boundary:end])) > overlap_tokens:
            break
        overlap_start = boundary
    return overlap_start


def _bounded_token_range(
    text: str,
    start: int,
    end: int,
    tokenizer,
    max_tokens: int,
) -> tuple[int, int]:
    while end > start and len(_encode(tokenizer, text[start:end])) > max_tokens:
        end -= 1
    return start, end


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
            token_count=len(_encode(tokenizer, content)),
        )
    )
