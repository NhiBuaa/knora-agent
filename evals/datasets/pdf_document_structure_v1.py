"""Independent document structure annotation dataset contract and loader.

Captures canonical structural ground truth (reading order, headings, tables,
repeating headers/footers, and completeness) across the 16 evaluation PDFs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class StructureDatasetContractError(ValueError):
    """Signals dataset contract violation, integrity failure or checksum mismatch."""


class BlockType(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CODE = "code"
    CAPTION = "caption"


@dataclass(frozen=True, slots=True)
class NormalizedBoundingBox:
    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self) -> None:
        for val, name in (
            (self.left, "left"),
            (self.top, "top"),
            (self.right, "right"),
            (self.bottom, "bottom"),
        ):
            if not (0.0 <= val <= 1.0):
                raise StructureDatasetContractError(
                    f"Bounding box coordinate {name}={val} out of bounds [0.0, 1.0]"
                )
        if self.left > self.right or self.top > self.bottom:
            raise StructureDatasetContractError(
                f"Invalid bounding box: left ({self.left}) > right ({self.right}) "
                f"or top ({self.top}) > bottom ({self.bottom})"
            )


@dataclass(frozen=True, slots=True)
class AnnotatedTableCell:
    row_index: int
    column_index: int
    text: str = ""
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False
    bbox: NormalizedBoundingBox | None = None

    def __post_init__(self) -> None:
        if self.row_index < 0 or self.column_index < 0:
            raise StructureDatasetContractError("Cell coordinates must be non-negative")
        if self.row_span < 1 or self.col_span < 1:
            raise StructureDatasetContractError("Cell spans must be at least 1")


@dataclass(frozen=True, slots=True)
class AnnotatedTable:
    table_id: str
    page_number: int
    num_rows: int
    num_columns: int
    cells: tuple[AnnotatedTableCell, ...]
    caption: str | None = None
    bbox: NormalizedBoundingBox | None = None

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise StructureDatasetContractError("Table page number must be >= 1")
        if self.num_rows < 1 or self.num_columns < 1:
            raise StructureDatasetContractError("Table must have at least 1 row and 1 column")
        for cell in self.cells:
            if cell.row_index + cell.row_span > self.num_rows:
                raise StructureDatasetContractError(
                    f"Table cell row out of range: {cell.row_index}+{cell.row_span} "
                    f"> {self.num_rows}"
                )
            if cell.column_index + cell.col_span > self.num_columns:
                raise StructureDatasetContractError(
                    f"Table cell column out of range: {cell.column_index}+{cell.col_span} "
                    f"> {self.num_columns}"
                )


@dataclass(frozen=True, slots=True)
class AnnotatedBlock:
    block_id: str
    page_number: int
    block_type: BlockType
    text: str
    reading_order: int
    bbox: NormalizedBoundingBox | None = None
    heading_level: int | None = None
    parent_heading_id: str | None = None

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise StructureDatasetContractError("Block page number must be >= 1")
        if self.reading_order < 0:
            raise StructureDatasetContractError("Reading order index must be non-negative")
        if self.block_type == BlockType.HEADING and (
            self.heading_level is None or not (1 <= self.heading_level <= 6)
        ):
            raise StructureDatasetContractError(
                f"Heading block must have level 1..6, got {self.heading_level}"
            )


@dataclass(frozen=True, slots=True)
class AnnotatedHeaderFooter:
    region_id: str
    page_number: int
    region_type: str
    text: str
    bbox: NormalizedBoundingBox | None = None

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise StructureDatasetContractError("Header/footer page number must be >= 1")
        if self.region_type not in {"header", "footer"}:
            raise StructureDatasetContractError(
                f"Region type must be 'header' or 'footer', got '{self.region_type}'"
            )


@dataclass(frozen=True, slots=True)
class AnnotatedPage:
    page_number: int
    is_complete: bool
    blocks: tuple[AnnotatedBlock, ...]
    tables: tuple[AnnotatedTable, ...]
    header_footers: tuple[AnnotatedHeaderFooter, ...]
    reference_text: str | None = None
    completeness_reason: str | None = None

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise StructureDatasetContractError("Page number must be >= 1")
        orders = [b.reading_order for b in self.blocks]
        if len(orders) != len(set(orders)):
            raise StructureDatasetContractError(
                f"Duplicate reading_order on page {self.page_number}"
            )


@dataclass(frozen=True, slots=True)
class AnnotatedDocument:
    source_id: str
    source_sha256: str
    category: str
    page_count: int
    pages: tuple[AnnotatedPage, ...]
    is_complete: bool = True

    def __post_init__(self) -> None:
        if len(self.pages) != self.page_count:
            raise StructureDatasetContractError(
                f"Document {self.source_id} page count mismatch: "
                f"{len(self.pages)} != {self.page_count}"
            )
        page_nums = [p.page_number for p in self.pages]
        if page_nums != list(range(1, self.page_count + 1)):
            raise StructureDatasetContractError(
                f"Document {self.source_id} pages must be contiguous 1..{self.page_count}"
            )


@dataclass(frozen=True, slots=True)
class DocumentStructureDataset:
    schema_version: int
    dataset_id: str
    owner: str
    corpus_sha256: str
    dataset_sha256: str
    decision_url: str
    documents: tuple[AnnotatedDocument, ...]


def _parse_bbox(raw: dict | None) -> NormalizedBoundingBox | None:
    if raw is None:
        return None
    return NormalizedBoundingBox(
        left=float(raw["left"]),
        top=float(raw["top"]),
        right=float(raw["right"]),
        bottom=float(raw["bottom"]),
    )


def _parse_table(raw: dict) -> AnnotatedTable:
    cells = tuple(
        AnnotatedTableCell(
            row_index=int(c["row_index"]),
            column_index=int(c["column_index"]),
            text=str(c.get("text", "")),
            row_span=int(c.get("row_span", 1)),
            col_span=int(c.get("col_span", 1)),
            is_header=bool(c.get("is_header", False)),
            bbox=_parse_bbox(c.get("bbox")),
        )
        for c in raw.get("cells", [])
    )
    return AnnotatedTable(
        table_id=str(raw["table_id"]),
        page_number=int(raw["page_number"]),
        num_rows=int(raw["num_rows"]),
        num_columns=int(raw["num_columns"]),
        cells=cells,
        caption=raw.get("caption"),
        bbox=_parse_bbox(raw.get("bbox")),
    )


def _parse_block(raw: dict) -> AnnotatedBlock:
    return AnnotatedBlock(
        block_id=str(raw["block_id"]),
        page_number=int(raw["page_number"]),
        block_type=BlockType(raw["block_type"]),
        text=str(raw["text"]),
        reading_order=int(raw["reading_order"]),
        bbox=_parse_bbox(raw.get("bbox")),
        heading_level=int(raw["heading_level"]) if raw.get("heading_level") is not None else None,
        parent_heading_id=raw.get("parent_heading_id"),
    )


def _parse_header_footer(raw: dict) -> AnnotatedHeaderFooter:
    return AnnotatedHeaderFooter(
        region_id=str(raw["region_id"]),
        page_number=int(raw["page_number"]),
        region_type=str(raw["region_type"]),
        text=str(raw["text"]),
        bbox=_parse_bbox(raw.get("bbox")),
    )


def _parse_page(raw: dict) -> AnnotatedPage:
    return AnnotatedPage(
        page_number=int(raw["page_number"]),
        is_complete=bool(raw.get("is_complete", True)),
        blocks=tuple(_parse_block(b) for b in raw.get("blocks", [])),
        tables=tuple(_parse_table(t) for t in raw.get("tables", [])),
        header_footers=tuple(_parse_header_footer(hf) for hf in raw.get("header_footers", [])),
        reference_text=raw.get("reference_text"),
        completeness_reason=raw.get("completeness_reason"),
    )


def _parse_document(raw: dict) -> AnnotatedDocument:
    return AnnotatedDocument(
        source_id=str(raw["source_id"]),
        source_sha256=str(raw["source_sha256"]),
        category=str(raw["category"]),
        page_count=int(raw["page_count"]),
        pages=tuple(_parse_page(p) for p in raw.get("pages", [])),
        is_complete=bool(raw.get("is_complete", True)),
    )


def load_document_structure_dataset(
    manifest_path: Path | str, data_path: Path | str
) -> DocumentStructureDataset:
    manifest_file = Path(manifest_path)
    data_file = Path(data_path)

    if not manifest_file.exists():
        raise StructureDatasetContractError(f"Manifest not found: {manifest_file}")
    if not data_file.exists():
        raise StructureDatasetContractError(f"Dataset JSONL not found: {data_file}")

    manifest_raw = json.loads(manifest_file.read_text(encoding="utf-8"))
    data_bytes = data_file.read_bytes()
    data_sha = hashlib.sha256(data_bytes).hexdigest()

    expected_data_sha = manifest_raw.get("dataset_sha256")
    if data_sha != expected_data_sha:
        # Check normalized LF line endings for Windows checkout portability (F20)
        normalized_sha = hashlib.sha256(data_bytes.replace(b"\r\n", b"\n")).hexdigest()
        if normalized_sha != expected_data_sha:
            raise StructureDatasetContractError(
                f"Dataset checksum mismatch: expected {expected_data_sha}, got {data_sha}"
            )

    # Verify source PDF files closure
    evals_root = manifest_file.parents[1]
    sources_manifest = manifest_raw.get("sources", [])
    if len(sources_manifest) != 16:
        raise StructureDatasetContractError(
            f"Expected 16 source documents in manifest, got {len(sources_manifest)}"
        )

    for source_entry in sources_manifest:
        pdf_rel = source_entry.get("path")
        pdf_path = evals_root / pdf_rel
        if not pdf_path.exists():
            raise StructureDatasetContractError(f"Source PDF missing: {pdf_path}")
        actual_sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        if actual_sha != source_entry["sha256"]:
            raise StructureDatasetContractError(
                f"Source PDF sha256 mismatch for {source_entry['id']}: "
                f"expected {source_entry['sha256']}, got {actual_sha}"
            )

    documents = []
    lines = data_file.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise StructureDatasetContractError("Dataset JSONL is empty")

    for line in lines:
        if not line.strip():
            continue
        doc = _parse_document(json.loads(line))
        documents.append(doc)

    if len(documents) != 16:
        raise StructureDatasetContractError(
            f"Expected 16 annotated documents, got {len(documents)}"
        )

    return DocumentStructureDataset(
        schema_version=int(manifest_raw.get("schema_version", 1)),
        dataset_id=str(manifest_raw.get("version", "pdf-document-structure-v1")),
        owner=str(manifest_raw.get("owner", "NhiBuaa")),
        corpus_sha256=str(manifest_raw.get("corpus_sha256", "")),
        dataset_sha256=data_sha,
        decision_url=str(manifest_raw.get("decision_url", "")),
        documents=tuple(documents),
    )


def validate_approval(approval_path: Path | str, manifest_path: Path | str) -> None:
    approval_file = Path(approval_path)
    manifest_file = Path(manifest_path)

    if not approval_file.exists():
        raise StructureDatasetContractError(f"Approval file missing: {approval_file}")
    if not manifest_file.exists():
        raise StructureDatasetContractError(f"Manifest file missing: {manifest_file}")

    approval = json.loads(approval_file.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    if approval.get("status") != "approved":
        raise StructureDatasetContractError("Approval status is not 'approved'")
    if approval.get("owner") != manifest.get("owner"):
        raise StructureDatasetContractError("Approval owner mismatch")
    if approval.get("dataset_sha256") != manifest.get("dataset_sha256"):
        raise StructureDatasetContractError("Approval dataset_sha256 mismatch")
    if approval.get("corpus_sha256") != manifest.get("corpus_sha256"):
        raise StructureDatasetContractError("Approval corpus_sha256 mismatch")
