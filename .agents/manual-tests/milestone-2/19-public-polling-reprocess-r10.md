# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft. Await explicit human approval. Do not lock, implement, or execute this guide.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #19 — Public polling, reprocess, and PDF citation integration
- Authority: Issue #19; `CONTEXT.md`; Architecture Standard; ADRs 0002 and 0005–0013
- Guide revision: `m2-issue-19-r10`
- Replaces: `m2-issue-19-r9`; r1–r9 remain unchanged and unapproved.

## Evidence rules

- Use controlled clocks, providers, barriers, retrieval-store observations, two Workspaces, and
  reset database/ObjectStore state.
- Do not use sleep, timing luck, SQL strings, latency, or probabilistic races as test oracles.
- Capture safe IDs, public bodies and headers, immutable configuration IDs, checksums, equality
  results, and approved spy or projection counts only.

## Locked Test Cases

### TC-01: Successful upload contract and request idempotency

Apply the accepted-success response schema only to created, idempotency-replay, and fingerprint-
deduplication responses. Each successful response MUST contain `ingestion_job_id`, exact
`submission_outcome`, and public `status`. The ID and status MUST describe the same matched durable
job. For `IDEMPOTENCY_KEY_CONFLICT`, require safe conflict behavior and zero extra authoritative DB
job or Document Version. Do not require accepted-success fields in the conflict body.

| Setup | Required result |
| --- | --- |
| New upload | One job; `submission_outcome=created`; HTTP `202`; returned `status=queued`. |
| Same key and request while matched job is non-terminal | Same job; `idempotency_replay`; HTTP `202`; returned status equals the matched job's current durable public status. |
| Different key and eligible equal fingerprint while matched job is non-terminal | Same job; `deduplicated`; HTTP `202`; returned status equals the matched job's current durable public status. |
| Same key and request after matched job is terminal | Same job; `idempotency_replay`; HTTP `200`; returned status equals the durable terminal status in `succeeded | superseded | failed`. |
| Different key and eligible equal fingerprint after matched job is terminal | Same job; `deduplicated`; HTTP `200`; returned status equals the durable terminal status in `succeeded | superseded | failed`. |
| Same key with a different authoritative fingerprint | `IDEMPOTENCY_KEY_CONFLICT`; zero extra authoritative DB job or Document Version. |
| Filename-only change with the same Workspace, operation, key, source, bytes, and configs | Equal fingerprint; same job; `idempotency_replay`; no conflict or new work. |
| Missing reprocess key | Safe rejection; zero generation. |
| Same reprocess key and same authoritative request | Same generation; zero extra generation. |
| Same reprocess key and different authoritative fingerprint | Conflict; zero extra generation. |
| New reprocess key with exact same Version/config tuple while matching work is processing | Reuse the matching generation; zero extra generation. |
| New reprocess key with exact same Version/config tuple after matching work succeeded | Reuse the matching generation; zero extra generation. |

Use the same literal key in Workspaces A and B for independent upload bindings and jobs. Use the same
literal key for upload and reprocess in one Workspace for independent operation-scoped bindings.

For upload and reprocess separately, race two requests with the same Workspace, operation, key, and
fingerprint through an approved barrier. Require one durable Idempotency Record and one accepted DB
job or generation. Both responses MUST resolve to that same logical work. Neither response may
return conflict. No 500 or uniqueness detail may leak. For upload before worker progress, one response
may be `created` and the other `idempotency_replay`; both return the same non-terminal job. Reprocess
uses only authority-defined same-generation replay fields. Preserve the F1/F2 race: one winner, one
conflict, and zero loser authoritative DB work. An upload loser staging object may remain unreferenced
under existing orphan/sweeper semantics. Reprocess creates no source staging object.

**False pass eliminated.** Arbitrary six-state upload status, ID/status mismatch, filename-sensitive
identity, scope leakage, same-fingerprint conflict, or duplicate accepted DB work cannot pass.

### TC-02: Exact attempt progression, six states, polling fields, and serving tuple

