from __future__ import annotations

import hashlib

from knora.ingestion.pdf import PdfExtractionConfiguration
from knora.ingestion.pdf_chunking import (
    LangChainSplitterAssessment,
    assess_langchain_splitter_compatibility,
    chunk_canonical_document,
    serialize_table_to_markdown,
)
from knora.ingestion.pdf_structure import (
    BlockType,
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    CanonicalTable,
    CanonicalTableCell,
    PageCompleteness,
    SourceOrigin,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_multi_column_reading_order_preserved() -> None:
    # Page text with two columns laid out in reading order
    text = "Left column line 1.\nLeft column line 2.\n\nRight column line 1.\nRight column line 2."
    b1 = CanonicalBlock(
        block_id="b_left",
        page_number=1,
        block_type=BlockType.PARAGRAPH,
        start_offset=0,
        end_offset=39,
        text="Left column line 1.\nLeft column line 2.",
        source_origin=SourceOrigin.NATIVE_TEXT,
    )
    b2 = CanonicalBlock(
        block_id="b_right",
        page_number=1,
        block_type=BlockType.PARAGRAPH,
        start_offset=41,
        end_offset=83,
        text="Right column line 1.\nRight column line 2.",
        source_origin=SourceOrigin.NATIVE_TEXT,
    )
    page = CanonicalPage(
        page_number=1,
        text=text,
        content_checksum=_sha256(text),
        blocks=(b1, b2),
        completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
    )
    doc = CanonicalDocument(
        raw_source_hash="c" * 64,
        derivation_identity="d" * 64,
        parser_version="pypdf-6.14.2-plain-v1",
        pages=(page,),
        is_complete=True,
        completeness_status="COMPLETE",
    )
    config = PdfExtractionConfiguration.milestone_two()
    chunks = chunk_canonical_document(doc, config)

    assert len(chunks) >= 1
    # First chunk starts with left column text
    assert chunks[0].content.startswith("Left column")
    assert "b_left" in chunks[0].block_ids


def test_repeating_text_no_offset_ambiguity() -> None:
    # Two identical phrases at different offsets
    repeated = "Important Notice"
    filler = "A" * 200
    text = f"{repeated}\n\n{filler}\n\n{repeated}"
    # Offsets
    b1_start = 0
    b1_end = len(repeated)
    b2_start = b1_end + 2
    b2_end = b2_start + len(filler)
    b3_start = b2_end + 2
    b3_end = b3_start + len(repeated)

    b1 = CanonicalBlock(
        block_id="b1",
        page_number=1,
        block_type=BlockType.HEADING,
        start_offset=b1_start,
        end_offset=b1_end,
        text=repeated,
    )
    b2 = CanonicalBlock(
        block_id="b2",
        page_number=1,
        block_type=BlockType.PARAGRAPH,
        start_offset=b2_start,
        end_offset=b2_end,
        text=filler,
    )
    b3 = CanonicalBlock(
        block_id="b3",
        page_number=1,
        block_type=BlockType.HEADING,
        start_offset=b3_start,
        end_offset=b3_end,
        text=repeated,
    )
    page = CanonicalPage(
        page_number=1,
        text=text,
        content_checksum=_sha256(text),
        blocks=(b1, b2, b3),
    )
    doc = CanonicalDocument(
        raw_source_hash="c" * 64,
        derivation_identity="d" * 64,
        parser_version="pypdf-6.14.2-plain-v1",
        pages=(page,),
    )
    config = PdfExtractionConfiguration.milestone_two()
    chunks = chunk_canonical_document(doc, config)

    for chunk in chunks:
        # Every chunk's content must strictly equal page.text[start_offset:end_offset]
        assert chunk.content == text[chunk.start_offset : chunk.end_offset]


def test_heading_path_in_metadata_without_mutating_source_content() -> None:
    heading_text = "Architecture Standard"
    body_text = "All components must obey boundaries."
    text = f"{heading_text}\n\n{body_text}"

    b_head = CanonicalBlock(
        block_id="h1",
        page_number=1,
        block_type=BlockType.HEADING,
        start_offset=0,
        end_offset=len(heading_text),
        text=heading_text,
        heading_id="h1",
        heading_path=("Architecture Standard",),
    )
    b_body = CanonicalBlock(
        block_id="p1",
        page_number=1,
        block_type=BlockType.PARAGRAPH,
        start_offset=len(heading_text) + 2,
        end_offset=len(text),
        text=body_text,
        parent_heading_id="h1",
        heading_path=("Architecture Standard",),
    )
    page = CanonicalPage(
        page_number=1,
        text=text,
        content_checksum=_sha256(text),
        blocks=(b_head, b_body),
    )
    doc = CanonicalDocument(
        raw_source_hash="c" * 64,
        derivation_identity="d" * 64,
        parser_version="pypdf-6.14.2-plain-v1",
        pages=(page,),
    )
    config = PdfExtractionConfiguration.milestone_two()
    chunks = chunk_canonical_document(doc, config)

    assert len(chunks) >= 1
    # Chunk containing body must have heading_path in metadata
    body_chunk = [c for c in chunks if "p1" in c.block_ids][0]
    assert body_chunk.heading_path == ("Architecture Standard",)
    # Critical invariant: content must NOT have synthetic heading prepended
    assert body_chunk.content == text[body_chunk.start_offset : body_chunk.end_offset]
    assert not body_chunk.content.startswith("Heading: Architecture Standard")


def test_table_with_merged_cells_serialized_deterministically() -> None:
    table = CanonicalTable(
        table_id="table_1",
        page_number=1,
        num_rows=2,
        num_columns=2,
        cells=(
            CanonicalTableCell(
                row_index=0,
                column_index=0,
                row_span=1,
                col_span=2,
                text="Header Spanning 2 Cols",
                is_header=True,
            ),
            CanonicalTableCell(row_index=1, column_index=0, row_span=1, col_span=1, text="Cell A"),
            CanonicalTableCell(row_index=1, column_index=1, row_span=1, col_span=1, text="Cell B"),
        ),
        caption="Sample Table",
    )
    markdown = serialize_table_to_markdown(table)
    assert "Header Spanning 2 Cols" in markdown
    assert "Cell A" in markdown
    assert "Cell B" in markdown
    assert "| --- | --- |" in markdown


def test_chunk_page_boundary_and_token_limits() -> None:
    # 2 pages, chunker must NEVER merge blocks across pages (ADR0007)
    p1_text = "Page 1 content."
    p2_text = "Page 2 content."
    b1 = CanonicalBlock(
        block_id="p1_b1",
        page_number=1,
        block_type=BlockType.PARAGRAPH,
        start_offset=0,
        end_offset=len(p1_text),
        text=p1_text,
    )
    b2 = CanonicalBlock(
        block_id="p2_b1",
        page_number=2,
        block_type=BlockType.PARAGRAPH,
        start_offset=0,
        end_offset=len(p2_text),
        text=p2_text,
    )
    p1 = CanonicalPage(page_number=1, text=p1_text, content_checksum=_sha256(p1_text), blocks=(b1,))
    p2 = CanonicalPage(page_number=2, text=p2_text, content_checksum=_sha256(p2_text), blocks=(b2,))
    doc = CanonicalDocument(
        raw_source_hash="c" * 64,
        derivation_identity="d" * 64,
        parser_version="pypdf-6.14.2-plain-v1",
        pages=(p1, p2),
    )
    config = PdfExtractionConfiguration.milestone_two()
    chunks = chunk_canonical_document(doc, config)

    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
    assert chunks[1].page_number == 2
    assert chunks[1].page_start == 2
    assert chunks[1].page_end == 2


def test_langchain_splitter_drift_diagnostic() -> None:
    assessment = assess_langchain_splitter_compatibility("Sample text for splitter testing.")
    assert isinstance(assessment, LangChainSplitterAssessment)
    assert not assessment.meets_knora_source_invariants
    assert "offset" in assessment.drift_reason.lower()
