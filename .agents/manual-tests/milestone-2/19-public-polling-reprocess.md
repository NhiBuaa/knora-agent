# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft — awaiting explicit human approval; do not implement or execute yet.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #19 — Public polling, reprocess, and PDF citation integration
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/19
- Parent design ledger: https://github.com/NhiBuaa/knora-agent/issues/14
- Guide revision: `m2-issue-19-r1`
- Approved by: Pending
- Approved at: Pending

## Prerequisites

- Environment: a local PostgreSQL/pgvector-backed Knora checkout with the deterministic ObjectStore,
  isolated PDF extractor, deterministic embedding and generation providers, authenticated HTTP app,
  and worker runner. The environment can hold a claimed job, advance controlled retry/lease time,
  and observe safe job/document projections.
- Data and state: two authorized Workspaces with distinct credentials; a text-based PDF fixture
  containing one unique answerable fact; a changed-PDF fixture under the same `source_key`; and a
  historical Document Version fixture. Reset database, object store, worker and test-provider state
  between cases.
- Configuration: record immutable parser, normalizer, chunking and embedding configuration IDs at
  submission time. Provide both an earlier job configuration and a newer active configuration for
  reprocess snapshot checks.
- Observability: capture only HTTP status, headers and response bodies with safe IDs; controlled
  worker results; and read-only database projections for job/document/version/configuration
  relationships. Do not record object keys, PDF content, API keys, provider payloads, SQL text or
  stack traces.

## Locked Test Cases

### TC-01: Upload publishes the prescribed HTTP acceptance contract

- Purpose: cover created/reused non-terminal submissions and terminal replay/deduplication without
  exposing an internal lifecycle representation.
- Steps:
  1. Submit a valid PDF with a new scoped `Idempotency-Key`; retain the safe response fields.
  2. Repeat the request while its job is non-terminal, then complete the job through the worker.
  3. Repeat the original idempotency request and submit an eligible matching fingerprint request
     after terminal completion.
- Expected results:
  - A created or reused non-terminal result is `202 Accepted`; a terminal idempotency replay or
    fingerprint deduplication is `200 OK`.
  - Every response contains `ingestion_job_id`, `submission_outcome` (`created`,
    `idempotency_replay` or `deduplicated`) and exactly one public status.
  - The public status is one of `queued`, `processing`, `retry_scheduled`, `succeeded`,
    `superseded` or `failed`; no internal state or raw storage detail is disclosed.
- Evidence to capture:
  - Redacted request/response pairs, HTTP statuses and the safe job IDs proving reuse rather than
    duplicate job creation.

### TC-02: Authorized polling is safe, cache-resistant, and distinguishes serving from lifecycle

- Purpose: verify the complete Workspace-scoped polling projection and the non-leaking lookup
  boundary.
- Steps:
  1. Poll one job while queued/processing, while retry-scheduled (using controlled transient
     failure), and after a terminal outcome.
  2. For each state, inspect response headers and nullable/conditional fields.
  3. Poll an unknown ID and poll the first Workspace's job using the second Workspace credential.
- Expected results:
  - Polling returns attempt count and maximum, RFC 3339 UTC lifecycle timestamps, terminal
    result/error when applicable, and either `poll_after_seconds` or `Retry-After`; it returns
    `next_attempt_at` only when retry-scheduled and sends `Cache-Control: no-store`.
  - The same snapshot exposes target/current/nullable-served Document Version IDs and one
    server-computed `serving_state` of `unavailable`, `current` or `previous`; this does not
    replace `status`.
  - Authentication and authorization precede lookup. Unknown and cross-Workspace requests both
    return `404 INGESTION_JOB_NOT_FOUND` with indistinguishable safe bodies.
- Evidence to capture:
  - Safe polling bodies/headers for each lifecycle state and the two redacted 404 responses.

### TC-03: Previous active evidence remains served through processing and failure

- Purpose: prove that a newer source-version job never makes incomplete or failed work retrievable.
- Steps:
  1. Establish an answerable active PDF version A for one Document.
  2. Submit changed version B under the same `source_key`, hold it while processing, and poll B.
  3. Cause B to reach a safe terminal failure, then ask the version-A-supported question before,
     during and after B's processing.
