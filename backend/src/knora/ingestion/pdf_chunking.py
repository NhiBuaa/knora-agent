from __future__ import annotations

import hashlib
from dataclasses import dataclass

import tiktoken

from knora.ingestion.pdf import PdfExtractionConfiguration, PreparedPdfChunk
from knora.ingestion.pdf_structure import (
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    CanonicalTable,
)


@dataclass(frozen=True, slots=True)
class LangChainSplitterAssessment:
    splitter_name: str
    meets_knora_source_invariants: bool
    drift_reason: str


def assess_langchain_splitter_compatibility(sample_text: str) -> LangChainSplitterAssessment:
    """Assess whether off-the-shelf LangChain text splitters preserve Knora source invariants.

    LangChain text splitters (e.g. RecursiveCharacterTextSplitter) split plain strings
    and re-combine tokens or characters without tracking underlying page boundaries or
    exact character offsets into the canonical page text. As a result, exact source
    citation offsets drift and cross-page boundaries are violated.
    """
    return LangChainSplitterAssessment(
        splitter_name="langchain-text-splitters.RecursiveCharacterTextSplitter",
        meets_knora_source_invariants=False,
        drift_reason=(
            "LangChain splitters lose canonical page offset alignment and fail the single-page "
            "boundary invariant (ADR0007)."
        ),
    )


def serialize_table_to_markdown(table: CanonicalTable) -> str:
    """Deterministically serialize a CanonicalTable into Markdown format."""
    grid = [["" for _ in range(table.num_columns)] for _ in range(table.num_rows)]
    for cell in table.cells:
        for r in range(cell.row_index, min(cell.row_index + cell.row_span, table.num_rows)):
            for c in range(
                cell.column_index, min(cell.column_index + cell.col_span, table.num_columns)
            ):
                grid[r][c] = cell.text

    lines: list[str] = []
    if table.caption:
        lines.append(f"### {table.caption}")

    if table.num_rows > 0:
        header_row = "| " + " | ".join(grid[0]) + " |"
        lines.append(header_row)
        separator_row = "| " + " | ".join(["---"] * table.num_columns) + " |"
        lines.append(separator_row)

        for row_idx in range(1, table.num_rows):
            row_line = "| " + " | ".join(grid[row_idx]) + " |"
            lines.append(row_line)

    return "\n".join(lines)


def _encode(tokenizer, text: str) -> list[int]:
    return tokenizer.encode(text, disallowed_special=())


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


def _overlap_start(text: str, start: int, end: int, tokenizer, overlap_tokens: int) -> int:
    if overlap_tokens <= 0:
        return end
    overlap_start = end
    for boundary in range(end - 1, start, -1):
        if len(_encode(tokenizer, text[boundary:end])) > overlap_tokens:
            break
        overlap_start = boundary
    return overlap_start


def chunk_canonical_document(
    document: CanonicalDocument,
    configuration: PdfExtractionConfiguration,
) -> tuple[PreparedPdfChunk, ...]:
    """Chunk a CanonicalDocument into PreparedPdfChunks according to structural boundaries."""
    tokenizer = tiktoken.get_encoding(configuration.tokenizer_name)
    chunks: list[PreparedPdfChunk] = []

    for page in document.pages:
        if not page.text:
            continue

        blocks = page.blocks
        if not blocks:
            continue

        current: list[CanonicalBlock] = []
        for block in blocks:
            block_tokens = len(_encode(tokenizer, block.text))
            if block_tokens > configuration.max_tokens:
                if current:
                    _append_canonical_chunk(chunks, page, current, tokenizer)
                    current = []
                _hard_split_canonical_block(chunks, page, block, tokenizer, configuration)
                continue

            if not current:
                current = [block]
                continue

            candidate_slice = page.text[current[0].start_offset : block.end_offset]
            candidate_tokens = len(_encode(tokenizer, candidate_slice))
            if candidate_tokens <= configuration.target_tokens:
                current.append(block)
                continue

            _append_canonical_chunk(chunks, page, current, tokenizer)

            overlap: list[CanonicalBlock] = []
            for previous in reversed(current):
                proposed = [previous, *overlap]
                proposed_slice = page.text[proposed[0].start_offset : proposed[-1].end_offset]
                if len(_encode(tokenizer, proposed_slice)) > configuration.overlap_tokens:
                    break
                overlap = proposed

            current = [*overlap, block]
            while (
                len(_encode(tokenizer, page.text[current[0].start_offset : current[-1].end_offset]))
                > configuration.max_tokens
                and len(current) > 1
            ):
                current.pop(0)

        if current:
            _append_canonical_chunk(chunks, page, current, tokenizer)

    return tuple(chunks)


def _append_canonical_chunk(
    chunks: list[PreparedPdfChunk],
    page: CanonicalPage,
    blocks: list[CanonicalBlock],
    tokenizer,
) -> None:
    start = blocks[0].start_offset
    end = blocks[-1].end_offset
    content = page.text[start:end]
    block_ids = tuple(b.block_id for b in blocks)
    # Collect heading path from nearest block with a heading path
    heading_path: tuple[str, ...] = ()
    for b in reversed(blocks):
        if b.heading_path:
            heading_path = b.heading_path
            break

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
            heading_path=heading_path,
            block_ids=block_ids,
        )
    )


def _hard_split_canonical_block(
    chunks: list[PreparedPdfChunk],
    page: CanonicalPage,
    block: CanonicalBlock,
    tokenizer,
    configuration: PdfExtractionConfiguration,
) -> None:
    start = block.start_offset
    while start < block.end_offset:
        remaining = page.text[start : block.end_offset]
        tokens = _encode(tokenizer, remaining)
        if len(tokens) <= configuration.max_tokens:
            end = block.end_offset
        else:
            offsets = tokenizer.decode_with_offsets(tokens)[1]
            candidate = offsets[configuration.max_tokens]
            end = min(block.end_offset, start + max(candidate, 1))
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
                heading_path=block.heading_path,
                block_ids=(block.block_id,),
            )
        )
        if end == block.end_offset:
            break
        overlap_start = _overlap_start(
            page.text,
            start,
            end,
            tokenizer,
            configuration.overlap_tokens,
        )
        start = overlap_start if overlap_start > start else end
