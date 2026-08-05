# Manual Test Guide: Deterministic PDF Extraction and Page-Bounded Chunking

## Metadata

- Status: Approved and locked
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub issue #16 — Deterministic PDF extraction and page-bounded chunking
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/14
- Guide revision: `m2-issue-16-r1`
- Approved by: Nhi (explicit human approval in Codex task)
- Approved at: 2026-08-05T22:04:14+07:00

## Prerequisites

- Environment: local checkout with the pinned `pypdf` dependency and isolated extractor process
  available; no PostgreSQL, ObjectStore, worker claim or Embedding Provider is required for this
  pure module guide.
- Data and state: version-controlled small PDF fixtures for ordinary paragraphs, multiple pages,
  multi-column layout, tables, rotated text, unusual fonts, mixed image/text, empty pages,
  encrypted/password-protected, malformed and textless documents.
- Configuration: pinned parser/extraction-options, normalizer, tokenizer and chunking version IDs;
  baseline budgets of 25 MiB raw, 500 pages, 4 MiB decompressed stream per page, 64 MiB aggregate,
  30-second inspection/extraction timeout and 256 MiB hard extractor RSS/container ceiling.
- Observability: extractor exit classification, normalized page artifacts and Chunk projections;
  no raw PDF or extracted sensitive content is written to logs.

## Locked Test Cases

### TC-01: Reproduce normalized physical pages under one immutable configuration

- Purpose: prove determinism belongs to the Knora adapter rather than an implicit library promise.
- Steps:
  1. Extract the same valid multi-page PDF twice under identical parser/options and normalizer
     versions in fresh child processes.
  2. Compare page ordering, normalized text, checksums and metadata byte-for-byte.
- Expected results:
  - Both runs return the same 1-based physical-page sequence and identical normalized page text and
    checksums.
  - Unicode, whitespace, newlines, control characters and line joining follow the pinned
    normalization contract.
  - The result records exact parser, extraction-options and normalizer version IDs.
- Evidence to capture:
  - Configuration identities, normalized output hashes and deterministic comparison result.

### TC-02: Produce block-aware chunks confined to one physical page

- Purpose: prove the approved chunking policy and provenance invariants.
- Steps:
  1. Process fixtures containing short blocks, packable paragraphs, an oversized block and a blank
     page under the baseline tokenizer/chunking configuration.
  2. Inspect Chunk order, token counts, overlap, offsets and checksums.
- Expected results:
  - Paragraph/block units pack toward 500 tokens with at most 75-token complete-block overlap.
  - Only the block over 650 tokens uses deterministic token-window hard splits; no Chunk exceeds
    650 tokens because of overlap.
  - No Chunk crosses a physical page; every PDF Chunk has `page_start = page_end = page_number`.
  - Character offsets are start-inclusive/end-exclusive into normalized page text, ordinals are
    deterministic, content checksums match the selected text and blank pages create no Chunk.
- Evidence to capture:
  - Chunk projection and assertions for page, ordinal, token count, offsets, overlap and checksum.

### TC-03: Reject encrypted, malformed, unsupported and empty extractable content distinctly

- Purpose: prevent invalid PDFs from becoming successful empty knowledge.
- Steps:
  1. Run fixtures for encrypted/password-protected, malformed, unsupported and textless or
     insufficient-extractable-text PDFs.
- Expected results:
  - Each category returns its approved distinct terminal domain error.
  - No category returns an empty successful corpus or partial Chunk output.
  - Errors expose no password, raw parser exception, file contents, path or stack trace.
- Evidence to capture:
  - Fixture-to-error matrix, zero-output checks and sanitized error/log inspection.

### TC-04: Enforce raw, page and decompressed-stream budgets

- Purpose: stop resource-amplification inputs before they endanger the worker.
- Steps:
  1. Exercise values immediately below, at and above 25 MiB raw and 500 physical pages.
  2. Exercise one page above the 4 MiB decompressed-stream limit and a file above the 64 MiB
     aggregate limit.
- Expected results:
  - At-or-below values follow the documented inclusive boundary; above-limit values return
    terminal `PDF_RESOURCE_LIMIT_EXCEEDED` with the correct internal reason `RAW_FILE_SIZE`,
    `PAGE_COUNT`, `PAGE_STREAM_SIZE` or `TOTAL_STREAM_SIZE`.
  - No over-budget case returns normalized pages or chunks.
- Evidence to capture:
  - Exact fixture sizes/page counts, error reasons and zero-output evidence.

### TC-05: Isolate timeout and memory failures from the parent worker

- Purpose: prove the parent can stop unsafe extraction without losing its own process.
- Steps:
  1. Run a controlled extractor fixture that exceeds the 30-second inspection/extraction timeout.
  2. Run a controlled fixture/process that crosses the 256 MiB hard RSS/container/process ceiling.
  3. After each failure, process one ordinary PDF in the same parent process.
- Expected results:
  - The child is killed and classified as `PDF_RESOURCE_LIMIT_EXCEEDED` with
    `EXTRACTION_TIMEOUT` or `EXTRACTOR_MEMORY` when the file truly exceeds budget.
  - Infrastructure eviction/crash remains distinguishable as retryable for the caller.
  - The parent stays healthy and the subsequent ordinary extraction succeeds deterministically.
- Evidence to capture:
  - Child exit/kill classification, parent liveness and subsequent successful output hash.

### TC-06: Characterize difficult layouts without claiming unsupported quality

- Purpose: record baseline behavior for known `pypdf` extraction risks without asserting OCR,
  table reconstruction or perfect reading order.
- Steps:
  1. Process multi-column, table, rotated-text, unusual-font and mixed image/text fixtures twice.
  2. Compare outputs and inspect whether each fixture has sufficient extractable text.
- Expected results:
  - Each supported fixture is deterministic under the pinned configuration and preserves physical
    page identity even where reading order is imperfect.
  - Mixed image/text succeeds only when extractable text passes the configured sufficiency rule.
  - No result claims OCR, reconstructed table structure, bounding boxes or perfect reading order.
- Evidence to capture:
  - Per-fixture normalized hashes, sufficiency decision and documented baseline observations.

### TC-07: Create new derivation identity when extraction/chunking configuration changes

- Purpose: preserve historical reproducibility when parser behavior evolves.
- Steps:
  1. Process one PDF under the baseline configuration.
  2. Change exactly one of parser/options, normalizer, tokenizer exact version or chunking-policy
     version and process again.
  3. Repeat the baseline unchanged.
- Expected results:
  - A configuration change produces a distinct immutable extraction/chunk derivation identity even
    if visible text happens to match.
  - Repeating the unchanged baseline reproduces the original identity/output.
  - No historical normalized page, Chunk or checksum is mutated.
- Evidence to capture:
  - Configuration/derivation IDs, output hashes and immutability comparison.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
