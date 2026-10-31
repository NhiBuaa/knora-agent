# Retrieval V3 — S3 Document Understanding Comparison Report

- **Executed At:** `2026-10-21T14:07:57Z`
- **Reviewer:** `NhiBuaa`
- **Total Sources:** 16 documents (35 physical pages)
- **pypdf Duration:** p50=739.12ms, p95=1106.05ms
- **Docling Duration:** p50=0.0ms, p95=0.0ms

## Category Summary

| Category | Docs | Pages | pypdf Avg (ms) | Docling Avg (ms) | pypdf Chunks | Docling Chunks | Heading Recall |
|---|---|---|---|---|---|---|---|
| `academic` | 3 | 20 | 897.49 | 0.19 | 34 | 0 | 0.0 |
| `clean` | 2 | 3 | 783.02 | 0.06 | 3 | 0 | 0.0 |
| `hard_table` | 3 | 3 | 594.52 | 0.05 | 3 | 0 | 0.0 |
| `hierarchy` | 3 | 4 | 653.92 | 0.06 | 4 | 0 | 0.0 |
| `multi_column` | 2 | 2 | 635.15 | 0.05 | 2 | 0 | 0.0 |
| `scan_mixed` | 3 | 3 | 951.06 | 0.06 | 1 | 0 | 0.0 |

## Document Level Detail

| Source ID | Category | Pages | pypdf Chunks | pypdf ms | Docling Chunks | Docling ms | GT Headings | Ext Headings | Status |
|---|---|---|---|---|---|---|---|---|---|
| `clean-01` | `clean` | 2 | 2 | 823.99 | 0 | 0.05 | 2 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `clean-02` | `clean` | 1 | 1 | 742.05 | 0 | 0.06 | 1 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `hierarchy-01` | `hierarchy` | 1 | 1 | 611.06 | 0 | 0.04 | 6 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `hierarchy-02` | `hierarchy` | 1 | 1 | 601.92 | 0 | 0.07 | 6 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `hierarchy-03` | `hierarchy` | 2 | 2 | 748.78 | 0 | 0.06 | 8 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `columns-01` | `multi_column` | 1 | 1 | 684.8 | 0 | 0.05 | 1 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `columns-02` | `multi_column` | 1 | 1 | 585.51 | 0 | 0.05 | 1 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `table-01` | `hard_table` | 1 | 1 | 584.72 | 0 | 0.05 | 1 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `table-02` | `hard_table` | 1 | 1 | 599.33 | 0 | 0.05 | 1 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `table-03` | `hard_table` | 1 | 1 | 599.52 | 0 | 0.05 | 1 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `scan-01` | `scan_mixed` | 1 | 0 | 927.23 | 0 | 0.04 | 0 | 0 | `pypdf:PDF_TEXT_INSUFFICIENT|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `scan-02` | `scan_mixed` | 1 | 1 | 1106.05 | 0 | 0.08 | 1 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `scan-03` | `scan_mixed` | 1 | 0 | 819.91 | 0 | 0.05 | 0 | 0 | `pypdf:PDF_TEXT_INSUFFICIENT|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `academic-phobert` | `academic` | 6 | 14 | 1018.02 | 0 | 0.12 | 9 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `academic-phonlp` | `academic` | 7 | 13 | 935.32 | 0 | 0.28 | 14 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
| `academic-vit5` | `academic` | 7 | 7 | 739.12 | 0 | 0.17 | 10 | 0 | `pypdf:success|docling:not_run (PDF_EXTRACTOR_UNAVAILABLE)` |
