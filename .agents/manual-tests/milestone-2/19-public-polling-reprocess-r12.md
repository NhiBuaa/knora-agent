# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft. Await explicit human approval. Do not lock, implement, or execute this guide.
- Feature/Slice: Milestone 2, GitHub Issue #19
- Authority: Issue #19, `CONTEXT.md`, Architecture Standard, ADRs 0002 and 0005–0013
- Revision: `m2-issue-19-r12`; r1–r11 remain unchanged and unapproved.

## Evidence rules

- Use controlled clocks/providers/barriers, retrieval-store observations, two Workspaces, and reset
  database/ObjectStore state. Do not use sleep, latency, SQL strings, or probabilistic races.
- Capture safe IDs, public bodies/headers, immutable configuration IDs, checksums, equality results,
  and approved spy/projection counts only.

## Locked Test Cases

### TC-01: Upload contract and immutable request-idempotency bindings

The authority-backed public `status` domain MUST be exactly `queued | processing | retry_scheduled |
succeeded | superseded | failed`. The public schema MUST reject every seventh value, including
cancelled, expired, exhausted, or an internal state. Keep the six valid lifecycle fixtures in TC-02.

For successful created, replay, and dedup uploads only, require matched `ingestion_job_id`, exact
`submission_outcome`, and public `status` for that same job. Conflict requires only safe
`IDEMPOTENCY_KEY_CONFLICT` and zero extra authoritative DB job/version.

| Probe | Required result |
| --- | --- |
| New upload | `created`, HTTP 202, status `queued`, one job. |
| Non-terminal replay/dedup | Same job, exact outcome, HTTP 202, status equals matched durable status. |
| Terminal replay/dedup | Same job, exact outcome, HTTP 200, status equals durable terminal state. |
| Filename-only difference with same Workspace/operation/key/source/raw bytes/config IDs | Equal fingerprint, same J1, replay, no conflict/new work. |
| K1/F1 → K1/F2 → K1/F1 | Create/resolve J1, exact conflict, then replay J1; binding unchanged; no new job/version. |
| K2 dedup → K2 repeat | First deduplicates eligible J1; repeat is idempotency replay for J1. |
| Missing reprocess `Idempotency-Key` | Safe rejection, zero generation, zero worker execution; no invented status/code. |
| Same reprocess key and same request | Same generation through authority-defined replay; zero extra generation. |
| Same reprocess key and different authoritative fingerprint | Exact `IDEMPOTENCY_KEY_CONFLICT`; zero extra generation; original binding unchanged; zero worker execution. |
| Fresh reprocess key that first reuses equal processing/succeeded work | Immediate repeat resolves the same generation through request replay; no upload-only outcome field. |

Same literal key in Workspaces A/B has independent upload bindings/jobs. Same literal key for upload
and reprocess in one Workspace has independent operation bindings. Race upload and reprocess separately
with same Workspace/operation/key/fingerprint. Require one Idempotency Record, one accepted DB job or
generation, both responses resolving to it, no same-fingerprint conflict, and no 500. Preserve F1/F2
race: one winner, one conflict, zero loser DB work. Upload may leave an unreferenced staging orphan
under existing sweeper semantics; reprocess creates none.

**False pass eliminated.** Seventh public status, overwritten binding, missing dedup binding,
ambiguous missing-key/conflict behavior, scope leakage, or concurrency duplicate cannot pass.

### TC-02: Exact progression, six states, polling fields, serving tuple, and scoped 404

Run controlled progression: queued `0/4`; first claim processing `1/4`; retryable failure
retry-scheduled `1/4` with literal public `next_attempt_at` equal to durable value; advance controlled
time only; second claim processing `2/4`. Every non-retry state has no `next_attempt_at`.

