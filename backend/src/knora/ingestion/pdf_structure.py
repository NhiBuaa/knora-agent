from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum

from knora.domain.errors import KnoraError


class CanonicalStructureValidationError(KnoraError):
    def __init__(self, message: str) -> None:
        super().__init__("CANONICAL_STRUCTURE_VALIDATION_ERROR")
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class BlockType(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_CAPTION = "table_caption"
    FIGURE = "figure"
    HEADER_FOOTER = "header_footer"
    CODE = "code"
    UNKNOWN = "unknown"


class SourceOrigin(StrEnum):
    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    SYNTHETIC = "synthetic"


@dataclass(frozen=True, slots=True)
class BoundingBox:
    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self) -> None:
        if self.left > self.right or self.top > self.bottom:
            msg = (
                f"invalid bounding box: left ({self.left}) > right ({self.right}) "
                f"or top ({self.top}) > bottom ({self.bottom})"
            )
            raise CanonicalStructureValidationError(msg)
        if min(self.left, self.top, self.right, self.bottom) < 0:
            raise CanonicalStructureValidationError("invalid bounding box: negative coordinate")


@dataclass(frozen=True, slots=True)
class CanonicalTableCell:
    row_index: int
    column_index: int
    text: str = ""
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False
    bbox: BoundingBox | None = None

    def __post_init__(self) -> None:
        if self.row_index < 0 or self.column_index < 0:
            raise CanonicalStructureValidationError("table cell coordinates must be non-negative")
        if self.row_span < 1 or self.col_span < 1:
            raise CanonicalStructureValidationError("table cell spans must be at least 1")


@dataclass(frozen=True, slots=True)
class CanonicalTable:
    table_id: str
    page_number: int
    num_rows: int
    num_columns: int
    cells: tuple[CanonicalTableCell, ...]
    caption: str | None = None
    bbox: BoundingBox | None = None
    start_offset: int | None = None
    end_offset: int | None = None