Use one controlled database/clock sequence on a fresh job:

| Event | Required public and durable projection |
| --- | --- |
| Accepted before claim | `queued`; `attempt_count=0`; `max_attempts=4`; `next_attempt_at` absent. |
| First claim | `processing`; `attempt_count=1`; `max_attempts=4`; `next_attempt_at` absent. |
| First retryable failure | `retry_scheduled`; `attempt_count=1`; `max_attempts=4`; public `next_attempt_at` present and equal to the durable scheduled value. |
| Advance only controlled time until due; second claim | `processing`; `attempt_count=2`; `max_attempts=4`; `next_attempt_at` absent. |

Construct the remaining states separately. `succeeded` has count 1..4, max 4, no failure reason, and
no `next_attempt_at`. Retry exhaustion has `failed`, count=max=4, exact `retry_exhausted`, separate
safe error code, no `next_attempt_at`, and no raw diagnostics. An approved malformed, unsupported,
or textless fixture gives a deterministic non-exhaustion `failed` response. Its reason MUST belong
to `retry_exhausted | terminal_input | terminal_config | resource_limit`. It has a separate safe
error code, no raw details, and no `next_attempt_at`. Do not require which non-exhaustion reason
applies. TC-05 stale CAS gives `superseded`, count 1..4, max 4, no failure reason, and no
`next_attempt_at`.

Every polling response MUST contain either body field `poll_after_seconds` or header `Retry-After`.
Every polling response MUST include the `no-store` directive in `Cache-Control`. Do not accept an
arbitrary `X-Poll-*` header or differently named retry field as a substitute.

For unavailable, current, and previous serving fixtures, assert the exact HTTP tuple
`(target_document_version_id, current_document_version_id, served_document_version_id,
serving_state)`. The tuple MUST equal all committed S0 or all committed S1. The served ID may be
null. A controlled atomic transition MUST NOT return a hybrid tuple.

For job polling, require 401 and zero lookup for invalid credentials; 403 and zero lookup for a
Workspace-route mismatch; then an authorized Workspace-B-scoped lookup of A's job with the same
404 body as an unknown Workspace-B job.

UTC RFC3339 is authoritative. Public lifecycle timestamp schema/semantics and successful terminal-
result projection remain blocked below. Do not invent either contract.

**False pass eliminated.** Renamed retry fields, missing poll hints, weak cache control, incorrect
attempt progression, unsafe terminal failure, hybrid serving tuples, or pre-authorization lookup
cannot pass.

### TC-03: Query-boundary active retrieval, immutable J1 failure, and fresh J2

Use adversarial top-k data so inactive B candidates consume a global window if filtering occurs
late. The approved retrieval-store observation MUST show that database candidates passed to
application selection are already constrained by Workspace, active Embedding Set, and Embedding
Configuration. During J1 processing and after immutable J1 failure, poll B/B/A/previous and capture
A-only candidate and retrieval IDs. Create fresh J2 for B with `config_mode=current` and a new key.
Do not use `same_as_job`. J2 activates B and retrieval moves to B.

### TC-04: Reprocess authorization, input domain, and C1→C2 current-mode activation

Use an approved Document-Version lookup spy.

1. Send an invalid or missing credential. Require `401 UNAUTHENTICATED` and zero resource lookup.
2. Send a valid Workspace-B principal to a Workspace-A route. Require
   `403 WORKSPACE_ACCESS_DENIED` and zero resource lookup.
3. Send a valid B principal to a B route with A's Document Version ID. Require only B-scoped lookup,
   zero generation for A, and safe no-existence-leak behavior. Do not require the job-specific
   `INGESTION_JOB_NOT_FOUND` code.
4. Omit `config_mode`. Require safe rejection, zero generation, and zero worker execution.
5. Send an unsupported `config_mode` outside `same_as_job | current`. Require safe rejection, zero
   generation, and zero worker execution. Do not invent an exact public status or error code.