Separately construct succeeded with count 1..4/max 4 and no failure reason/next attempt; exhausted
failed `4/4` with exact `retry_exhausted`, separate safe error, and no diagnostics/next attempt;
representative non-exhaustion failed with reason in exact closed four-value domain and no leaked raw
detail; and superseded with count 1..4/max 4, no failure reason/next attempt.

Every poll MUST have body `poll_after_seconds` or header `Retry-After`, plus `Cache-Control: no-store`.
For unavailable/current/previous, assert exact HTTP tuple `(target_document_version_id,
current_document_version_id,served_document_version_id,serving_state)` equals committed S0 or S1.
Served ID may be null. A controlled atomic transition returns no hybrid tuple.

Job polling authentication and lookup oracles:

1. Invalid or missing credential returns HTTP 401 with `UNAUTHENTICATED`; lookup count is zero.
2. Valid principal on another Workspace route returns HTTP 403 with `WORKSPACE_ACCESS_DENIED`;
   lookup count is zero.
3. Authorized unknown Workspace-B job returns HTTP 404 and `INGESTION_JOB_NOT_FOUND`.
4. Authorized B-scoped lookup with A's job ID performs B-scoped lookup and returns the same HTTP 404,
   `INGESTION_JOB_NOT_FOUND`, and indistinguishable safe body as the unknown B job.

UTC RFC3339 is authoritative. Timestamp projection semantics and successful terminal-result schema
remain blocked. Do not invent either.

**False pass eliminated.** Seventh status, wrong auth code, generic 404, lookup leakage, incorrect
attempt progression, renamed retry fields, or hybrid tuple cannot pass.

### TC-03: Query-boundary active retrieval and joined previous-serving lifecycle

Adversarial top-k data makes inactive B consume a global window if filtering occurs late. Approved
retrieval-store observation proves candidates handed to selection are already restricted to Workspace,
active Set, and embedding config. While J1 is held, one poll MUST contain status `processing`, target
B, current B, served A, and `previous`. After immutable J1 failure, one poll MUST contain status
`failed` with the same B/B/A/previous tuple. Both retrieval observations contain A-only IDs. Fresh J2
uses `config_mode=current` plus a new key; never same-as-job; J2 activates B and retrieval moves to B.

**False pass eliminated.** State-dependent serializer joins, global filtering, hidden inactive IDs,
or terminal J1 reopening cannot pass.

### TC-04: Reprocess auth, input domain, historical rejection, and C1→C2 activation

Use a Document-Version lookup spy. Invalid/missing credential → exact 401 `UNAUTHENTICATED`, zero
lookup. B principal on A route → exact 403 `WORKSPACE_ACCESS_DENIED`, zero lookup. B principal on B
route with A's Version ID → B-scoped lookup only, no A generation, safe no-existence leak. Missing
or unsupported `config_mode` → safe rejection, zero generation, zero worker execution.

For a historical/non-current Version, require HTTP 409 and exact `DOCUMENT_VERSION_NOT_CURRENT`.
Require zero new job/generation, zero enqueue/worker execution, unchanged current and served/active
pointers, and unchanged existing job/version projections. Do not assert audit behavior.

Sole prior succeeded J1 for V uses C1. Set current config C2 != C1. New current-mode J2 links J1,
has `attempt_count=0`, `max_attempts=4`, full reset, leaves J1 immutable, and snapshots C2. Hold worker,
mutate later selection, release; worker uses C2, succeeds, activates, serves current, retrieves active
Set. Unavailable source creates none; ObjectStore spy records availability check only. Do not resolve
same-as-job selection.

**False pass eliminated.** Enqueue-before-history-check, pointer mutation on rejection, pre-auth
lookup, invalid-mode work, missing reset/linkage, or late config resolution cannot pass.

### TC-05: Exact-tuple reuse and stale supersession

Both reuse probes use exact same Version/config tuple while matching work processes and after success.
Hold A, advance current/served, release A. Require immutable reuse, superseded A, counted attempt,
no retry/pointer replacement, and immutable old jobs.

