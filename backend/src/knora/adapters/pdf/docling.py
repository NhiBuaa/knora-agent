from __future__ import annotations

import concurrent.futures
import hashlib
import logging
import re
import tempfile
import time
from contextlib import suppress
from dataclasses import dataclass, replace
from multiprocessing.connection import Connection
from pathlib import Path
from typing import BinaryIO

from knora.adapters.pdf._pypdf_limits import (
    _page_count,
    _page_stream_bytes,
    _PageStreamBudgetExceeded,
)
from knora.adapters.pdf._pypdf_process import (
    _child_send,
    _extract_in_child,
)
from knora.ingestion.pdf import (
    NormalizedPdfPage,
    PdfExtractionConfiguration,
    PdfExtractionError,
    PdfExtractionResult,
)
from knora.ingestion.pdf_chunking import (
    chunk_canonical_document,
    serialize_table_to_markdown,
)
from knora.ingestion.pdf_structure import (
    BlockType,
    BoundingBox,
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    CanonicalTable,
    CanonicalTableCell,
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

    @classmethod
    def cloudflare_native_v2(cls) -> DoclingExtractionConfiguration:
        return cls(
            parser_version="docling-native-cf-v2",
            extraction_options_version="cf-tomarkdown-moondream-v2",
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


@dataclass(frozen=True, slots=True)
class _DoclingChildPage:
    page_number: int
    native_text: str
    blocks: tuple[CanonicalBlock, ...]
    tables: tuple[CanonicalTable, ...]
    images: tuple[tuple[int, float, bytes], ...]
    is_complete: bool
    status: str
    reason: str | None
    width: float
    height: float


def _child_docling_extract(
    pdf_path: str,
    configuration: DoclingExtractionConfiguration,
    connection: Connection,
) -> None:
    logging.getLogger("pypdf").disabled = True
    try:
        from pypdf import PdfReader
        from pypdf.errors import FileNotDecryptedError

        reader = PdfReader(pdf_path, strict=False)
        if reader.is_encrypted:
            _child_send(connection, ("error", "PDF_ENCRYPTED", "ENCRYPTED", False))
            return
        if _page_count(reader, configuration.max_pages) > configuration.max_pages:
            _child_send(connection, ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "PAGE_COUNT", False))
            return
        pages = reader.pages
        if len(pages) > configuration.max_pages:
            _child_send(connection, ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "PAGE_COUNT", False))
            return

        total_stream_bytes = 0
        _child_send(connection, ("ok_start", len(pages)))
        for page_idx, page in enumerate(pages, start=1):
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
                    connection,
                    ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "PAGE_STREAM_SIZE", False),
                )
                return
            total_stream_bytes += stream_bytes
            if total_stream_bytes > configuration.max_total_stream_bytes:
                _child_send(
                    connection,
                    ("error", "PDF_RESOURCE_LIMIT_EXCEEDED", "TOTAL_STREAM_SIZE", False),
                )
                return

            mediabox = getattr(page, "mediabox", None)
            cropbox = getattr(page, "cropbox", None) or mediabox
            crop_left = float(getattr(cropbox, "left", 0.0) if cropbox else 0.0)
            crop_bottom = float(getattr(cropbox, "bottom", 0.0) if cropbox else 0.0)
            crop_width = float(getattr(cropbox, "width", 612.0) if cropbox else 612.0)
            crop_height = float(getattr(cropbox, "height", 792.0) if cropbox else 792.0)

            rotation = int(getattr(page, "rotation", 0) or page.get("/Rotate", 0) or 0) % 360
            if rotation in (90, 270):
                page_width = crop_height
                page_height = crop_width
            else:
                page_width = crop_width
                page_height = crop_height

            def _transform_point(
                x_val: float,
                y_val: float,
                cm_mat: list | tuple | None,
                crop_l: float = crop_left,
                crop_b: float = crop_bottom,
                crop_w: float = crop_width,
                crop_h: float = crop_height,
                rot: int = rotation,
            ) -> tuple[float, float]:
                if cm_mat and len(cm_mat) >= 6:
                    xu = x_val * float(cm_mat[0]) + y_val * float(cm_mat[2]) + float(cm_mat[4])
                    yu = x_val * float(cm_mat[1]) + y_val * float(cm_mat[3]) + float(cm_mat[5])
                else:
                    xu, yu = x_val, y_val
                xr = xu - crop_l
                yr = yu - crop_b
                if rot == 90:
                    return yr, crop_w - xr
                if rot == 180:
                    return crop_w - xr, crop_h - yr
                if rot == 270:
                    return crop_h - yr, xr
                return xr, yr

            text_items: list[tuple[str, float, float, float]] = []
            image_items: list[tuple[str, float, float]] = []
            current_font_size = 12.0

            def visitor_op(
                op: object,
                args: list | tuple,
                cm: list | tuple,
                tm: list | tuple,
                text_items: list[tuple[str, float, float, float]] = text_items,
                image_items: list[tuple[str, float, float]] = image_items,
            ) -> None:
                nonlocal current_font_size
                if op in (b"Tf", "Tf") and len(args) >= 2:
                    with suppress(ValueError, TypeError):
                        current_font_size = float(args[1])
                elif op in (b"Tj", "Tj") and args:
                    text_arg = args[0]
                    text_str = (
                        text_arg.decode("latin-1", errors="replace")
                        if isinstance(text_arg, bytes)
                        else str(text_arg)
                    )
                    if text_str.strip():
                        tx, ty = _transform_point(float(tm[4]), float(tm[5]), cm)
                        text_items.append((text_str.strip(), tx, ty, current_font_size))
                elif op in (b"TJ", "TJ") and args:
                    parts = []
                    for arg in args[0]:
                        if isinstance(arg, (str, bytes)):
                            parts.append(
                                arg.decode("latin-1", errors="replace")
                                if isinstance(arg, bytes)
                                else arg
                            )
                    text_str = "".join(parts).strip()
                    if text_str:
                        tx, ty = _transform_point(float(tm[4]), float(tm[5]), cm)
                        text_items.append((text_str, tx, ty, current_font_size))
                elif op in (b"Do", "Do") and args:
                    ix, iy = _transform_point(0.0, 0.0, cm)
                    image_items.append((str(args[0]), ix, iy))

            with suppress(Exception):
                page.extract_text(visitor_operand_before=visitor_op)

            # Detect grid tables from positioned text items
            rows_dict: dict[float, list[tuple[str, float, float, float]]] = {}
            for item in text_items:
                t, x, y, fs = item
                found_key = None
                for k in rows_dict:
                    if abs(k - y) < 4.0:
                        found_key = k
                        break
                if found_key is None:
                    found_key = y
                    rows_dict[found_key] = []
                rows_dict[found_key].append(item)

            sorted_y = sorted(rows_dict.keys(), reverse=True)
            candidate_grid: list[tuple[float, list[tuple[str, float, float, float]]]] = []
            for y in sorted_y:
                candidate_grid.append((y, sorted(rows_dict[y], key=lambda it: it[1])))

            native_text = (page.extract_text() or "").strip()
            page_images = list(getattr(page, "images", []))
            has_images = len(page_images) > 0

            detected_tables: list[CanonicalTable] = []
            table_y_set: set[float] = set()

            i = 0
            while i < len(candidate_grid):
                if len(candidate_grid[i][1]) >= 2:
                    j = i
                    while j < len(candidate_grid) and len(candidate_grid[j][1]) >= 2:
                        j += 1
                    if j - i >= 2:
                        table_rows = candidate_grid[i:j]
                        cells: list[CanonicalTableCell] = []
                        num_cols = max(len(r[1]) for r in table_rows)
                        for r_idx, (r_y, r_items) in enumerate(table_rows):
                            table_y_set.add(r_y)
                            for c_idx, (c_text, c_x, c_y, c_fs) in enumerate(r_items):
                                top = max(0.0, page_height - c_y - c_fs)
                                bottom = min(page_height, page_height - c_y + 2.0)
                                left = max(0.0, c_x)
                                right = min(page_width, c_x + max(len(c_text) * c_fs * 0.6, 20.0))
                                bbox = BoundingBox(
                                    left=round(left, 2),
                                    top=round(top, 2),
                                    right=round(right, 2),
                                    bottom=round(bottom, 2),
                                )
                                cells.append(
                                    CanonicalTableCell(
                                        row_index=r_idx,
                                        column_index=c_idx,
                                        text=c_text,
                                        is_header=(r_idx == 0),
                                        bbox=bbox,
                                    )
                                )
                        table_bbox = BoundingBox(
                            left=round(min(c.bbox.left for c in cells if c.bbox), 2),
                            top=round(min(c.bbox.top for c in cells if c.bbox), 2),
                            right=round(max(c.bbox.right for c in cells if c.bbox), 2),
                            bottom=round(max(c.bbox.bottom for c in cells if c.bbox), 2),
                        )
                        table_lines = [" ".join(c[0] for c in r_items) for _, r_items in table_rows]
                        table_sample = "\n".join(table_lines)
                        t_start = native_text.find(table_sample)
                        if t_start == -1 and table_lines:
                            first_line = table_lines[0]
                            t_start = native_text.find(first_line)
                            if t_start != -1:
                                last_line = table_lines[-1]
                                last_pos = native_text.find(last_line, t_start)
                                t_end = (
                                    (last_pos + len(last_line))
                                    if last_pos != -1
                                    else (t_start + len(first_line))
                                )
                            else:
                                t_start = None
                                t_end = None
                        elif t_start != -1:
                            t_end = t_start + len(table_sample)
                        else:
                            t_start = None
                            t_end = None

                        tbl = CanonicalTable(
                            table_id=f"p{page_idx}_t{len(detected_tables) + 1}",
                            page_number=page_idx,
                            num_rows=len(table_rows),
                            num_columns=num_cols,
                            cells=tuple(cells),
                            bbox=table_bbox,
                            start_offset=t_start,
                            end_offset=t_end,
                        )
                        detected_tables.append(tbl)
                    i = j
                else:
                    i += 1

            non_table_items = [
                it for it in text_items if not any(abs(it[2] - ty) < 4.0 for ty in table_y_set)
            ]
            prose_blocks: list[CanonicalBlock] = []
            if non_table_items:
                sorted_items = sorted(non_table_items, key=lambda it: (-it[2], it[1]))
                groups: list[list[tuple[str, float, float, float]]] = []
                current_group: list[tuple[str, float, float, float]] = []
                for item in sorted_items:
                    if not current_group:
                        current_group.append(item)
                    else:
                        prev = current_group[-1]
                        y_diff = prev[2] - item[2]
                        has_intervening_image = any(
                            prev[2] > img_y > item[2] for _, _, img_y in image_items
                        )
                        max_fs = max(prev[3], item[3], 12.0)
                        if y_diff > 1.8 * max_fs or has_intervening_image or y_diff < -4.0:
                            groups.append(current_group)
                            current_group = [item]
                        else:
                            current_group.append(item)
                if current_group:
                    groups.append(current_group)

                heading_stack: list[str] = []
                for g_idx, group in enumerate(groups, start=1):
                    lines_dict: dict[float, list[tuple[str, float]]] = {}
                    for it in group:
                        found_k = None
                        for k in lines_dict:
                            if abs(k - it[2]) < 4.0:
                                found_k = k
                                break
                        if found_k is None:
                            found_k = it[2]
                            lines_dict[found_k] = []
                        lines_dict[found_k].append((it[0], it[1]))

                    assembled_lines: list[str] = []
                    for y_key in sorted(lines_dict.keys(), reverse=True):
                        row_items = sorted(lines_dict[y_key], key=lambda x: x[1])
                        assembled_lines.append(" ".join(t for t, _ in row_items))
                    block_text = "\n".join(assembled_lines).strip()
                    if not block_text:
                        continue

                    min_x = min(it[1] for it in group)
                    max_x = max(it[1] + max(len(it[0]) * it[3] * 0.6, 20.0) for it in group)
                    max_y = max(it[2] for it in group)
                    min_y = min(it[2] for it in group)
                    max_fs = max(it[3] for it in group)
                    top = max(0.0, page_height - max_y - max_fs)
                    bottom = min(page_height, page_height - min_y + 2.0)
                    bbox = BoundingBox(
                        left=round(max(0.0, min_x), 2),
                        top=round(top, 2),
                        right=round(min(page_width, max_x), 2),
                        bottom=round(bottom, 2),
                    )

                    block_type = BlockType.PARAGRAPH
                    heading_level = None
                    heading_match = re.match(r"^(#{1,6})\s+(.*)$", block_text)
                    if heading_match:
                        block_type = BlockType.HEADING
                        level = len(heading_match.group(1))
                        heading_level = level
                        title = heading_match.group(2).strip()
                        heading_stack = heading_stack[: level - 1] + [title]

                    prose_blocks.append(
                        CanonicalBlock(
                            block_id=f"p{page_idx}_b{g_idx}",
                            page_number=page_idx,
                            block_type=block_type,
                            start_offset=0,
                            end_offset=len(block_text),
                            text=block_text,
                            heading_level=heading_level,
                            heading_path=tuple(heading_stack),
                            bbox=bbox,
                            source_origin=SourceOrigin.NATIVE_TEXT,
                            confidence=None,
                        )
                    )

            table_blocks: list[CanonicalBlock] = []
            for t_idx, dt in enumerate(detected_tables, start=1):
                tbl_text = serialize_table_to_markdown(dt)
                table_blocks.append(
                    CanonicalBlock(
                        block_id=f"p{page_idx}_tb{t_idx}",
                        page_number=page_idx,
                        block_type=BlockType.TABLE,
                        start_offset=0,
                        end_offset=len(tbl_text),
                        text=tbl_text,
                        bbox=dt.bbox,
                        source_origin=SourceOrigin.NATIVE_TEXT,
                        confidence=None,
                    )
                )

            all_page_blocks = prose_blocks + table_blocks
            if not all_page_blocks and native_text:
                all_page_blocks = DoclingTextExtractor._parse_page_blocks_static(
                    page_idx, native_text, SourceOrigin.NATIVE_TEXT
                )
                assembled_blocks = all_page_blocks
                assembled_page_text = native_text
            else:
                all_page_blocks.sort(
                    key=lambda b: (
                        b.bbox.top if b.bbox else 0.0,
                        b.bbox.left if b.bbox else 0.0,
                    )
                )
                assembled_blocks = []
                text_parts = []
                current_offset = 0
                for idx, b in enumerate(all_page_blocks, start=1):
                    if text_parts:
                        current_offset += 2
                    start = current_offset
                    end = start + len(b.text)
                    current_offset = end
                    text_parts.append(b.text)
                    assembled_blocks.append(
                        replace(
                            b,
                            block_id=f"p{page_idx}_b{idx}",
                            start_offset=start,
                            end_offset=end,
                        )
                    )
                assembled_page_text = "\n\n".join(text_parts)

                updated_detected_tables: list[CanonicalTable] = []
                for dt in detected_tables:
                    matching_block = next(
                        (
                            ab
                            for ab in assembled_blocks
                            if ab.block_type == BlockType.TABLE and ab.bbox == dt.bbox
                        ),
                        None,
                    )
                    if matching_block is not None:
                        updated_detected_tables.append(
                            replace(
                                dt,
                                start_offset=matching_block.start_offset,
                                end_offset=matching_block.end_offset,
                            )
                        )
                    else:
                        updated_detected_tables.append(dt)
                detected_tables = updated_detected_tables

            text_tables = DoclingTextExtractor._extract_tables_from_blocks_static(
                page_idx, assembled_blocks
            )
            all_tables = tuple(
                detected_tables
                + [
                    t
                    for t in text_tables
                    if not any(
                        abs(t.bbox.top - dt.bbox.top) < 4.0
                        for dt in detected_tables
                        if dt.bbox and t.bbox
                    )
                ]
            )

            image_records: list[tuple[int, float, bytes]] = []
            for img_idx, img in enumerate(page_images):
                img_y = page_height / 2.0
                if img_idx < len(image_items):
                    img_y = image_items[img_idx][2]
                image_records.append((img_idx, img_y, img.data))

            page_text_for_page = assembled_page_text if assembled_page_text else native_text
            child_has_native = len(page_text_for_page) >= configuration.minimum_extracted_characters
            child_page = _DoclingChildPage(
                page_number=page_idx,
                native_text=page_text_for_page,
                blocks=tuple(assembled_blocks),
                tables=all_tables,
                images=tuple(image_records),
                is_complete=(child_has_native and not has_images),
                status="COMPLETE"
                if (child_has_native and not has_images)
                else ("INCOMPLETE" if has_images else "EMPTY"),
                reason=None
                if (child_has_native and not has_images)
                else ("UNPROCESSED_PAGE_IMAGES" if has_images else None),
                width=page_width,
                height=page_height,
            )
            _child_send(connection, ("docling_page", page_idx, child_page))

        _child_send(connection, ("ok_end",), wait_for_ack=True)
    except FileNotDecryptedError:
        _child_send(connection, ("error", "PDF_ENCRYPTED", "ENCRYPTED", False))
    except Exception:
        _child_send(connection, ("error", "PDF_MALFORMED", "UNPARSEABLE", False))
    finally:
        with suppress(Exception):
            connection.close()


