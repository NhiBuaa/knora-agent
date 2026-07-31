# Manual Test Guide: Deterministic Cited Retrieval

## Metadata

- Status: Approved and locked
- Feature: Milestone 1 — Cited RAG
- Slice: GitHub issue #3 — Answer questions with deterministic cited retrieval
- Authoritative specification: `docs/specs/milestone-1-cited-rag.md`
- Guide revision: `m1-deterministic-cited-retrieval-r1`
- Approved by: NhiBuaa
- Approved at: 2026-07-31T19:24:11+07:00

## Prerequisites

- Environment: local checkout with Docker PostgreSQL/pgvector healthy, migrated schema and the
  FastAPI application running in deterministic-local provider mode.
- Data and state: dedicated Workspaces `acceptance-question-a` and `acceptance-question-b`; ingest
  a curated Markdown corpus with active and historical Document Versions, adjacent overlapping
  Chunks and enough eligible Chunks to exercise count and token limits. Reset these Workspaces
  before a new Evaluation run without rewriting prior Evaluation history.
- Credentials and permissions: enabled test credentials for both acceptance Workspaces, stored as
  hash-only runtime records. Raw keys remain only in the test client/environment.
- Configuration: Milestone 1 Embedding Configuration (`text-embedding-3-small`, 1536 dimensions,
  cosine distance) and Retrieval Configuration (`candidate_k=8`, `min_similarity=0.65`,
  `max_evidence_chunks=5`, `max_evidence_tokens=3000`) are pinned for the run.
- Provider observability: the deterministic Generation Provider exposes a focused test seam for
  invocation count and controlled valid answer, valid refusal and invalid structured outputs.

## Locked Test Cases

### TC-01: Retrieve only active evidence from the authorized Workspace and configuration

- Purpose: prove tenant, Active Embedding Set and Embedding Configuration predicates are applied
  inside exact PostgreSQL retrieval rather than filtering a global result afterward.
- Steps:
  1. Seed similar Chunks in both acceptance Workspaces, plus an inactive historical Embedding Set
     and a completed set using a non-requested Embedding Configuration in
     `acceptance-question-a`.
  2. Ask an answerable question using the credential for `acceptance-question-a`.
  3. Run the focused retrieval-adapter verification for the same query vector.
- Expected results:
  - The HTTP response is derived only from active Chunks in `acceptance-question-a` using the
    pinned Embedding Configuration.
  - No Chunk from `acceptance-question-b`, an inactive historical set or another Embedding
    Configuration appears in candidates, evidence, citations or the Question Trace.
  - A valid key for one Workspace used with another Workspace returns HTTP 403
    `WORKSPACE_ACCESS_DENIED` before retrieval.
- Evidence to capture:
  - HTTP responses and focused PostgreSQL retrieval output showing the applied scope.

### TC-02: Apply exact cosine scoring, threshold and deterministic candidate ordering

- Purpose: verify the locked retrieval baseline and repeatability when similarities tie.
- Steps:
  1. Seed candidates above, at and below similarity `0.65`, including equal-similarity candidates
     with different Document IDs, Chunk ordinals and Chunk IDs.
  2. Execute the same Question Request twice and inspect the focused candidate output.
- Expected results:
  - Candidate search is exact pgvector cosine search with
    `similarity = 1 - cosine_distance` and at most eight candidates.
  - The threshold is applied to similarity: the boundary candidate qualifies and the below-boundary
    candidate is marked `BELOW_THRESHOLD`.
  - Both runs order candidates by
    `similarity DESC → document_id ASC → chunk_ordinal ASC → chunk_id ASC`.
  - The Question Trace records both cosine distance and derived similarity for every candidate.
- Evidence to capture:
  - Focused adapter output with scores, ordering and repeated-run comparison.

### TC-03: Enforce evidence overlap, chunk-count and token-budget bounds

- Purpose: prove every retrieval candidate receives one decision and the Evidence Set remains
  bounded without merging Chunks.
- Steps:
  1. Run a focused scenario containing strongly overlapping adjacent Chunks from one Chunk Set,
     more than five otherwise eligible Chunks and a candidate that would exceed 3000 evidence
     tokens.
  2. Inspect the selected Evidence Set and candidate decisions.
- Expected results:
  - At most five Chunks and at most 3000 tokens are selected.
  - Strongly overlapping adjacent Chunks are excluded as `REDUNDANT_OVERLAP`; Chunks are not
    merged.
  - A qualifying candidate that exceeds the remaining token budget is marked
    `TOKEN_BUDGET_EXCEEDED`.
  - Every candidate has exactly one of `SELECTED`, `BELOW_THRESHOLD`, `REDUNDANT_OVERLAP` or
    `TOKEN_BUDGET_EXCEEDED` in deterministic scan order.
- Evidence to capture:
  - Focused evidence-selection output with candidate decisions and final count/token totals.