### TC-06: Server-resolved PDF citation, independent page index, and frozen baseline

GenerationProvider spy receives zero DB Chunk IDs and cites request-scoped Evidence Alias only.
Application retains alias-to-Chunk mapping and resolves the complete base Citation Projection plus
PDF provenance from persisted data. The excerpt is server-resolved from persisted evidence and is at
most 500 characters.

Use a deterministic multi-page PDF whose cited fact is independently known to be on physical page
P, where P > 1. Establish from the fixture/PDF—not the Chunk row—that the first physical page is page
1 and the fact is on P. Require `page_start=P`, `page_end=P`, and normalized `[start:end]` from that
same page P. Start is inclusive; end is exclusive. The substring equals persisted Chunk content/
checksum. Preserve exact Chunk identity/checksum and server-resolution assertions.

Immutable source: commit `c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`, blob
`92fb06d62d3ce926c14f4302ea60c649983c33da`; symbol
`test_question_http_contract_preserves_null_pdf_locators_for_legacy_citations`.

```json
{"evidence_id":"E1","document_id":"document-legacy","document_version_id":"version-legacy","source_key":"support/legacy","source_name":"legacy.md","heading_path":["Legacy"],"start_line":1,"end_line":1,"excerpt":"Legacy citation.","content_checksum":"sha256:legacy","page_start":null,"page_end":null,"start_offset":null,"end_offset":null}
```

**False pass eliminated.** Internally consistent zero-based page indexing, oversized/provider-derived
excerpt, provider metadata trust, or moved legacy baseline cannot pass.

### TC-07: Connected tracer bullet, tenant isolation, frozen refusal, and no UI/stream

In A, run public upload → retained job → actual worker → same-job success poll → activated tuple →
unique-fact citation to that flow's Version/Chunk. In B, query-boundary observation proves B
Workspace/active Set/config before selection. B no-evidence has zero A IDs, B-only IDs if any,
provider calls zero, generation-not-called trace, and this immutable refusal payload:

```json
{"decision":"REFUSAL","answer":"Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này.","citations":[],"refusal_reason":"INSUFFICIENT_EVIDENCE","trace_id":"<present opaque value>"}
```

Source is the same pinned commit/blob, symbol `test_no_qualified_evidence_returns_deterministic_http_refusal`.
No SSE, token events, progress, streaming, or UI/frontend surface.

## Acceptance-criteria traceability matrix

| Issue #19 criterion | Tests | Coverage |
| --- | --- | --- |
| Upload response: status, job ID, outcome, public state | TC-01 | PASS |
| Six public states and terminal metadata | TC-01, TC-02 | PASS |
| Poll fields, timestamps, hints, no-store | TC-02 | BLOCKED |
| One-snapshot pointers and serving states | TC-02 | PASS |
| Auth-before-lookup and scoped job 404 | TC-02, TC-04 | PASS |
| Reprocess auth, audit, key, historical conflict | TC-01, TC-04 | BLOCKED |
| `same_as_job` and `current` snapshots | TC-04 | BLOCKED |
| Fresh generation and equal-work reuse | TC-01, TC-04, TC-05 | PASS |
| PDF provenance and backward compatibility | TC-06 | PASS |
| Active-only cited answers and refusal | TC-03, TC-07 | PASS |
| E2E, serving, reprocess, supersession, tenant isolation | TC-03–TC-05, TC-07 | PASS |
| No percentage progress, tokens, SSE, or UI | TC-07 | PASS |

## UPSTREAM AUTHORITY BLOCKERS

1. Reprocess audit observation contract.
2. Public lifecycle timestamp projection semantics; UTC RFC3339 is already authoritative.
3. Canonical or explicit prior-generation selector for `config_mode=same_as_job`.
4. Successful terminal-result public polling projection.

## Approval gate

Do not lock, implement, execute acceptance, update Issue #19, or change authority artifacts until
explicit human approval of `m2-issue-19-r12`.
