# Manual Test Guide: Concurrency and Workspace Isolation Failure Semantics

## Metadata

- Status: Approved and locked
- Feature: Milestone 1 — Cited RAG
- Slice: GitHub issue #5 — Enforce concurrency and Workspace isolation failure semantics
- Authoritative specification: `docs/specs/milestone-1-cited-rag.md`
- Guide revision: `m1-concurrency-workspace-isolation-r1`
- Approved by: Nhi (explicit human approval in Codex task)
- Approved at: 2026-07-31T21:04:04+07:00

## Prerequisites

- Environment: local checkout with Docker PostgreSQL/pgvector healthy, migrated schema and the
  FastAPI application running in deterministic-local provider mode. Execute focused persistence
  checks against PostgreSQL rather than substituting an in-memory database.
- Data and state: dedicated Workspaces `acceptance-isolation-a` and `acceptance-isolation-b`, each
  with distinct logical Documents and overlapping content. Reset these Workspaces before a new
  Evaluation run without rewriting prior Evaluation history.
- Credentials and permissions: one enabled test credential per acceptance Workspace plus missing,
  invalid and disabled key cases. Raw keys remain only in the test client/environment; evidence
  records use safe key IDs or fingerprints.
- Concurrency control: a controllable Embedding Provider or synchronization barrier that can pause
  one ingestion after it reads Document revision and release it after a newer ingestion commits.
- Persistence observability: focused projections may inspect Document revision/active pointer and
  counts/identities of Document Versions, Chunk Sets and Embedding Sets. These projections are
  test-only evidence for the PostgreSQL adapter, not new public application interfaces.

## Locked Test Cases

### TC-01: Authenticate and authorize before any Workspace resource lookup

- Purpose: prevent credential failures and cross-Workspace requests from revealing whether a
  Document, Chunk, trace or other resource exists.
- Steps:
  1. Submit otherwise identical ingestion and Question Requests with a missing key, invalid key,
     disabled key, the matching Workspace key and the other Workspace's valid key.
  2. Repeat mismatched-Workspace requests for both an existing and nonexistent logical resource.
  3. Observe the application-service invocation and persistence lookup seams.
- Expected results:
  - Missing, invalid and disabled keys return HTTP 401 `UNAUTHENTICATED`; no Workspace lookup,
    embedding, retrieval or generation occurs.
  - A valid principal targeting another Workspace returns HTTP 403 `WORKSPACE_ACCESS_DENIED`
    before resource lookup.
  - Existing and nonexistent resource variants return indistinguishable authorization failures;
    no response discloses existence, database/provider details or raw credentials.
  - A matching principal reaches the shared application seam and preserves the normal response
    contract.
- Evidence to capture:
  - Sanitized HTTP responses and focused call-order observations for ingestion and questions.

### TC-02: Preserve Workspace isolation through the CLI ingestion seam

- Purpose: prove the CLI bypasses only HTTP credential parsing and cannot use one explicit
  Workspace Principal to write another Workspace's data.
- Steps:
  1. Ingest one source into `acceptance-isolation-a` through the CLI with its explicit Workspace.
  2. Invoke the shared `IngestDocument` seam with a principal for `acceptance-isolation-a` and a
     command targeting `acceptance-isolation-b`.
  3. Query both Workspaces through focused persistence projections.
- Expected results:
  - The valid CLI ingestion creates or reuses resources only in `acceptance-isolation-a`.
  - Principal/command mismatch fails with `WORKSPACE_ACCESS_DENIED` before Document lookup or
    Embedding Provider work.
  - No Document, derivation or active pointer is created or changed in
    `acceptance-isolation-b` by the mismatched invocation.
- Evidence to capture:
  - CLI result/error, provider call count and per-Workspace persistence projections.

### TC-03: Reject a late concurrent ingestion and roll back its complete derivation

- Purpose: prove Document revision compare-and-swap prevents an older provider call from replacing
  a newer activation or leaving partial immutable state.
- Steps:
  1. Seed one active Document version and record its Document revision, active Embedding Set and
     derivation counts.
  2. Start ingestion A for new content and pause its provider after it reads the expected revision.
  3. Complete ingestion B for different content on the same Workspace/source key, then release A.
  4. Inspect A's error and the final PostgreSQL state; retry A's content as a fresh ingestion.
- Expected results:
  - B commits successfully, increments Document revision and owns the active Embedding Set.
  - A returns `DOCUMENT_CONCURRENTLY_UPDATED`; its transaction rolls back completely and cannot
    replace B's active pointer.
  - No Document Version, Chunk Set, Embedding Set or Chunk Embedding unique to failed A remains.
  - Retrying A reads the new revision and may commit normally, demonstrating the failed attempt did
    not poison idempotency state.
