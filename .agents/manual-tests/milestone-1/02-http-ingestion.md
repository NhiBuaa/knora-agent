# Manual Test Guide: Authenticated HTTP Document Ingestion

## Metadata

- Status: Approved and locked
- Feature: Milestone 1 — Cited RAG
- Slice: GitHub issue #2 — Expose authenticated synchronous ingestion over HTTP
- Authoritative specification: `docs/specs/milestone-1-cited-rag.md`
- Guide revision: `m1-http-ingestion-r1`
- Approved by: NhiBuaa
- Approved at: 2026-07-31T18:49:08+07:00

## Proposed HTTP contract for this slice

- Endpoint: `POST /v1/workspaces/{workspace_id}/documents`.
- Request encoding: `multipart/form-data` with required `source_key` and `file` fields.
- Supported files: Markdown (`.md`, `.markdown`) and plain text (`.txt`, `.text`, or no suffix).
- Errors use `{"error":{"code":"..."}}` and do not expose resource existence or stack traces.
- Missing/invalid API keys return `401 UNAUTHENTICATED`.
- Valid keys used against another Workspace return `403 WORKSPACE_ACCESS_DENIED`.
- Invalid source key/type returns HTTP 400 with its domain error code.
- Synchronous size-limit violations return HTTP 413 with
  `DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION`.

## Prerequisites

- Environment: local checkout with Docker PostgreSQL/pgvector healthy, migrated schema and the
  FastAPI application running in deterministic-local provider mode.
- Data and state: dedicated Workspaces `acceptance-http-a` and `acceptance-http-b`; reset their
  Documents before a new Evaluation run without rewriting old Evaluation history.
- Credentials: enabled test credentials configured only as `key_id`, salted/derived `key_hash`,
  `workspace_id` and `enabled`. Raw keys exist only in the test client/environment and are never
  logged or persisted.
- Corpus: `sample_data/refund-policy.md` plus generated invalid/oversized fixtures.

## Locked Test Cases

### TC-01: Keep health public and minimal

- Purpose: prove service health does not depend on credentials and reveals no dependency or model
  details.
- Steps:
  1. Call `GET /health` without `X-API-Key`.
- Expected results:
  - Response is HTTP 200 with exactly `{"status":"ok","service":"knora-agent"}`.
  - No database, provider, credential, secret, configuration or stack-trace detail is present.
- Evidence to capture:
  - HTTP status and complete response body.

### TC-02: Reject missing and invalid credentials before resource lookup

- Purpose: verify authentication precedes principal creation, authorization and resource lookup.
- Steps:
  1. Submit the same valid multipart ingestion request without `X-API-Key`.
  2. Repeat with an unknown raw key.
  3. Run the focused auth-order integration scenario.
- Expected results:
  - Both HTTP requests return 401 with `UNAUTHENTICATED` and indistinguishable error shapes.
  - No Workspace/Document lookup, embedding-provider call or persistence occurs.
  - Raw keys do not appear in logs or responses.
- Evidence to capture:
  - Both responses and focused auth-order test output.

### TC-03: Deny a valid principal from another Workspace without existence leaks

- Purpose: prove one credential authorizes exactly one Workspace.
- Steps:
  1. Use the enabled key for `acceptance-http-a` against the path for `acceptance-http-b`.
  2. Repeat once when the requested logical Document exists and once when it does not.
- Expected results:
  - Both responses return 403 with `WORKSPACE_ACCESS_DENIED` and the same error shape.
  - No requested-Workspace resource lookup, provider call or persistence occurs.
- Evidence to capture:
  - Both responses and focused Workspace-isolation output.

### TC-04: Create a derivation through the authenticated HTTP adapter

- Purpose: prove HTTP delegates to the same `IngestDocument` seam as CLI and serializes the full
  result contract.
- Steps:
  1. Submit `refund-policy.md` with `source_key=acceptance/refund-policy` using the matching key.
- Expected results:
  - Response is HTTP 201 with `outcome=created` and `activation_changed=true`.
  - It includes non-empty Document, Document Version, Chunk Set, Embedding Set, Chunking
    Configuration and Embedding Configuration IDs plus a positive `chunk_count`.
  - PostgreSQL shows one completed active Embedding Set with 1536-dimensional vectors.
- Evidence to capture:
  - Complete response and focused persistence verification output.

### TC-05: Reuse an identical HTTP ingestion idempotently

- Purpose: verify HTTP status semantics independently from activation state.
- Steps:
  1. Repeat TC-04 with identical key, Workspace, source key and file bytes.
- Expected results:
  - Response is HTTP 200 with `outcome=reused` and `activation_changed=false`.
  - Every resource/configuration ID matches TC-04 and no duplicate derivation is persisted.
- Evidence to capture:
  - Complete second response, ID comparison and focused idempotency output.

### TC-06: Reject invalid source contracts and synchronous limits before provider work

- Purpose: keep HTTP validation and application limits ahead of embedding cost and persistence.
- Steps:
  1. Submit a blank/path-shaped `source_key` with an otherwise valid Markdown file.
  2. Submit an unsupported file type.
  3. Submit a Markdown/plain-text file above the raw 1 MiB limit.
  4. Run focused normalized-token and chunk-count boundary scenarios.
- Expected results:
  - Invalid source keys return HTTP 400 with `INVALID_SOURCE_KEY`.
  - Unsupported files return HTTP 400 with `UNSUPPORTED_DOCUMENT_TYPE`.
  - Every size violation returns HTTP 413 with
    `DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION`.
  - Provider-call count remains zero and no partial derivation is persisted.
- Evidence to capture:
  - HTTP responses and focused provider/persistence boundary-test output.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
