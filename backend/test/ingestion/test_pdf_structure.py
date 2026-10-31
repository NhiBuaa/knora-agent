from __future__ import annotations

import hashlib

import pytest

from knora.ingestion.pdf_structure import (
    BlockType,
    BoundingBox,
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    CanonicalStructureValidationError,
    CanonicalTable,
    CanonicalTableCell,
    PageCompleteness,
    SourceOrigin,
    canonical_document_from_dict,
    canonical_document_to_dict,
    validate_canonical_document,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _valid_page(
    page_number: int = 1,
    text: str = "Hello world.\n\nSecond block.",
    blocks: tuple[CanonicalBlock, ...] | None = None,
    tables: tuple[CanonicalTable, ...] = (),
    completeness: PageCompleteness | None = None,
) -> CanonicalPage:
    if blocks is None:
        b1 = CanonicalBlock(
            block_id=f"p{page_number}_b1",
            page_number=page_number,
            block_type=BlockType.PARAGRAPH,
            start_offset=0,
            end_offset=12,
            text="Hello world.",
            source_origin=SourceOrigin.NATIVE_TEXT,
        )
        b2 = CanonicalBlock(
            block_id=f"p{page_number}_b2",
            page_number=page_number,
            block_type=BlockType.PARAGRAPH,
            start_offset=14,
            end_offset=27,
            text="Second block.",
            source_origin=SourceOrigin.NATIVE_TEXT,
        )
        blocks = (b1, b2)
    return CanonicalPage(
        page_number=page_number,
        text=text,
        content_checksum=_sha256(text),
        blocks=blocks,
        tables=tables,
        completeness=completeness or PageCompleteness(is_complete=True, status="COMPLETE"),
    )


def _valid_document(pages: tuple[CanonicalPage, ...] | None = None) -> CanonicalDocument:
    return CanonicalDocument(
        raw_source_hash="a" * 64,
        derivation_identity="b" * 64,
        parser_version="pypdf-6.14.2-plain-v1",
        pages=pages if pages is not None else (_valid_page(1), _valid_page(2)),
        is_complete=True,
        completeness_status="COMPLETE",
    )


def test_valid_canonical_document_passes_validation() -> None:
    doc = _valid_document()
    validate_canonical_document(doc)


def test_duplicate_block_ids_rejected() -> None:
    duplicate_blocks = (
        CanonicalBlock(
            block_id="duplicate_id",
            page_number=1,
            block_type=BlockType.PARAGRAPH,
            start_offset=0,
            end_offset=5,
            text="Hello",
        ),
        CanonicalBlock(
            block_id="duplicate_id",
            page_number=1,
            block_type=BlockType.PARAGRAPH,
            start_offset=6,
            end_offset=11,
            text="world",
        ),
    )
    p = CanonicalPage(
        page_number=1,
        text="Hello world",
        content_checksum=_sha256("Hello world"),
        blocks=duplicate_blocks,
        tables=(),
        completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
    )
    doc = _valid_document(pages=(p,))
    with pytest.raises(CanonicalStructureValidationError, match="duplicate block ID"):
        validate_canonical_document(doc)


def test_duplicate_table_ids_rejected() -> None:
    t1 = CanonicalTable(
        table_id="table_1",
        page_number=1,
        num_rows=1,
        num_columns=1,
        cells=(CanonicalTableCell(row_index=0, column_index=0, text="A"),),
    )
    t2 = CanonicalTable(
        table_id="table_1",
        page_number=1,
        num_rows=1,
        num_columns=1,
        cells=(CanonicalTableCell(row_index=0, column_index=0, text="B"),),
    )
    p = _valid_page(tables=(t1, t2))
    doc = _valid_document(pages=(p,))
    with pytest.raises(CanonicalStructureValidationError, match="duplicate table ID"):
        validate_canonical_document(doc)


def test_cyclic_heading_parent_rejected() -> None:
    # A -> B -> A
    b1 = CanonicalBlock(
        block_id="heading_a",
        page_number=1,
        block_type=BlockType.HEADING,
        start_offset=0,
        end_offset=9,
        text="Heading A",
        heading_id="heading_a",
        parent_heading_id="heading_b",
    )
    b2 = CanonicalBlock(
        block_id="heading_b",
        page_number=1,
        block_type=BlockType.HEADING,
        start_offset=11,
        end_offset=20,
        text="Heading B",
        heading_id="heading_b",
        parent_heading_id="heading_a",
    )
    text = "Heading A\n\nHeading B"
    p = CanonicalPage(
        page_number=1,
        text=text,
        content_checksum=_sha256(text),
        blocks=(b1, b2),
        tables=(),
        completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
    )
    doc = _valid_document(pages=(p,))
    with pytest.raises(CanonicalStructureValidationError, match="cyclic heading"):
        validate_canonical_document(doc)


def test_self_cyclic_heading_parent_rejected() -> None:
    b1 = CanonicalBlock(
        block_id="heading_self",
        page_number=1,
        block_type=BlockType.HEADING,
        start_offset=0,
        end_offset=7,
        text="Heading",
        heading_id="heading_self",
        parent_heading_id="heading_self",
    )
    text = "Heading"
    p = CanonicalPage(
        page_number=1,
        text=text,
        content_checksum=_sha256(text),
        blocks=(b1,),
        tables=(),
        completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
    )
    doc = _valid_document(pages=(p,))
    with pytest.raises(CanonicalStructureValidationError, match="cyclic heading"):
        validate_canonical_document(doc)


def test_invalid_page_number_rejected() -> None:
    p = _valid_page(page_number=0)
    doc = _valid_document(pages=(p,))
    with pytest.raises(CanonicalStructureValidationError, match="invalid page number"):
        validate_canonical_document(doc)


def test_invalid_block_range_rejected() -> None:
    # end_offset exceeds len(page.text)
    b = CanonicalBlock(
        block_id="b1",
        page_number=1,
        block_type=BlockType.PARAGRAPH,
        start_offset=0,
        end_offset=999,
        text="Short",
    )
    p = CanonicalPage(
        page_number=1,
        text="Short text",
        content_checksum=_sha256("Short text"),
        blocks=(b,),
        tables=(),
        completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
    )
    doc = _valid_document(pages=(p,))
    with pytest.raises(CanonicalStructureValidationError, match="offset out of bounds"):
        validate_canonical_document(doc)


def test_block_text_mismatch_with_canonical_page_rejected() -> None:
    b = CanonicalBlock(
        block_id="b1",
        page_number=1,
        block_type=BlockType.PARAGRAPH,
        start_offset=0,
        end_offset=5,
        text="World",  # page text has "Hello" at [0:5]
    )
    p = CanonicalPage(
        page_number=1,
        text="Hello there",
        content_checksum=_sha256("Hello there"),
        blocks=(b,),
        tables=(),
        completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
    )
    doc = _valid_document(pages=(p,))
    with pytest.raises(CanonicalStructureValidationError, match="text mismatch"):
        validate_canonical_document(doc)


def test_invalid_bbox_rejected() -> None:
    with pytest.raises(CanonicalStructureValidationError, match="invalid bounding box"):
        BoundingBox(left=100.0, top=50.0, right=50.0, bottom=70.0)  # left > right


def test_table_cell_span_exceeding_grid_rejected() -> None:
    # 2 rows, 2 columns, but cell at row 1 has row_span 2 (1 + 2 = 3 > 2)
    t = CanonicalTable(
        table_id="table_overflow",
        page_number=1,
        num_rows=2,
        num_columns=2,
        cells=(
            CanonicalTableCell(row_index=0, column_index=0, row_span=1, col_span=1, text="r0c0"),
            CanonicalTableCell(
                row_index=1, column_index=0, row_span=2, col_span=1, text="overflow"
            ),
        ),
    )
    p = _valid_page(tables=(t,))
    doc = _valid_document(pages=(p,))
    with pytest.raises(CanonicalStructureValidationError, match="exceeds table grid"):
        validate_canonical_document(doc)


def test_table_cell_grid_collision_rejected() -> None:
    t = CanonicalTable(
        table_id="table_collision",
        page_number=1,
        num_rows=2,
        num_columns=2,
        cells=(
            CanonicalTableCell(row_index=0, column_index=0, row_span=2, col_span=1, text="tall"),
            CanonicalTableCell(
                row_index=1, column_index=0, row_span=1, col_span=1, text="colliding"
            ),
        ),
    )
    p = _valid_page(tables=(t,))
    doc = _valid_document(pages=(p,))
    with pytest.raises(CanonicalStructureValidationError, match="collision"):
        validate_canonical_document(doc)


def test_page_content_checksum_mismatch_rejected() -> None:
    p = CanonicalPage(
        page_number=1,
        text="Authentic content",
        content_checksum="wrong_checksum" + "0" * 50,
        blocks=(),
        tables=(),
        completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
    )
    doc = _valid_document(pages=(p,))
    with pytest.raises(CanonicalStructureValidationError, match="checksum mismatch"):
        validate_canonical_document(doc)


def test_incomplete_page_reflected_in_document() -> None:
    # Page marked incomplete but document claims is_complete=True -> validation error
    p = _valid_page(
        page_number=1,
        completeness=PageCompleteness(
            is_complete=False,
            status="PARTIAL",
            reason="OCR_UNREADABLE_REGION",
            unprocessed_regions=(BoundingBox(left=0, top=0, right=100, bottom=100),),
        ),
    )
    doc = CanonicalDocument(
        raw_source_hash="a" * 64,
        derivation_identity="b" * 64,
        parser_version="pypdf-6.14.2-plain-v1",
        pages=(p,),
        is_complete=True,  # Inconsistent!
        completeness_status="COMPLETE",
    )
    with pytest.raises(
        CanonicalStructureValidationError, match="document completeness inconsistency"
    ):
        validate_canonical_document(doc)


def test_canonical_document_serialization_round_trip() -> None:
    cell1 = CanonicalTableCell(row_index=0, column_index=0, text="H1", is_header=True)
    cell2 = CanonicalTableCell(row_index=0, column_index=1, text="H2", is_header=True)
    table = CanonicalTable(
        table_id="p1_t1",
        page_number=1,
        num_rows=1,
        num_columns=2,
        cells=(cell1, cell2),
        caption="Sample Table",
    )
    b1 = CanonicalBlock(
        block_id="p1_b1",
        page_number=1,
        block_type=BlockType.HEADING,
        start_offset=0,
        end_offset=7,
        text="# Title",
        heading_level=1,
        heading_path=("Title",),
        bbox=BoundingBox(left=10.0, top=20.0, right=100.0, bottom=40.0),
        source_origin=SourceOrigin.NATIVE_TEXT,
    )
    text_content = "# Title"
    page1 = CanonicalPage(
        page_number=1,
        text=text_content,
        content_checksum=_sha256(text_content),
        blocks=(b1,),
        tables=(table,),
        completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
    )
    doc = CanonicalDocument(
        raw_source_hash="f" * 64,
        derivation_identity="d" * 64,
        parser_version="docling-native-cf-v1",
        pages=(page1,),
        document_version="v1",
        is_complete=True,
        completeness_status="COMPLETE",
    )
    d = canonical_document_to_dict(doc)
    restored = canonical_document_from_dict(d)
    assert restored == doc
    validate_canonical_document(restored)