- Evidence to capture:
  - Synchronization timeline, both ingestion outcomes and before/after derivation projections.

### TC-04: Enforce active Embedding Set relational invariants

- Purpose: ensure an active pointer can reference only a completed Embedding Set belonging to the
  same Document, Workspace and required Embedding Configuration and cannot be deleted underneath
  retrieval.
- Steps:
  1. Create completed Embedding Sets for two Documents in different Workspaces and one alternate
     Embedding Configuration; create or simulate a non-completed set where the schema permits it.
  2. Attempt focused persistence operations assigning each invalid set as a Document's active
     pointer.
  3. Attempt to delete a currently active Embedding Set.
- Expected results:
  - Cross-Document, cross-Workspace, alternate-configuration and non-completed active assignments
    are rejected atomically.
  - The prior active pointer and Document revision remain unchanged after every rejected update.
  - Deleting an active Embedding Set fails through `ON DELETE RESTRICT`; no dependent derivation is
    partially removed.
  - A valid completed same-Document/workspace/configuration set can be activated through the
    compare-and-swap path.
- Evidence to capture:
  - Constraint/application errors and before/after active-pointer plus derivation projections.

### TC-05: Keep failed ingestion atomic before and during persistence

- Purpose: prove provider validation and transaction failures cannot leave partial derivations or
  disturb the last known-good activation.
- Steps:
  1. Record a Document's active pointer, revision and derivation counts after a successful
     ingestion.
  2. Run new-content ingestions with a vector count mismatch, 1535-dimensional vector and
     provider/model identity mismatch.
  3. Trigger one controlled persistence failure after derivation reconciliation begins but before
     commit.
- Expected results:
  - Provider output failures return `EMBEDDING_DIMENSION_MISMATCH` or the explicit configuration
    mismatch error before any database write.
  - The controlled transaction failure rolls back every new Document Version, Chunk Set,
    Embedding Set, Chunk and vector written in that transaction.
  - Every failed attempt preserves the prior active pointer and Document revision.
  - Client-visible errors contain only stable Knora codes, not raw vector, SQL or provider data.
- Evidence to capture:
  - Error results and before/after PostgreSQL projections for every failure scenario.

### TC-06: Retrieve only authorized active state under adversarial similarity

- Purpose: prove Workspace, Active Embedding Set and Embedding Configuration predicates execute
  inside SQL even when forbidden Chunks would otherwise rank first.
- Steps:
  1. Seed near-identical high-similarity Chunks in both Workspaces, an inactive historical set and
     an alternate Embedding Configuration; make forbidden candidates score above the authorized
     active candidate.
  2. Ask the question using the credential for `acceptance-isolation-a` and inspect focused
     retrieval output plus the persisted Question Trace.
  3. Repeat for `acceptance-isolation-b`.
- Expected results:
  - Each request returns candidates, evidence, citations and trace provenance only from its own
    Workspace's active sets under the requested Embedding Configuration.
  - Cross-Workspace, inactive and alternate-configuration Chunks never appear in the candidate
    list, even when their raw similarity would rank higher.
  - Filtering occurs in the PostgreSQL query rather than after a global top-k result.
- Evidence to capture:
  - Seeded score identities, focused SQL retrieval output, HTTP responses and Question Traces.

### TC-07: Sanitize concurrency, authorization and persistence failures

- Purpose: ensure all new failure paths remain stable public errors and do not expose secrets,
  resource existence or infrastructure internals.
- Steps:
  1. Exercise the authorization failures from TC-01, stale compare-and-swap from TC-03, invalid
     active-pointer operations from TC-04 and controlled persistence failure from TC-05.
  2. Include distinct canaries in raw API keys, provider exception text and database exception
     text.
  3. Search HTTP/CLI responses, application logs, Question Traces and generated artifacts for the
     canaries and internal stack/connection details.
- Expected results:
  - Public responses contain only the expected HTTP status and stable Knora error code.
  - Authorization responses remain existence-opaque and stale concurrency returns HTTP 409
    `DOCUMENT_CONCURRENTLY_UPDATED`.
  - No raw key, provider payload, SQL text, database URL, stack trace or canary appears in client
    output, logs, traces or Evaluation artifacts.
- Evidence to capture:
  - Sanitized error matrix and negative canary-search output.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL
Evaluation records.