@dataclass(frozen=True, slots=True)
class CanonicalBlock:
    block_id: str
    page_number: int
    block_type: BlockType
    start_offset: int
    end_offset: int
    text: str
    heading_id: str | None = None
    heading_level: int | None = None
    parent_heading_id: str | None = None
    heading_path: tuple[str, ...] = ()
    bbox: BoundingBox | None = None
    source_origin: SourceOrigin = SourceOrigin.NATIVE_TEXT
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class PageCompleteness:
    is_complete: bool = True
    status: str = "COMPLETE"
    reason: str | None = None
    unprocessed_regions: tuple[BoundingBox, ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalPage:
    page_number: int
    text: str
    content_checksum: str
    blocks: tuple[CanonicalBlock, ...] = ()
    tables: tuple[CanonicalTable, ...] = ()
    completeness: PageCompleteness = field(default_factory=PageCompleteness)
    width: float | None = None
    height: float | None = None


@dataclass(frozen=True, slots=True)
class CanonicalDocument:
    raw_source_hash: str
    derivation_identity: str
    parser_version: str
    pages: tuple[CanonicalPage, ...]
    document_version: str | None = None
    is_complete: bool = True
    completeness_status: str = "COMPLETE"
    unprocessed_pages: tuple[int, ...] = ()


def validate_canonical_document(document: CanonicalDocument) -> None:
    seen_block_ids: set[str] = set()
    seen_table_ids: set[str] = set()
    heading_parents: dict[str, str | None] = {}

    for page in document.pages:
        if page.page_number <= 0:
            raise CanonicalStructureValidationError(
                f"invalid page number {page.page_number}: page numbers must be >= 1"
            )

        expected_checksum = hashlib.sha256(page.text.encode()).hexdigest()
        if page.content_checksum != expected_checksum:
            msg = (
                f"checksum mismatch on page {page.page_number}: "
                f"expected {expected_checksum}, got {page.content_checksum}"
            )
            raise CanonicalStructureValidationError(msg)

        if not page.completeness.is_complete and document.is_complete:
            msg = (
                f"document completeness inconsistency: page {page.page_number} "
                "is incomplete but document is marked complete"
            )
            raise CanonicalStructureValidationError(msg)

        for block in page.blocks:
            if block.block_id in seen_block_ids:
                raise CanonicalStructureValidationError(
                    f"duplicate block ID '{block.block_id}' detected"
                )
            seen_block_ids.add(block.block_id)

            if block.page_number != page.page_number:
                msg = (
                    f"block page number mismatch: block {block.block_id} has page "
                    f"{block.page_number}, page is {page.page_number}"
                )
                raise CanonicalStructureValidationError(msg)

            if (
                block.start_offset < 0
                or block.end_offset > len(page.text)
                or block.start_offset > block.end_offset
            ):
                msg = (
                    f"offset out of bounds for block '{block.block_id}': "
                    f"[{block.start_offset}:{block.end_offset}] "
                    f"in page text length {len(page.text)}"
                )
                raise CanonicalStructureValidationError(msg)

            expected_text = page.text[block.start_offset : block.end_offset]
            if block.text != expected_text:
                msg = (
                    f"text mismatch for block '{block.block_id}': "
                    f"expected '{expected_text}', got '{block.text}'"
                )
                raise CanonicalStructureValidationError(msg)

            if block.heading_id:
                heading_parents[block.heading_id] = block.parent_heading_id

        for table in page.tables:
            if table.table_id in seen_table_ids:
                raise CanonicalStructureValidationError(
                    f"duplicate table ID '{table.table_id}' detected"
                )
            seen_table_ids.add(table.table_id)

            if table.page_number != page.page_number:
                msg = (
                    f"table page number mismatch: table {table.table_id} has page "
                    f"{table.page_number}, page is {page.page_number}"
                )
                raise CanonicalStructureValidationError(msg)

            if table.num_rows <= 0 or table.num_columns <= 0:
                msg = (
                    f"invalid table dimensions ({table.num_rows}x{table.num_columns}) "
                    f"for table {table.table_id}"
                )
                raise CanonicalStructureValidationError(msg)

            occupied_cells: set[tuple[int, int]] = set()
            for cell in table.cells:
                if (
                    cell.row_index + cell.row_span > table.num_rows
                    or cell.column_index + cell.col_span > table.num_columns
                ):
                    msg = (
                        f"cell at ({cell.row_index}, {cell.column_index}) with span "
                        f"({cell.row_span}, {cell.col_span}) exceeds table grid "
                        f"({table.num_rows}x{table.num_columns}) in table {table.table_id}"
                    )
                    raise CanonicalStructureValidationError(msg)

                for r in range(cell.row_index, cell.row_index + cell.row_span):
                    for c in range(cell.column_index, cell.column_index + cell.col_span):
                        if (r, c) in occupied_cells:
                            raise CanonicalStructureValidationError(
                                f"grid collision at cell ({r}, {c}) in table {table.table_id}"
                            )
                        occupied_cells.add((r, c))

    for node in heading_parents:
        visited: set[str] = set()
        current: str | None = node
        while current is not None:
            if current in visited:
                raise CanonicalStructureValidationError(
                    f"cyclic heading parent relationship detected involving '{node}'"
                )
            visited.add(current)
            current = heading_parents.get(current)


def bbox_to_dict(b: BoundingBox | None) -> dict | None:
    if b is None:
        return None
    return {"left": b.left, "top": b.top, "right": b.right, "bottom": b.bottom}


def bbox_from_dict(d: dict | None) -> BoundingBox | None:
    if not d:
        return None
    return BoundingBox(
        left=float(d["left"]),
        top=float(d["top"]),
        right=float(d["right"]),
        bottom=float(d["bottom"]),
    )


def canonical_document_to_dict(doc: CanonicalDocument) -> dict:
    return {
        "raw_source_hash": doc.raw_source_hash,
        "derivation_identity": doc.derivation_identity,
        "parser_version": doc.parser_version,
        "document_version": doc.document_version,
        "is_complete": doc.is_complete,
        "completeness_status": doc.completeness_status,
        "unprocessed_pages": list(doc.unprocessed_pages),
        "pages": [
            {
                "page_number": p.page_number,
                "text": p.text,
                "content_checksum": p.content_checksum,
                "width": p.width,
                "height": p.height,
                "completeness": {
                    "is_complete": p.completeness.is_complete,
                    "status": p.completeness.status,
                    "reason": p.completeness.reason,
                    "unprocessed_regions": [
                        bbox_to_dict(r) for r in p.completeness.unprocessed_regions
                    ],
                },
                "blocks": [
                    {
                        "block_id": b.block_id,
                        "page_number": b.page_number,
                        "block_type": (
                            b.block_type.value
                            if hasattr(b.block_type, "value")
                            else str(b.block_type)
                        ),
                        "start_offset": b.start_offset,
                        "end_offset": b.end_offset,
                        "text": b.text,
                        "heading_id": b.heading_id,
                        "heading_level": b.heading_level,
                        "parent_heading_id": b.parent_heading_id,
                        "heading_path": list(b.heading_path),
                        "bbox": bbox_to_dict(b.bbox),
                        "source_origin": (
                            b.source_origin.value
                            if hasattr(b.source_origin, "value")
                            else str(b.source_origin)
                        ),
                        "confidence": b.confidence,
                    }
                    for b in p.blocks
                ],
                "tables": [
                    {
                        "table_id": t.table_id,
                        "page_number": t.page_number,
                        "num_rows": t.num_rows,
                        "num_columns": t.num_columns,
                        "caption": t.caption,
                        "bbox": bbox_to_dict(t.bbox),
                        "start_offset": t.start_offset,
                        "end_offset": t.end_offset,
                        "cells": [
                            {
                                "row_index": c.row_index,
                                "column_index": c.column_index,
                                "text": c.text,
                                "row_span": c.row_span,
                                "col_span": c.col_span,
                                "is_header": c.is_header,
                                "bbox": bbox_to_dict(c.bbox),
                            }
                            for c in t.cells
                        ],
                    }
                    for t in p.tables
                ],
            }
            for p in doc.pages
        ],
    }


def canonical_document_from_dict(d: dict) -> CanonicalDocument:
    pages = []
    for p in d.get("pages", []):
        comp_d = p.get("completeness", {})
        unproc = tuple(
            bbox_from_dict(r) for r in comp_d.get("unprocessed_regions", []) if r is not None
        )
        comp = PageCompleteness(
            is_complete=comp_d.get("is_complete", True),
            status=comp_d.get("status", "COMPLETE"),
            reason=comp_d.get("reason"),
            unprocessed_regions=unproc,
        )
        blocks = []
        for b in p.get("blocks", []):
            blocks.append(
                CanonicalBlock(
                    block_id=b["block_id"],
                    page_number=b["page_number"],
                    block_type=BlockType(b["block_type"]),
                    start_offset=b["start_offset"],
                    end_offset=b["end_offset"],
                    text=b["text"],
                    heading_id=b.get("heading_id"),
                    heading_level=b.get("heading_level"),
                    parent_heading_id=b.get("parent_heading_id"),
                    heading_path=tuple(b.get("heading_path", [])),
                    bbox=bbox_from_dict(b.get("bbox")),
                    source_origin=SourceOrigin(b.get("source_origin", "native_text")),
                    confidence=b.get("confidence"),
                )
            )
        tables = []
        for t in p.get("tables", []):
            cells = [
                CanonicalTableCell(
                    row_index=c["row_index"],
                    column_index=c["column_index"],
                    text=c.get("text", ""),
                    row_span=c.get("row_span", 1),
                    col_span=c.get("col_span", 1),
                    is_header=c.get("is_header", False),
                    bbox=bbox_from_dict(c.get("bbox")),
                )
                for c in t.get("cells", [])
            ]
            tables.append(
                CanonicalTable(
                    table_id=t["table_id"],
                    page_number=t["page_number"],
                    num_rows=t["num_rows"],
                    num_columns=t["num_columns"],
                    cells=tuple(cells),
                    caption=t.get("caption"),
                    bbox=bbox_from_dict(t.get("bbox")),
                    start_offset=t.get("start_offset"),
                    end_offset=t.get("end_offset"),
                )
            )
        pages.append(
            CanonicalPage(
                page_number=p["page_number"],
                text=p["text"],
                content_checksum=p["content_checksum"],
                blocks=tuple(blocks),
                tables=tuple(tables),
                completeness=comp,
                width=p.get("width"),
                height=p.get("height"),
            )
        )
    return CanonicalDocument(
        raw_source_hash=d["raw_source_hash"],
        derivation_identity=d["derivation_identity"],
        parser_version=d["parser_version"],
        pages=tuple(pages),
        document_version=d.get("document_version"),
        is_complete=d.get("is_complete", True),
        completeness_status=d.get("completeness_status", "COMPLETE"),
        unprocessed_pages=tuple(d.get("unprocessed_pages", ())),
    )