For the successful branch, the sole prior succeeded J1 for V uses C1. Set the current immutable
configuration to C2 where C2 != C1. A new `config_mode=current` request creates J2. J2 links to J1,
has `attempt_count=0`, `max_attempts=4`, full reset budget, leaves J1 unchanged, and snapshots C2.
Hold the worker, change the later current selection, then release it. The worker still uses C2,
succeeds, activates, serves current, and retrieves the active Set. A historical target returns 409.
An unavailable source creates no generation; the ObjectStore spy records only the availability check
before worker execution. Do not test unresolved `same_as_job` selection.

**False pass eliminated.** Pre-authorization lookup, invalid config acceptance, worker execution on
invalid input, Version-only deduplication, missing reset/linkage, or late config resolution cannot
pass.

### TC-05: Exact-tuple reuse and stale supersession

Both positive reuse probes use the exact same Document Version and immutable configuration tuple.
Run one while matching work processes and one after it succeeds. Hold A before finalization, advance
current/served state, then release A. Require immutable reuse, terminal `superseded`, counted started
attempt, no retry or pointer replacement, and immutable old jobs.

### TC-06: Server-resolved PDF citation and immutable legacy baseline

The Generation Provider spy receives zero DB Chunk IDs and cites request-scoped Evidence Aliases only.
The application retains alias-to-Chunk mapping and resolves the base Citation Projection plus PDF
page/offset/Chunk provenance from persisted data. The pinned normalized `[start:end]` equals Chunk
content/checksum and page start equals page end.

Immutable source: commit `c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`, blob
`92fb06d62d3ce926c14f4302ea60c649983c33da`, file
`backend/test/adapters/http/test_questions.py`, symbol
`test_question_http_contract_preserves_null_pdf_locators_for_legacy_citations`.

```json
{"evidence_id":"E1","document_id":"document-legacy","document_version_id":"version-legacy","source_key":"support/legacy","source_name":"legacy.md","heading_path":["Legacy"],"start_line":1,"end_line":1,"excerpt":"Legacy citation.","content_checksum":"sha256:legacy","page_start":null,"page_end":null,"start_offset":null,"end_offset":null}
```

### TC-07: Connected tracer bullet, tenant isolation, immutable refusal, and no UI/stream

In A, run public upload → retained job → actual worker → same-job success poll → activated pointer
tuple → unique-fact citation to that flow's Version/Chunk. In B, the adversarial retrieval-store
observation proves B Workspace/active Set/config filtering before selection. B's no-evidence request
has zero A IDs, B-only IDs if any, provider calls 0, and trace generation-not-called.

Immutable refusal source: the same commit/blob/file above, symbol
`test_no_qualified_evidence_returns_deterministic_http_refusal`.

```json
{"decision":"REFUSAL","answer":"Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này.","citations":[],"refusal_reason":"INSUFFICIENT_EVIDENCE","trace_id":"<present opaque value>"}
```

No SSE, token events, percentage progress, streaming response, or UI/frontend surface may appear.

## Acceptance-criteria traceability matrix

| Issue #19 criterion | Tests | Coverage |
| --- | --- | --- |
| Upload response: status, job ID, outcome, public state | TC-01 | PASS |
| Six public states and terminal metadata | TC-02 | PASS |
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

1. **Reprocess audit.** Authority does not define observable correlation semantics, a safe
   observation seam, or the audit/enqueue relationship or atomicity.
2. **Public lifecycle timestamps.** UTC RFC3339 is authoritative. Authority does not define public
   schema/names, lifecycle and retry semantics, nullability, or durable-source mapping.
3. **`same_as_job` selection.** Authority does not define the canonical prior generation or an
   explicit selector when multiple prior generations exist.
4. **Successful terminal result.** Authority does not define the public field, shape, contents, or
   succeeded-versus-superseded projection semantics.

## Approval gate

Do not lock, implement, execute acceptance, update Issue #19, or change authority artifacts until
explicit human approval of `m2-issue-19-r10`.
