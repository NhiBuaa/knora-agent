# Manual Test Guide: CLI Document Ingestion

## Metadata

- Status: Approved and locked
- Feature: Milestone 1 — Cited RAG
- Slice: GitHub issue #1 — Ingest and activate a versioned Document through CLI
- Authoritative specification: `docs/specs/milestone-1-cited-rag.md`
- Guide revision: `m1-cli-ingestion-r1`
- Approved by: NhiBuaa
- Approved at: 2026-07-31T18:04:39+07:00

## Prerequisites

- Environment: local checkout with Python environment, Docker and PostgreSQL/pgvector running.
- Data and state: dedicated acceptance Workspace `acceptance-m1`; reset it before a new Evaluation
  run, but never rewrite a previous Evaluation record.
- Credentials and permissions: CLI constructs a Workspace Principal for `acceptance-m1` and uses
  the same authorization policy as the HTTP adapter.
- Provider mode: deterministic local Embedding Provider configured for 1536 dimensions.
- Corpus: a small Markdown source with headings and paragraphs plus generated boundary fixtures.

## Locked Test Cases

### TC-01: Create and activate the first derivation chain

- Purpose: prove the CLI traverses the complete IngestDocument interface and creates a usable,
  citation-ready derivation.
- Steps:
  1. Ingest a Markdown fixture under `source_key=acceptance/refund-policy` in `acceptance-m1`.
  2. Record the CLI response and run the focused persistence verification supplied by the slice.
- Expected results:
  - Outcome is `created` and `activation_changed` is true.
  - Response includes Document, Document Version, Chunk Set, Embedding Set and configuration IDs
    plus a positive chunk count.
  - Chunks use the approved token limits and expose ordinal, heading path, line range, content
    checksum and token count.
  - The active pointer selects the completed Embedding Set.
- Evidence to capture:
  - CLI response.
  - Focused verification output showing the active completed set and 1536-dimensional vectors.

### TC-02: Reuse the exact derivation idempotently

- Purpose: verify all three derivation idempotency keys and stable logical source identity.
- Steps:
  1. Repeat TC-01 with identical raw content, source key and configurations.
  2. Compare both CLI responses.
- Expected results:
  - Outcome is `reused` and `activation_changed` is false.
  - Resource and configuration IDs match TC-01.
  - No duplicate Document Version, Chunk Set or Embedding Set is persisted.
- Evidence to capture:
  - Second CLI response and ID comparison.
  - Focused idempotency verification output.

### TC-03: Create a new Document Version for changed content

- Purpose: verify content history changes independently from logical Document identity.
- Steps:
  1. Change the fixture content without changing its source key.
  2. Ingest it with the same Chunking and Embedding Configurations.
- Expected results:
  - Outcome is `created` and `activation_changed` is true.
  - Document ID is unchanged; Document Version, Chunk Set and Embedding Set IDs are new.
  - The new completed Embedding Set becomes active only after atomic persistence succeeds.
- Evidence to capture:
  - CLI response and ID comparison with TC-01.
  - Focused active-pointer verification output.

### TC-04: Keep equal content under different source keys separate

- Purpose: verify `source_key` defines logical Document identity rather than content deduplication.
- Steps:
  1. Ingest the original TC-01 content under `source_key=acceptance/refund-policy-copy`.
- Expected results:
  - Outcome is `created`.
  - A different Document ID is returned despite an equal normalized checksum.
  - The new Document owns its own active Embedding Set.
- Evidence to capture:
  - CLI response and Document ID comparison.

### TC-05: Reject synchronous ingestion limits before embedding

- Purpose: verify raw-size, normalized-token and chunk-count bounds without provider cost or
  partial persistence.
- Steps:
  1. Run the provided boundary fixture for raw content above 1 MiB.
  2. Run fixtures exceeding 50,000 normalized tokens and 100 Chunks.
  3. Inspect the focused provider-call and persistence verification output.
- Expected results:
  - Every request fails with `DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION` before embedding.
  - Provider-call count remains zero for each rejected request.
  - No partial Document Version, Chunk Set or Embedding Set is persisted.
- Evidence to capture:
  - CLI errors and focused boundary-test output.

### TC-06: Reject invalid embedding dimensions atomically

- Purpose: verify production-shaped vector validation and failure atomicity.
- Steps:
  1. Run the focused adapter-contract scenario whose deterministic test adapter returns a vector
     length other than 1536.
  2. Inspect the application result and persistence verification output.
- Expected results:
  - Result is `EMBEDDING_DIMENSION_MISMATCH`.
  - Validation occurs before the persistence transaction.
  - No partial Chunk Set or Embedding Set exists and the previous active pointer is unchanged.
- Evidence to capture:
  - Focused test output and error code.

### TC-07: Prevent late ingestion from replacing newer knowledge

- Purpose: verify revision compare-and-swap protects the active pointer.
- Steps:
  1. Run the focused concurrent-ingestion scenario with two prepared derivations using the same
     expected Document revision.
  2. Allow the newer derivation to commit before the earlier provider call completes.
- Expected results:
  - The first commit increments revision and selects its completed Embedding Set.
  - The late commit fails with `DOCUMENT_CONCURRENTLY_UPDATED` and rolls back its transaction.
  - The active pointer remains on the newer derivation.
- Evidence to capture:
  - Focused concurrency-test output and final active-pointer observation.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