class DoclingTextExtractor:
    """Document understanding extractor leveraging native parser + Cloudflare Workers AI.

    Never loads local neural weights, VLMs or HuggingFace models (strictly Cloudflare-only).
    """

    _child_target = staticmethod(_child_docling_extract)

    def __init__(
        self,
        cf_provider: CloudflarePdfUnderstandingProvider | None = None,
    ) -> None:
        self._cf_provider = cf_provider

    @staticmethod
    def _copy_to_temporary_file(stream: BinaryIO, max_raw_bytes: int) -> tuple[Path, str, bytes]:
        total = 0
        hasher = hashlib.sha256()
        path: Path | None = None
        chunks: list[bytes] = []
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary:
                path = Path(temporary.name)
                while chunk := stream.read(64 * 1024):
                    total += len(chunk)
                    if total > max_raw_bytes:
                        raise PdfExtractionError(
                            "PDF_RESOURCE_LIMIT_EXCEEDED",
                            reason="RAW_FILE_SIZE",
                        )
                    hasher.update(chunk)
                    temporary.write(chunk)
                    chunks.append(chunk)
            return path, hasher.hexdigest(), b"".join(chunks)
        except BaseException:
            if path is not None:
                with suppress(OSError):
                    path.unlink(missing_ok=True)
            raise

    def extract(
        self,
        stream: BinaryIO,
        configuration: DoclingExtractionConfiguration,
        cancellation: object | None = None,
    ) -> PdfExtractionResult:
        if not isinstance(configuration, DoclingExtractionConfiguration):
            raise PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE",
                reason="INCOMPATIBLE_EXTRACTION_CONFIGURATION",
                retryable=False,
            )

        start_time = time.monotonic()
        timeout = configuration.extraction_timeout_seconds

        def check_limits() -> None:

            if cancellation is not None and getattr(cancellation, "is_cancelled", lambda: False)():
                raise PdfExtractionError("PDF_RESOURCE_LIMIT_EXCEEDED", reason="CANCELLED")

            if time.monotonic() - start_time > timeout:
                raise PdfExtractionError("PDF_RESOURCE_LIMIT_EXCEEDED", reason="TIMEOUT")

        path, raw_source_hash, raw_bytes = self._copy_to_temporary_file(
            stream, configuration.max_raw_bytes
        )
        canonical_pages: list[CanonicalPage] = []
        is_pdf_stream = False
        try:
            try:
                raw_pages = _extract_in_child(path, configuration, self._child_target)
                is_pdf_stream = True
            except PdfExtractionError as exc:
                if exc.code == "PDF_MALFORMED" and exc.reason == "UNPARSEABLE":
                    is_pdf_stream = False
                    raw_pages = ()
                else:
                    raise

            if is_pdf_stream and raw_pages:
                for cp in raw_pages:
                    if isinstance(cp, _DoclingChildPage):
                        page_images = cp.images
                        has_images = len(page_images) > 0
                        has_native = (
                            len(cp.native_text) >= configuration.minimum_extracted_characters
                        )

                        if has_native and not has_images:
                            canonical_pages.append(
                                CanonicalPage(
                                    page_number=cp.page_number,
                                    text=cp.native_text,
                                    content_checksum=hashlib.sha256(
                                        cp.native_text.encode()
                                    ).hexdigest(),
                                    blocks=cp.blocks,
                                    tables=cp.tables,
                                    completeness=PageCompleteness(
                                        is_complete=True, status="COMPLETE"
                                    ),
                                    width=cp.width,
                                    height=cp.height,
                                )
                            )
                        elif has_images:
                            if self._cf_provider is None:
                                canonical_pages.append(
                                    CanonicalPage(
                                        page_number=cp.page_number,
                                        text=cp.native_text,
                                        content_checksum=hashlib.sha256(
                                            cp.native_text.encode()
                                        ).hexdigest(),
                                        blocks=cp.blocks,
                                        tables=cp.tables,
                                        completeness=PageCompleteness(
                                            is_complete=False,
                                            status="INCOMPLETE",
                                            reason="UNPROCESSED_PAGE_IMAGES",
                                        ),
                                        width=cp.width,
                                        height=cp.height,
                                    )
                                )
                            else:
                                ocr_items: list[tuple[float, str]] = []
                                all_ocr_success = True
                                for _img_idx, img_y, img_data in page_images:
                                    remaining = timeout - (time.monotonic() - start_time)
                                    if remaining <= 0:
                                        raise PdfExtractionError(
                                            "PDF_RESOURCE_LIMIT_EXCEEDED", reason="TIMEOUT"
                                        )
                                    check_limits()
                                    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                                    try:
                                        future = executor.submit(
                                            self._cf_provider.ocr_page_image, img_data
                                        )
                                        resp = future.result(timeout=max(0.001, remaining))
                                        check_limits()
                                        t = resp.text.strip()
                                        if t:
                                            ocr_items.append((img_y, t))
                                        else:
                                            all_ocr_success = False
                                    except concurrent.futures.TimeoutError as exc:
                                        raise PdfExtractionError(
                                            "PDF_RESOURCE_LIMIT_EXCEEDED", reason="TIMEOUT"
                                        ) from exc
                                    except PdfExtractionError:
                                        raise
                                    except Exception:
                                        all_ocr_success = False
                                    finally:
                                        executor.shutdown(wait=False, cancel_futures=True)

                                elements: list[
                                    tuple[
                                        float,
                                        str,
                                        SourceOrigin,
                                        BoundingBox | None,
                                        BlockType,
                                        CanonicalTable | None,
                                    ]
                                ] = []
                                for blk in cp.blocks:
                                    if blk.block_type != BlockType.TABLE:
                                        blk_y = cp.height - (blk.bbox.top if blk.bbox else 0.0)
                                        elements.append(
                                            (
                                                blk_y,
                                                blk.text,
                                                SourceOrigin.NATIVE_TEXT,
                                                blk.bbox,
                                                blk.block_type,
                                                None,
                                            )
                                        )

                                updated_tables: list[CanonicalTable] = []
                                for tbl in cp.tables:
                                    tbl_text = serialize_table_to_markdown(tbl)
                                    tbl_y = cp.height - (tbl.bbox.top if tbl.bbox else 0.0)
                                    elements.append(
                                        (
                                            tbl_y,
                                            tbl_text,
                                            SourceOrigin.NATIVE_TEXT,
                                            tbl.bbox,
                                            BlockType.TABLE,
                                            tbl,
                                        )
                                    )

                                for img_y, ocr_text in ocr_items:
                                    top = max(0.0, cp.height - img_y - 20.0)
                                    bottom = min(cp.height, cp.height - img_y + 20.0)
                                    ocr_bbox = BoundingBox(
                                        left=72.0,
                                        top=round(top, 2),
                                        right=min(cp.width, 540.0),
                                        bottom=round(bottom, 2),
                                    )
                                    elements.append(
                                        (
                                            img_y,
                                            ocr_text,
                                            SourceOrigin.OCR,
                                            ocr_bbox,
                                            BlockType.PARAGRAPH,
                                            None,
                                        )
                                    )

                                elements.sort(key=lambda el: el[0], reverse=True)

                                assembled_blocks: list[CanonicalBlock] = []
                                text_parts: list[str] = []
                                current_offset = 0
                                for el_idx, (
                                    _el_y,
                                    el_text,
                                    el_origin,
                                    el_bbox,
                                    el_type,
                                    el_tbl,
                                ) in enumerate(elements, start=1):
                                    if text_parts:
                                        current_offset += 2
                                    start = current_offset
                                    end = start + len(el_text)
                                    current_offset = end
                                    text_parts.append(el_text)
                                    assembled_blocks.append(
                                        CanonicalBlock(
                                            block_id=f"p{cp.page_number}_b{el_idx}",
                                            page_number=cp.page_number,
                                            block_type=el_type,
                                            start_offset=start,
                                            end_offset=end,
                                            text=el_text,
                                            bbox=el_bbox,
                                            source_origin=el_origin,
                                            confidence=None,
                                        )
                                    )
                                    if el_tbl is not None:
                                        updated_tables.append(
                                            replace(el_tbl, start_offset=start, end_offset=end)
                                        )

                                combined = "\n\n".join(text_parts)
                                is_complete = all_ocr_success and bool(ocr_items)
                                canonical_pages.append(
                                    CanonicalPage(
                                        page_number=cp.page_number,
                                        text=combined,
                                        content_checksum=hashlib.sha256(
                                            combined.encode()
                                        ).hexdigest(),
                                        blocks=tuple(assembled_blocks),
                                        tables=tuple(
                                            updated_tables if updated_tables else cp.tables
                                        ),
                                        completeness=PageCompleteness(
                                            is_complete=is_complete,
                                            status="COMPLETE" if is_complete else "INCOMPLETE",
                                            reason=None
                                            if is_complete
                                            else (
                                                "MIXED_PAGE_OCR_FAILED"
                                                if has_native
                                                else "SCANNED_PAGE_OCR_FAILED"
                                            ),
                                        ),
                                        width=cp.width,
                                        height=cp.height,
                                    )
                                )
                        else:
                            canonical_pages.append(
                                CanonicalPage(
                                    page_number=cp.page_number,
                                    text="",
                                    content_checksum=hashlib.sha256(b"").hexdigest(),
                                    blocks=(),
                                    tables=(),
                                    completeness=PageCompleteness(
                                        is_complete=False, status="EMPTY"
                                    ),
                                    width=cp.width,
                                    height=cp.height,
                                )
                            )
        finally:
            with suppress(OSError):
                path.unlink(missing_ok=True)

        check_limits()

        if not is_pdf_stream or not canonical_pages:
            if self._cf_provider is None:
                raise PdfExtractionError(
                    "PDF_EXTRACTOR_UNAVAILABLE",
                    reason="CLOUDFLARE_PROVIDER_UNCONFIGURED",
                    retryable=True,
                )

            remaining = timeout - (time.monotonic() - start_time)
            if remaining <= 0:
                raise PdfExtractionError("PDF_RESOURCE_LIMIT_EXCEEDED", reason="TIMEOUT")
            check_limits()
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                future = executor.submit(self._cf_provider.convert_to_markdown, raw_bytes)
                conversion = future.result(timeout=max(0.001, remaining))
            except concurrent.futures.TimeoutError as exc:
                raise PdfExtractionError("PDF_RESOURCE_LIMIT_EXCEEDED", reason="TIMEOUT") from exc
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
            check_limits()
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
        check_limits()
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

    @staticmethod
    def _parse_markdown_table(
        table_id: str,
        page_number: int,
        table_text: str,
        start_offset: int,
        end_offset: int,
    ) -> CanonicalTable | None:
        lines = [line.strip() for line in table_text.strip().splitlines() if line.strip()]
        if len(lines) < 2:
            return None

        table_lines = [line for line in lines if line.startswith("|") and line.endswith("|")]
        if len(table_lines) >= 2:
            sep_pattern = re.compile(r"^\|(\s*:?-+:?\s*\|)+$")
            has_separator = bool(sep_pattern.match(table_lines[1]))

            def parse_cells(line: str) -> list[str]:
                inner = line[1:-1]
                return [cell.strip() for cell in inner.split("|")]

            rows_data: list[tuple[bool, list[str]]] = []
            for idx, line in enumerate(table_lines):
                if idx == 1 and has_separator:
                    continue
                is_header = idx == 0 and has_separator
                cell_values = parse_cells(line)
                rows_data.append((is_header, cell_values))
        else:
            split_rows = [re.split(r"\t+|\s{2,}", line) for line in lines]
            col_counts = [len(r) for r in split_rows]
            if len(set(col_counts)) != 1 or col_counts[0] < 2:
                return None
            rows_data = [(idx == 0, [c.strip() for c in r]) for idx, r in enumerate(split_rows)]

        if not rows_data:
            return None

        num_columns = max(len(cells) for _, cells in rows_data)
        if num_columns == 0:
            return None
        num_rows = len(rows_data)

        cells: list[CanonicalTableCell] = []
        for r_idx, (is_header, row_cells) in enumerate(rows_data):
            padded = row_cells + [""] * (num_columns - len(row_cells))
            for c_idx, cell_text in enumerate(padded[:num_columns]):
                top = 80.0 + r_idx * 20.0
                bottom = top + 16.0
                left = 72.0 + c_idx * 120.0
                right = left + 100.0
                c_bbox = BoundingBox(
                    left=round(left, 2),
                    top=round(top, 2),
                    right=round(right, 2),
                    bottom=round(bottom, 2),
                )
                cells.append(
                    CanonicalTableCell(
                        row_index=r_idx,
                        column_index=c_idx,
                        text=cell_text,
                        is_header=is_header,
                        bbox=c_bbox,
                    )
                )

        tbl_bbox = BoundingBox(
            left=round(min(c.bbox.left for c in cells if c.bbox), 2),
            top=round(min(c.bbox.top for c in cells if c.bbox), 2),
            right=round(max(c.bbox.right for c in cells if c.bbox), 2),
            bottom=round(max(c.bbox.bottom for c in cells if c.bbox), 2),
        )

        return CanonicalTable(
            table_id=table_id,
            page_number=page_number,
            num_rows=num_rows,
            num_columns=num_columns,
            cells=tuple(cells),
            bbox=tbl_bbox,
            start_offset=start_offset,
            end_offset=end_offset,
        )

    @classmethod
    def _extract_tables_from_blocks_static(
        cls,
        page_number: int,
        blocks: list[CanonicalBlock] | tuple[CanonicalBlock, ...],
    ) -> list[CanonicalTable]:
        tables: list[CanonicalTable] = []
        for idx, block in enumerate(blocks, start=1):
            has_table_shape = (
                block.block_type == BlockType.TABLE
                or ("|" in block.text and "\n" in block.text)
                or (
                    len(block.text.splitlines()) >= 2
                    and any("\t" in line or "  " in line for line in block.text.splitlines())
                )
            )
            if has_table_shape:
                parsed = cls._parse_markdown_table(
                    table_id=f"p{page_number}_t{idx}",
                    page_number=page_number,
                    table_text=block.text,
                    start_offset=block.start_offset,
                    end_offset=block.end_offset,
                )
                if parsed is not None:
                    tables.append(parsed)
        return tables

    def _extract_tables_from_blocks(
        self,
        page_number: int,
        blocks: list[CanonicalBlock] | tuple[CanonicalBlock, ...],
    ) -> list[CanonicalTable]:
        return self._extract_tables_from_blocks_static(page_number, blocks)

    @staticmethod
    def _parse_page_blocks_static(
        page_number: int,
        page_text: str,
        source_origin: SourceOrigin,
        confidence: float | None = None,
        base_offset: int = 0,
        start_block_idx: int = 1,
        full_text: str | None = None,
    ) -> list[CanonicalBlock]:
        raw_sections = [s.strip() for s in re.split(r"(?:\r?\n\s*){2,}", page_text) if s.strip()]
        if not raw_sections:
            return []

        search_corpus = full_text if full_text is not None else page_text
        blocks: list[CanonicalBlock] = []
        heading_stack: list[str] = []
        current_search_idx = base_offset

        for idx_offset, section in enumerate(raw_sections):
            block_idx = start_block_idx + idx_offset
            start = search_corpus.find(section, current_search_idx)
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
            else:
                table_lines = [line.strip() for line in section.splitlines() if line.strip()]
                is_pipe_table = (
                    len(table_lines) >= 2
                    and all(line.startswith("|") and line.endswith("|") for line in table_lines)
                ) or (section.startswith("|") and section.endswith("|"))
                is_grid_table = False
                if not is_pipe_table and len(table_lines) >= 2:
                    split_rows = [re.split(r"\t+|\s{2,}", line) for line in table_lines]
                    col_counts = [len(r) for r in split_rows]
                    if len(set(col_counts)) == 1 and col_counts[0] >= 2:
                        is_grid_table = True

                if is_pipe_table or is_grid_table:
                    block_type = BlockType.TABLE
                    clean_text = section
                else:
                    clean_text = section

            blocks.append(
                CanonicalBlock(
                    block_id=f"p{page_number}_b{block_idx}",
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

    def _parse_page_blocks(
        self,
        page_number: int,
        page_text: str,
        source_origin: SourceOrigin,
        confidence: float | None = None,
        base_offset: int = 0,
        start_block_idx: int = 1,
        full_text: str | None = None,
    ) -> list[CanonicalBlock]:
        return self._parse_page_blocks_static(
            page_number,
            page_text,
            source_origin,
            confidence=confidence,
            base_offset=base_offset,
            start_block_idx=start_block_idx,
            full_text=full_text,
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
            blocks = self._parse_page_blocks(
                page_number, page_text, SourceOrigin.OCR, confidence=ocr_resp.confidence
            )
            tables = self._extract_tables_from_blocks(page_number, blocks)
            return CanonicalPage(
                page_number=page_number,
                text=page_text,
                content_checksum=hashlib.sha256(page_text.encode()).hexdigest(),
                blocks=tuple(blocks),
                tables=tuple(tables),
                completeness=PageCompleteness(is_complete=True, status="COMPLETE"),
            )

        page_text = native_text.strip()
        blocks = self._parse_page_blocks(page_number, page_text, SourceOrigin.NATIVE_TEXT)
        tables = self._extract_tables_from_blocks(page_number, blocks)
        return CanonicalPage(
            page_number=page_number,
            text=page_text,
            content_checksum=hashlib.sha256(page_text.encode()).hexdigest(),
            blocks=tuple(blocks),
            tables=tuple(tables),
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
            tables = self._extract_tables_from_blocks(page_idx, blocks)
            pages.append(
                CanonicalPage(
                    page_number=page_idx,
                    text=p_text,
                    content_checksum=hashlib.sha256(p_text.encode()).hexdigest(),
                    blocks=tuple(blocks),
                    tables=tuple(tables),
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
                    tables=(),
                    completeness=PageCompleteness(is_complete=False, status="EMPTY"),
                ),
            )
        )