### TC-04: Return a validated deterministic answer with ordered Citation Projections

- Purpose: prove the complete answer path uses request-scoped Evidence Aliases and resolves all
  citation metadata from persisted server state.
- Steps:
  1. Ask a question supported by at least two selected Chunks while the deterministic Generation
     Provider returns a valid structured answer whose first marker order is `[[E2]]`, then
     `[[E1]]`.
  2. Compare the response with the selected Evidence Set and persisted Chunk metadata.
- Expected results:
  - HTTP 200 returns `decision=ANSWER`, a non-empty answer with inline markers,
    `refusal_reason=null`, an opaque non-empty `trace_id` and no partial/token events.
  - The provider receives opaque request-scoped aliases and never receives database Chunk IDs.
  - `citations` contains `E2` then `E1`, each exactly once, matching first marker appearance and
    only Chunks in the Evidence Set.
  - Every Citation Projection pins Document Version, source key/name, heading path, line range and
    content checksum; its excerpt is server-resolved and no longer than 500 characters.
  - `source_name` is display-only and neither it nor `source_key` exposes an internal filesystem
    path.
- Evidence to capture:
  - Complete HTTP response, provider request capture and Citation Projection comparison.

### TC-05: Refuse deterministically when retrieval has no qualified evidence

- Purpose: ensure insufficient retrieval cannot fabricate an answer or incur generation work.
- Steps:
  1. Ask an out-of-corpus question whose candidates are empty or all below threshold.
  2. Inspect the Generation Provider invocation count and persisted trace.
- Expected results:
  - HTTP 200 returns `decision=REFUSAL`, the application-owned refusal message, empty citations,
    `refusal_reason=INSUFFICIENT_EVIDENCE` and an opaque `trace_id`.
  - The Generation Provider invocation count remains zero.
  - Candidate decisions and refusal state are persisted before the response.
- Evidence to capture:
  - Complete HTTP response, zero-call provider observation and Question Trace verification.

### TC-06: Accept a valid structured provider refusal when evidence exists

- Purpose: distinguish a provider's valid insufficient-evidence decision from the deterministic
  no-candidate refusal path.
- Steps:
  1. Supply qualified evidence and configure the deterministic Generation Provider to return
     `decision=REFUSAL`, `answer=null`, empty cited IDs and
     `refusal_reason=INSUFFICIENT_EVIDENCE`.
  2. Submit the Question Request and inspect the trace.
- Expected results:
  - HTTP 200 returns the same normalized refusal contract as TC-05 with no citations.
  - The application supplies the user-facing message and records that generation occurred.
  - No provider-supplied citation metadata is projected.
- Evidence to capture:
  - HTTP response, provider invocation observation and generation-status trace fields.

### TC-07: Reject malformed or untrusted generation output without repair

- Purpose: enforce structured schema, marker membership, uniqueness and ordering before any answer
  or citation reaches the client.
- Steps:
  1. With qualified evidence available, run controlled provider outputs covering an unknown alias,
     duplicate cited ID, marker/list ordering mismatch, missing marker, and an internally
     inconsistent ANSWER or REFUSAL shape.
  2. Observe the HTTP result and provider invocation count for each scenario.
- Expected results:
  - Every scenario returns HTTP 502 with `GENERATION_OUTPUT_INVALID`; none is converted to a
    Refusal or exposed as a partial answer.
  - Milestone 1 performs no repair retry, so each scenario invokes generation exactly once.
  - No citation based on provider-supplied metadata is returned.
  - The invalid validation outcome and parsed marker observations are persisted for debugging.
- Evidence to capture:
  - HTTP errors, one-call provider observations and focused generation-validation/trace output.

### TC-08: Persist a complete Question Trace before every successful response

- Purpose: prove response delivery waits for trace persistence and captures the required retrieval,
  generation and citation-validation provenance without chain-of-thought.
- Steps:
  1. Execute one valid answer, one no-qualified-evidence refusal and one valid provider refusal.
  2. Resolve each returned `trace_id` through the focused workspace-authorized trace-store seam.
  3. Run a controlled trace-store failure during an otherwise valid answer.
- Expected results:
  - Before each successful HTTP response, the trace contains the Question, active Embedding Set,
    Chunk Set, Embedding Configuration, retrieved Chunk IDs, candidate decisions, alias mapping,
    parsed markers, validation outcome, provider/model, prompt version, usage, latency, finish
    reason and provider request ID when present.
  - No trace contains requested or persisted chain-of-thought, raw API keys or secrets.
  - `trace_id` is opaque and does not itself grant cross-Workspace access.
  - A trace-store failure prevents the normal answer response; no untraced or partially validated
    answer is returned.
- Evidence to capture:
  - HTTP responses, persisted trace projections and controlled trace-store failure output.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL
Evaluation records.
