# Manual Test Guide: PDF derivation, embedding, and CAS activation

## Metadata

- Status: Draft — awaiting explicit human approval; do not implement or execute yet.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub issue #18 — PDF derivation, embedding, and CAS activation
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/18
- Design: docs/design/issue-18-pdf-derivation-activation.md
- Guide revision: `m2-issue-18-r1`
- Approved by: Pending
- Approved at: Pending

## Prerequisites

- Environment: local checkout with PostgreSQL/pgvector and the configured deterministic ObjectStore,
  isolated PDF extractor, deterministic Embedding Provider and worker runtime. The environment
  supports a controlled provider failure, a held worker attempt and an injected final-transaction
  rollback for the cases below.
- Data and state: one authorized Workspace, two text-based PDF fixtures with distinct raw checksums
  under the same `source_key`, and one known active historical Embedding Set for the preservation
  cases. Reset database and object-store state between cases.
- Configuration: immutable Milestone 2 parser, normalizer, chunking and embedding configuration
  IDs are recorded at submission. Test vectors use the configured 1536-dimensional deterministic
  provider and no raw object key, PDF content or credential is written to evidence.
- Observability: authenticated upload and job-status responses, worker lifecycle result, focused
  PostgreSQL derivation/attempt projections, and existing question response with PDF Citation
  Projection. Capture only safe IDs, statuses, checksums, counts and allowlisted error codes.

## Locked Test Cases

### TC-01: Activate one complete derivation through the worker seam

- Purpose: verify Issue #18's primary path: a claimed job reaches `succeeded` only with a complete,
  compatible active Embedding Set.
- Steps:
  1. Submit a valid text-based PDF with an idempotency key and record its accepted job ID, target
     Document Version and pinned configuration IDs.
  2. Run one worker iteration to completion, then poll the job through the authorized status seam.
  3. Ask a question uniquely supported by the PDF through the existing question seam.
- Expected results:
  - The job is `succeeded` with one closed successful attempt, no active lease, and a terminal
    result whose IDs/counts match one complete derivation.
  - The active set belongs to the same Workspace, Document, target Document Version and immutable
    embedding configuration as the job; every persisted vector has the configured dimension.
  - The answer is cited from the new active set. Its PDF Citation Projection has a 1-based
    physical page locator and start-inclusive/end-exclusive normalized-text offsets.
- Evidence to capture:
  - Safe upload/status responses, worker result, derivation IDs/counts, attempt disposition,
    activation-pointer projection and redacted cited answer/provenance fields.

### TC-02: Preserve the existing active knowledge on terminal input/vector failure

- Purpose: prove invalid deterministic worker inputs cannot create partial retrieval-visible
  knowledge or replace a previous active set.
- Steps:
  1. Start with a Document that has an answerable active historical set.
  2. Submit a fixture that produces a deterministic terminal input/configuration/vector failure
     after claim (for example, an invalid vector count or dimension from the controlled provider).
  3. Run the worker and poll the job; ask the historical supported question again.
- Expected results:
  - The job is terminal `failed` after its one counted attempt with only an allowlisted safe code
    and failure reason; it does not schedule a retry.
  - No incomplete Chunk Set or Embedding Set is committed, and the prior active set remains the
    retrieval target and continues to answer the historical question.
  - Evidence contains no provider response, SQL text, object key or PDF content.
- Evidence to capture:
  - Job/attempt terminal projection, before/after active-pointer IDs, derivation-row counts and
    redacted historical question response.

### TC-03: Retry a transient provider failure without duplicating the derivation

- Purpose: verify the Issue #17 retry contract is preserved by the concrete PDF handler.
- Steps:
  1. Configure the controlled Embedding Provider to return one classified transient failure, then
     succeed on its next call for the same submitted PDF.
  2. Run the worker once, advance only the controlled retry eligibility time, then run it again.
  3. Poll status after each iteration and inspect the completed derivation.
- Expected results:
  - First attempt closes `retry_scheduled` with the already-selected retry metadata; the second
    claim starts a new counted attempt only after the schedule is due.
  - The second attempt succeeds and creates or reuses exactly one compatible immutable derivation
    chain; no provider call occurs inside the final database transaction.
  - Retry timing, attempt numbers and terminal success agree with the durable attempt history.
- Evidence to capture:
  - Both safe job projections, attempt-history policy metadata, provider-call count/timing and final
    derivation IDs/counts.

### TC-04: Finish an older claimed job as superseded when the target version is stale

- Purpose: verify activation CAS protects newer source knowledge without wasting retry budget.
- Steps:
  1. Submit PDF version A, claim it and hold its handler before finalization.
  2. Submit and complete distinct PDF version B for the same Document so it becomes the current
     Document Version and has the serving set.
  3. Release A's handler and complete its worker iteration.
- Expected results:
  - A's finalization observes that its target is no longer current and atomically records
    `superseded`, closes its existing attempt and clears its lease. It schedules no retry and does
    not consume another attempt.
  - B remains current and the active/served set; A never replaces it. Replacement identifiers are
    present when available and are Workspace-safe.
- Evidence to capture:
  - Ordered safe status snapshots for A and B, Document current/active/served pointers, A attempt
    history and an answer proving B remains served.

### TC-05: Reconcile duplicate delivery and finalization rollback atomically

- Purpose: cover at-least-once delivery plus the no-partial-write transaction guarantee.
- Steps:
  1. Execute two controlled deliveries of the same claimed PDF work, using the persisted
     transition operation ID for reconciliation where the test environment simulates an ambiguous
     finalization transport result.
  2. In a separate fresh run, inject a failure after tentative derivation-row creation but before
     commit, then inspect the database and retry according to the durable result.
- Expected results:
  - Duplicate/reconciled delivery returns the one authoritative lifecycle result and leaves one
    immutable compatible Chunk Set/Embedding Set chain; it does not rerun remote work solely to
    resolve finalization.
  - The injected rollback leaves no partial Chunk Set, Chunk, Embedding Set, Chunk embedding,
    activation pointer or terminal success. A later valid finalization can create/reuse a complete
    chain.
  - The open attempt is closed exactly once and job/attempt projection correspondence remains
    valid at commit.
- Evidence to capture:
  - Operation ID/result read-back, row-count/constraint checks before and after rollback, attempt
    disposition and final active-pointer projection.

### TC-06: Fence a lease lost during handler work

- Purpose: ensure a late handler cannot publish extraction or embedding output after ownership
  expires or another worker has recovered it.
- Steps:
  1. Claim a valid PDF job and hold its handler while controlled database time passes lease expiry
     and the recovery flow schedules the successor attempt.
  2. Let the original handler complete and attempt success finalization.
  3. Poll the original lifecycle outcome and inspect derivation/activation state.
- Expected results:
  - The original worker receives `Fenced`/`LeaseLost`, commits no success, no retry decision and
    no activation pointer change.
  - Recovery preserves the original counted attempt and schedules or exhausts only through its
    normal durable policy transition; any later due claim owns a distinct lease generation.
- Evidence to capture:
  - Original token and safe lifecycle result, recovery attempt/job projection, before/after active
    pointer, and proof that no original-worker finalization was committed.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
