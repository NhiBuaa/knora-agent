# Manual Test Guide: Durable PDF Submission and Source-Version Commit

## Metadata

- Status: Approved and locked
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub issue #15 — Durable PDF submission and source-version commit
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/14
- Guide revision: `m2-issue-15-r1`
- Approved by: Nhi (explicit human approval in Codex task)
- Approved at: 2026-08-05T22:04:14+07:00

## Prerequisites

- Environment: local checkout with PostgreSQL/pgvector and MinIO healthy, all migrations applied,
  the FastAPI application running in deterministic-local provider mode, and no background worker
  required for queued-submission observations.
- Data and state: dedicated Workspaces `acceptance-m2-submit-a` and `acceptance-m2-submit-b`, reset
  before each Evaluation run without rewriting prior Evaluation history; a small valid text-based
  PDF and a second PDF with different bytes.
- Credentials and permissions: one enabled credential per Workspace, plus missing, invalid and
  disabled key cases. Raw keys remain runtime-only and never enter evidence.
- Observability: focused test projections for Document, Document Version, Original Source Object,
  Ingestion Job, Idempotency Record and immutable configuration identities. These are acceptance
  evidence, not new public interfaces.

## Locked Test Cases

### TC-01: Persist a streamed PDF and acknowledge one durable queued job

- Purpose: prove the request process durably accepts source and job state without parsing,
  embedding or loading the complete PDF in memory.
- Steps:
  1. Submit the valid PDF to `acceptance-m2-submit-a` with a canonical source key and a new
     `Idempotency-Key`.
  2. Capture the complete response and inspect the object/job/source-version projections before
     any worker is started.
- Expected results:
  - The response is HTTP 202 with `submission_outcome=created`, a non-empty Ingestion Job ID and
    `status=queued`.
  - MinIO contains one immutable object under a server-generated opaque key with matching
    Workspace, raw SHA-256, byte size and PDF media type; ETag is not used as the checksum.
  - One durable job and immutable configuration snapshot exist; no parser, chunker or Embedding
    Provider call occurred.
  - Upload handling used the streaming ObjectStore seam and did not materialize the complete
    object in application memory.
- Evidence to capture:
  - HTTP status/body, sanitized ObjectStore metadata, provider/parser call counts and focused
    persistence projection.

### TC-02: Commit source identity and current pointer atomically

- Purpose: prove PDF source history is independent from later derivation work.
- Steps:
  1. Inspect the Document and Document Version created or reused by TC-01.
  2. Trigger a controlled database failure during the source-version/current-pointer transaction
     in an isolated acceptance scenario.
- Expected results:
  - Successful submission stores one PDF Document Version identified by `(document_id,
    raw_sha256)`, assigns the next sequential `version_number`, and atomically points
    `current_document_version_id` to it.
  - The controlled failure commits neither the new version nor the pointer update and leaves no
    cross-Document/Workspace reference.
  - No Chunk Set or Embedding Set is required for the source version to be current.
- Evidence to capture:
  - Before/after Document/version projection and controlled rollback result.

### TC-03: Replay and conflict on scoped request idempotency

- Purpose: distinguish request replay from content and derivation deduplication.
- Steps:
  1. Repeat TC-01 with the same Workspace, operation, Idempotency-Key and immutable request
     fingerprint.
  2. Reuse the same key with different PDF bytes or immutable configuration IDs.
  3. Repeat the same key value in the other Workspace.
- Expected results:
  - The exact replay returns the same job/response with `submission_outcome=idempotency_replay` and
    does not create another object, version or job.
  - Changed fingerprint returns `IDEMPOTENCY_KEY_CONFLICT` without mutation.
  - The other Workspace's scoped key is independent and cannot reveal the first Workspace's job.
  - The Idempotency Record uses the approved 24-hour retention metadata.
- Evidence to capture:
  - Response matrix and per-Workspace record/object counts and identities.

### TC-04: Separate PDF Document Version identity from derivation target identity

- Purpose: ensure configuration changes reprocess one source revision rather than manufacturing
  source history.
- Steps:
  1. Submit the same source key and identical PDF bytes under the same configuration versions.
  2. Submit the same bytes under a changed immutable parser, normalizer, chunking or embedding
     configuration version ID with a new Idempotency-Key.
  3. Submit changed PDF bytes under the same source key.
- Expected results:
  - Identical bytes reuse the same Document Version.
  - Configuration-only change reuses that Document Version but creates or targets a distinct
    derivation fingerprint/job as applicable.
  - Changed raw SHA-256 creates a new sequential Document Version and advances the current pointer.
  - Filename, upload timestamp and object key do not affect either fingerprint.
- Evidence to capture:
  - Version/job/config identity comparison and uniqueness projections.

### TC-05: Resolve concurrent duplicate and competing uploads through database constraints

- Purpose: prove concurrency safety does not depend on request ordering or queue behavior.
- Steps:
  1. Submit two concurrent requests with the same idempotency key and fingerprint.
  2. Submit two concurrent requests for the same source key with identical bytes but distinct
     request keys.
  3. Submit two concurrent changed-byte versions for the same source key.
- Expected results:
  - Each duplicate case produces one durable identity and an equivalent replay/dedup response.
  - Unique constraints or atomic insert prevent duplicate Idempotency Records, Document Versions
    and derivation-target jobs.
  - Competing changed versions serialize or use CAS, receive unique sequential version numbers and
    leave exactly one explicit current pointer.
- Evidence to capture:
  - Concurrency timeline, all responses and database uniqueness/current-pointer projections.

### TC-06: Enforce Workspace authorization and pointer ownership before lookup

- Purpose: prevent submission and source-version state from leaking across tenants.
- Steps:
  1. Submit with missing, invalid and disabled credentials.
  2. Use Workspace A's valid key against Workspace B's upload path for an existing and nonexistent
     source key.
  3. Attempt focused cross-Workspace current-version and active-set pointer assignments and hard
     deletion of referenced resources.
- Expected results:
  - Missing/invalid/disabled keys return indistinguishable 401 `UNAUTHENTICATED` responses before
    Workspace/object/database work.
  - Cross-Workspace requests return 403 `WORKSPACE_ACCESS_DENIED` without existence leaks or
    persisted objects/jobs.
  - Database constraints reject cross-owner pointers and deletion of current/active resources.
- Evidence to capture:
  - Sanitized response matrix, zero-side-effect evidence and constraint results.

### TC-07: Preserve Milestone 1 synchronous ingestion behavior

- Purpose: ensure the new PDF submission path does not regress existing Markdown/plain-text
  ingestion.
- Steps:
  1. Execute the approved Milestone 1 CLI and authenticated HTTP ingestion scenarios for new,
     reused, oversized and invalid inputs.
  2. Run the focused Milestone 1 ingestion regression suites.
- Expected results:
  - Existing Markdown/plain-text requests retain their synchronous 201/200 outcomes, errors,
    normalized-content identity and complete activation behavior.
  - The existing CLI still crosses `IngestDocument.execute(...)` and never requires MinIO or the
    PDF background worker.
  - No Milestone 1 test or public response contract regresses.
- Evidence to capture:
  - CLI/HTTP outputs and focused regression test summary.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
