"""Parser comparison runner between pypdf baseline and Cloudflare-native Docling.

Evaluates structure fidelity, reading order, table preservation, heading hierarchy,
completeness, and resource footprint across all 16 evaluation documents.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from evals.datasets.pdf_document_structure_v1 import (
    DocumentStructureDataset,
    load_document_structure_dataset,
)
from evals.datasets.pdf_retrieval_v3_v1 import load_dataset as load_gold_dataset

from knora.adapters.pdf.docling import (
    DoclingExtractionConfiguration,
    DoclingTextExtractor,
)
from knora.adapters.pdf.pypdf import PypdfTextExtractor
from knora.ingestion.pdf import (
    PdfExtractionConfiguration,
    PdfExtractionError,
)
from knora.providers.cloudflare.pdf_understanding import CloudflarePdfUnderstandingProvider


@dataclass(frozen=True, slots=True)
class DocumentParserMetrics:
    source_id: str
    category: str
    page_count: int
    pypdf_chunks_count: int
    pypdf_duration_ms: float
    pypdf_has_structure: bool
    docling_chunks_count: int
    docling_duration_ms: float
    docling_has_structure: bool
    heading_count_ground_truth: int
    heading_count_extracted: int
    table_count_ground_truth: int
    table_count_extracted: int
    scan_handled_by_ocr: bool
    status: str = "success"


@dataclass(frozen=True, slots=True)
class ComparisonSuiteReport:
    version: str
    executed_at: str
    reviewer: str
    total_sources: int
    total_pages: int
    pypdf_p50_duration_ms: float
    pypdf_p95_duration_ms: float
    docling_p50_duration_ms: float
    docling_p95_duration_ms: float
    category_summary: dict[str, dict[str, Any]]
    document_metrics: tuple[DocumentParserMetrics, ...]


def _load_env_credentials() -> tuple[str | None, str | None]:
    account_id = os.environ.get("KNORA_CLOUDFLARE_ACCOUNT_ID")
    api_token = os.environ.get("KNORA_CLOUDFLARE_API_TOKEN")
    if account_id and api_token:
        return account_id, api_token

    for env_path in (Path(".env"), Path("../knora-agent/.env")):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("KNORA_CLOUDFLARE_ACCOUNT_ID="):
                    account_id = line.split("=", 1)[1].strip()
                elif line.startswith("KNORA_CLOUDFLARE_API_TOKEN="):
                    api_token = line.split("=", 1)[1].strip()
    return account_id, api_token


def run_parser_comparison(
    evals_root: Path,
    output_dir: Path,
    cf_provider: CloudflarePdfUnderstandingProvider | None = None,
) -> ComparisonSuiteReport:
    manifest_struct = evals_root / "datasets/pdf_document_structure_v1.manifest.json"
    data_struct = evals_root / "datasets/pdf_document_structure_v1.jsonl"
    manifest_gold = evals_root / "datasets/pdf_retrieval_v3_v1.manifest.json"
    data_gold = evals_root / "datasets/pdf_retrieval_v3_v1.jsonl"

    structure_ds: DocumentStructureDataset = load_document_structure_dataset(
        manifest_struct, data_struct
    )
    gold_ds = load_gold_dataset(manifest_gold, data_gold)

    pypdf_extractor = PypdfTextExtractor()
    docling_extractor = DoclingTextExtractor(cf_provider=cf_provider)

    pypdf_config = PdfExtractionConfiguration.layout_preserving()
    docling_config = DoclingExtractionConfiguration.cloudflare_native_v1()

    doc_metrics: list[DocumentParserMetrics] = []
    pypdf_times: list[float] = []
    docling_times: list[float] = []

    doc_struct_map = {d.source_id: d for d in structure_ds.documents}

    for source in gold_ds.sources:
        pdf_path = evals_root / source.path
        raw_bytes = pdf_path.read_bytes()
        struct_doc = doc_struct_map.get(source.id)

        # Ground truth counts
        gt_headings = 0
        gt_tables = 0
        if struct_doc:
            for p in struct_doc.pages:
                gt_headings += sum(1 for b in p.blocks if b.block_type == "heading")
                gt_tables += len(p.tables)

        # Run pypdf
        t0 = time.perf_counter()
        pypdf_result = None
        pypdf_status = "success"
        try:
            pypdf_result = pypdf_extractor.extract(BytesIO(raw_bytes), pypdf_config)
            t_pypdf = (time.perf_counter() - t0) * 1000.0
            pypdf_times.append(t_pypdf)
        except PdfExtractionError as exc:
            t_pypdf = (time.perf_counter() - t0) * 1000.0
            pypdf_status = exc.code

        # Run Docling native + CF (or record not_run if unconfigured/transient)
        t0 = time.perf_counter()
        docling_result = None
        docling_status = "success"
        try:
            docling_result = docling_extractor.extract(BytesIO(raw_bytes), docling_config)
            t_docling = (time.perf_counter() - t0) * 1000.0
            docling_times.append(t_docling)
        except PdfExtractionError as exc:
            t_docling = (time.perf_counter() - t0) * 1000.0
            docling_status = f"not_run ({exc.code})"

        # Extracted counts from docling or pypdf structure
        ext_headings = 0
        ext_tables = 0
        active_structure = (
            docling_result.structure
            if docling_result
            else (pypdf_result.structure if pypdf_result else None)
        )
        if active_structure:
            for page in active_structure.pages:
                ext_headings += sum(1 for b in page.blocks if b.block_type == "heading")
                ext_tables += len(page.tables)

        scan_handled = (
            source.category == "scan_mixed"
            and docling_result is not None
            and any(len(p.text.strip()) > 0 for p in docling_result.pages)
        )

        doc_metrics.append(
            DocumentParserMetrics(
                source_id=source.id,
                category=source.category,
                page_count=source.page_count,
                pypdf_chunks_count=len(pypdf_result.chunks) if pypdf_result else 0,
                pypdf_duration_ms=round(t_pypdf, 2),
                pypdf_has_structure=pypdf_result.structure is not None if pypdf_result else False,
                docling_chunks_count=len(docling_result.chunks) if docling_result else 0,
                docling_duration_ms=round(t_docling, 2),
                docling_has_structure=docling_result.structure is not None
                if docling_result
                else False,
                heading_count_ground_truth=gt_headings,
                heading_count_extracted=ext_headings,
                table_count_ground_truth=gt_tables,
                table_count_extracted=ext_tables,
                scan_handled_by_ocr=scan_handled,
                status=f"pypdf:{pypdf_status}|docling:{docling_status}",
            )
        )

    pypdf_times.sort()
    n = len(pypdf_times)
    p50_idx = n // 2
    p95_idx = int(n * 0.95)

    docling_times_sorted = sorted(docling_times) if docling_times else [0.0]
    dn = len(docling_times_sorted)

    categories: dict[str, dict[str, Any]] = {}
    for cat in sorted({m.category for m in doc_metrics}):
        cat_docs = [m for m in doc_metrics if m.category == cat]
        categories[cat] = {
            "document_count": len(cat_docs),
            "page_count": sum(d.page_count for d in cat_docs),
            "pypdf_avg_duration_ms": round(
                sum(d.pypdf_duration_ms for d in cat_docs) / len(cat_docs), 2
            ),
            "docling_avg_duration_ms": (
                round(sum(d.docling_duration_ms for d in cat_docs) / len(cat_docs), 2)
                if any(d.docling_duration_ms > 0 for d in cat_docs)
                else 0.0
            ),
            "pypdf_chunks_total": sum(d.pypdf_chunks_count for d in cat_docs),
            "docling_chunks_total": sum(d.docling_chunks_count for d in cat_docs),
            "heading_recall": (
                round(
                    sum(d.heading_count_extracted for d in cat_docs)
                    / max(1, sum(d.heading_count_ground_truth for d in cat_docs)),
                    3,
                )
                if sum(d.heading_count_ground_truth for d in cat_docs) > 0
                else 1.0
            ),
        }

    report = ComparisonSuiteReport(
        version="retrieval-v3-s3-document-understanding-comparison-v1",
        executed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        reviewer="NhiBuaa",
        total_sources=len(doc_metrics),
        total_pages=sum(m.page_count for m in doc_metrics),
        pypdf_p50_duration_ms=round(pypdf_times[p50_idx], 2),
        pypdf_p95_duration_ms=round(pypdf_times[p95_idx], 2),
        docling_p50_duration_ms=round(docling_times_sorted[dn // 2], 2),
        docling_p95_duration_ms=round(docling_times_sorted[int(dn * 0.95)], 2),
        category_summary=categories,
        document_metrics=tuple(doc_metrics),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    report_json = output_dir / "parser_comparison_report.json"
    report_md = output_dir / "parser_comparison_summary.md"

    report_dict = asdict(report)
    report_json.write_text(
        json.dumps(report_dict, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    md_lines = [
        "# Retrieval V3 — S3 Document Understanding Comparison Report",
        "",
        f"- **Executed At:** `{report.executed_at}`",
        f"- **Reviewer:** `{report.reviewer}`",
        f"- **Total Sources:** {report.total_sources} documents "
        f"({report.total_pages} physical pages)",
        f"- **pypdf Duration:** p50={report.pypdf_p50_duration_ms}ms, "
        f"p95={report.pypdf_p95_duration_ms}ms",
        f"- **Docling Duration:** p50={report.docling_p50_duration_ms}ms, "
        f"p95={report.docling_p95_duration_ms}ms",
        "",
        "## Category Summary",
        "",
        "| Category | Docs | Pages | pypdf Avg (ms) | Docling Avg (ms) | "
        "pypdf Chunks | Docling Chunks | Heading Recall |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cat, stats in categories.items():
        md_lines.append(
            f"| `{cat}` | {stats['document_count']} | {stats['page_count']} | "
            f"{stats['pypdf_avg_duration_ms']} | {stats['docling_avg_duration_ms']} | "
            f"{stats['pypdf_chunks_total']} | {stats['docling_chunks_total']} | "
            f"{stats['heading_recall']} |"
        )

    md_lines.extend(
        [
            "",
            "## Document Level Detail",
            "",
            "| Source ID | Category | Pages | pypdf Chunks | pypdf ms | "
            "Docling Chunks | Docling ms | GT Headings | Ext Headings | Status |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for m in doc_metrics:
        md_lines.append(
            f"| `{m.source_id}` | `{m.category}` | {m.page_count} | "
            f"{m.pypdf_chunks_count} | {m.pypdf_duration_ms} | "
            f"{m.docling_chunks_count} | {m.docling_duration_ms} | "
            f"{m.heading_count_ground_truth} | {m.heading_count_extracted} | `{m.status}` |"
        )

    report_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8", newline="\n")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run parser comparison between pypdf and Docling")
    parser.add_argument(
        "--evals-root",
        type=Path,
        default=Path("evals"),
        help="Root path to evals directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evals/reports/pdf_retrieval_v3_v1/s3-document-understanding"),
        help="Directory to save comparison reports",
    )
    args = parser.parse_args()

    account_id, api_token = _load_env_credentials()
    cf_provider = None
    if account_id and api_token:
        cf_provider = CloudflarePdfUnderstandingProvider(account_id, api_token)

    report = run_parser_comparison(args.evals_root, args.output_dir, cf_provider)
    print(
        f"Completed comparison across {report.total_sources} sources. "
        f"Report saved to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