- Expected results:
  - B's polling projection identifies B as target/current and A as nullable served, with
    `serving_state=previous` while A remains active.
  - The question endpoint continues to cite A before and after B's terminal failure; B contributes
    no partial evidence and no changed answer contract.
  - Failure reason and error code are safe and distinct from the public `failed` status.
- Evidence to capture:
  - Ordered safe job/document projections and redacted question responses showing the cited
    Document Version remains A.

### TC-04: Reprocess accepts only the current version and snapshots immutable configuration

- Purpose: verify authorization, audit/idempotency boundary, current-version guard and configuration
  selection without allowing the worker to resolve mutable configuration later.
- Steps:
  1. Request reprocess for the current Document Version with a new scoped `Idempotency-Key` using
     `config_mode=same_as_job`; record its accepted generation and configuration IDs.
  2. Request reprocess for the same current version with `config_mode=current` after setting a
     distinct active configuration; hold the worker, then change the mutable active configuration.
  3. Try reprocess without required authorization/key and target a historical Document Version.
- Expected results:
  - Each accepted generation records `reprocess_of_job_id`, resets its attempt budget, preserves
    the prior job, and has an auditable accepted request.
  - `same_as_job` copies the exact earlier immutable configuration IDs; `current` snapshots IDs at
    creation, and the held worker uses those recorded IDs despite later mutable changes.
  - Unauthorized/missing-key requests fail safely before lookup or creation, and a historical
    target returns `409 DOCUMENT_VERSION_NOT_CURRENT`.
- Evidence to capture:
  - Redacted request/response pairs, before/after job/configuration projections, worker input
    configuration IDs and the safe 409/error responses.

### TC-05: Reprocess deduplicates eligible work and supersedes a stale generation safely

- Purpose: cover the fresh-generation identity, repeat submission behavior and stale CAS outcome.
- Steps:
  1. Submit the same eligible current-version/configuration reprocess request twice while it is
     processing or after success.
  2. In a separate run, hold reprocess generation A, advance the Document current version through
     a newer accepted/completed update, then release A.
- Expected results:
  - Eligible equal work is reused rather than creating another processing/succeeded generation;
    the prior immutable job is never rewritten.
  - A stale A completes as `superseded`, does not spend another retry attempt, and never replaces
    the current/served version. Replacement metadata is present only when safely available.
- Evidence to capture:
  - Generation IDs and immutable linkage, attempt counts, ordered safe job snapshots and current/
    active/served pointer projections.

### TC-06: Cited answers project canonical PDF provenance while preserving legacy citations

- Purpose: prove the public citation contract is document-version-pinned and backward compatible.
- Steps:
  1. Complete one PDF ingestion/reprocess and ask a question uniquely supported by its active PDF.
  2. Inspect the returned citation and compare its Document Version/Chunk identity provenance with
     the persisted active evidence.
  3. Ask a question backed by a legacy non-PDF citation fixture.
- Expected results:
  - The PDF answer cites only active evidence and projects a 1-based physical page range plus
    half-open normalized-text offsets, resolved server-side and pinned to the Document Version and
    Chunk identity.
  - Existing citation fields and refusal behavior remain compatible; legacy citations retain their
    valid nullable PDF locator fields.
- Evidence to capture:
  - Redacted PDF and legacy question responses plus read-only provenance projection (safe IDs,
    page range and offsets only).

### TC-07: End-to-end tenant isolation holds across upload, worker, polling and answer

- Purpose: exercise the approved integration seam with cross-Workspace access denied without
  resource-existence leakage.
- Steps:
  1. In Workspace A, upload the unique PDF, run the worker, poll to terminal success and ask the
     supporting question.
  2. Using Workspace B credentials, attempt to poll/reprocess A's job/version and ask for A's
     unique fact.
- Expected results:
  - Workspace A observes `upload → worker → poll → cited answer` with only the activated PDF
    evidence.
  - Workspace B receives the same safe unknown/cross-workspace lookup behavior, cannot reprocess
    A's version, and receives the existing refusal contract for A's fact.
  - No percentage progress, token streaming, SSE or UI behavior is introduced.
- Evidence to capture:
  - Safe end-to-end A responses, redacted B authorization/404/refusal responses and a route/API
    surface check showing no streaming/progress response.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
