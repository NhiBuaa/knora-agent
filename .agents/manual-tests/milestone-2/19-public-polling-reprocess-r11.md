# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft. Await explicit human approval. Do not lock, implement, or execute this guide.
- Feature/Slice: Milestone 2, GitHub Issue #19
- Authority: Issue #19, `CONTEXT.md`, Architecture Standard, ADRs 0002 and 0005–0013
- Revision: `m2-issue-19-r11`; r1–r10 remain unchanged and unapproved.

## Evidence rules

- Use controlled clocks/providers/barriers, retrieval-store observations, two Workspaces, and reset
  database/ObjectStore state. Do not use sleep, latency, SQL strings, or probabilistic races.
- Capture safe IDs, public bodies/headers, immutable configuration IDs, checksums, equality results,
  and approved spy/projection counts only.

## Locked Test Cases

### TC-01: Upload response contract and immutable request-idempotency bindings

For successful created, replay, and fingerprint-dedup upload responses only, require matched
`ingestion_job_id`, exact `submission_outcome`, and six-state public `status` for that job. Conflict
requires only safe `IDEMPOTENCY_KEY_CONFLICT` behavior and zero extra authoritative DB job/version.

| Probe | Required result |
| --- | --- |
| New upload | `created`, HTTP 202, status `queued`, one job. |
| Non-terminal replay/dedup | Same job, exact replay/dedup outcome, HTTP 202, status equals matched durable status. |
| Terminal replay/dedup | Same job, exact replay/dedup outcome, HTTP 200, status equals durable `succeeded`, `superseded`, or `failed`. |
| Same key, different fingerprint | Conflict, zero extra DB job/version. |
| Filename-only difference with same Workspace/operation/key/source/raw bytes/config IDs | Equal fingerprint, same J1, `idempotency_replay`, no conflict/new job/version. |
| K1 conflict chain | K1+F1 resolves J1; K1+F2 conflicts; K1+F1 again replays J1; no new job/version. |
| K2 fingerprint dedup chain | Fresh K2 first deduplicates eligible J1; immediate K2 repeat is `idempotency_replay` for J1. |
| Fresh reprocess key first reuses equal processing/succeeded work | Immediate repeat resolves the same generation through authority-defined replay behavior; do not invent upload outcome fields. |
| Missing reprocess key or same key/different fingerprint | Safe rejection or conflict; zero generation. |

Same literal key in Workspaces A/B has independent upload bindings/jobs. Same literal key for upload
and reprocess in one Workspace has independent operation bindings. Race upload and reprocess separately
with the same Workspace/operation/key/fingerprint. Require one durable Idempotency Record, one
accepted DB job/generation, both responses resolving to it, no same-fingerprint conflict, and no 500.
Keep F1/F2 race: one winner, loser conflict, zero loser DB work. Upload may retain an unreferenced
staging orphan under existing sweeper semantics; reprocess creates none.

**False pass eliminated.** Conflict handling cannot overwrite F1, dedup cannot omit a durable K2
binding, and same-fingerprint concurrency cannot produce a false conflict or duplicate work.

### TC-02: Exact attempt progression, six states, polling fields, and serving tuple

Run one controlled sequence: accepted queued `0/4`; first claim processing `1/4`; retryable failure
retry-scheduled `1/4` with public field `next_attempt_at` equal to durable scheduled value; advance
only controlled time; second claim processing `2/4`. No double, skipped, or decremented increment.

Separately construct success with count 1..4/max 4 and no failure reason/next attempt; exact retry
exhaustion with failed `4/4`, `failure_reason=retry_exhausted`, separate safe `error_code`, no next
attempt/raw diagnostics; representative non-exhaustion terminal failure with reason in the exact
domain `retry_exhausted | terminal_input | terminal_config | resource_limit`, safe code, no raw
detail/next attempt; and stale CAS with superseded count 1..4/max 4, no failure reason/next attempt.

Every polling response MUST contain body field `poll_after_seconds` or header `Retry-After`, and
MUST include the `no-store` directive in `Cache-Control`. For every non-retry state,
`next_attempt_at` is absent according to the public contract. Serving fixtures assert exact
`(target_document_version_id,current_document_version_id,served_document_version_id,serving_state)`
tuples for committed S0/S1; served may be null; no hybrid transition. Auth is 401/zero lookup,
403 route mismatch/zero lookup, then B-scoped A-job lookup equal to unknown-B 404. Timestamp schema
and successful terminal-result semantics remain blocked; UTC RFC3339 is already authoritative.

**False pass eliminated.** Renamed hint fields, missing cache directive, incorrect progression,
unsafe failure, or hybrid serving tuple cannot pass.

### TC-03: Query-boundary active retrieval and failed J1 → fresh J2

Adversarial top-k data makes inactive B consume a global window if filtering occurs late. Approved
retrieval-store observation proves candidates handed to selection are already restricted to Workspace,
active Set, and embedding config. During J1 processing and after immutable J1 failure, require poll
status `processing` then `failed`, target B/current B/served A/`serving_state=previous`, and A-only
candidate/retrieval IDs. Create fresh J2 for current B with `config_mode=current` and new key; never
same-as-job; J2 activates B and retrieval moves to B.

**False pass eliminated.** State-independent serializer/join bugs, global filtering, hidden inactive
candidates, and terminal J1 reopening cannot pass.

### TC-04: Reprocess authorization, invalid mode, and C1→C2 activation

Use lookup spy: invalid/missing credential → `401 UNAUTHENTICATED`, zero Document-Version lookup;
Workspace-B principal on Workspace-A route → `403 WORKSPACE_ACCESS_DENIED`, zero lookup; valid B
principal on B route with A version → only B-scoped lookup, zero A generation, safe no-existence leak.
Omitted `config_mode` and unsupported value outside `same_as_job | current` each cause safe rejection,
zero generation, and zero worker execution. Do not invent statuses/codes or resolve same-as-job rule.

Sole prior succeeded J1 for V uses C1. Set current config C2 != C1. New current-mode J2 is not J1;
`reprocess_of_job_id=J1`, `attempt_count=0`, `max_attempts=4`, full reset budget, J1 unchanged, exact
C2 snapshot. Hold worker, mutate later selection, release; worker still uses C2, succeeds, activates,
serves current, and retrieves active Set. Historical target is 409. Unavailable source creates none;
ObjectStore spy sees availability check only.

**False pass eliminated.** Pre-auth lookup, invalid-mode execution, cross-Workspace generation,
Version-only deduplication, missing reset/linkage, or late config use cannot pass.

### TC-05: Exact-tuple reuse and stale supersession

Both reuse probes use exact same Version/config tuple while matching work processes and after success.
Hold A, advance current/served, release A. Require immutable reuse, superseded A, counted attempt,
no retry/pointer replacement, and immutable old jobs.

### TC-06: Server-resolved PDF citation and immutable baseline

GenerationProvider spy receives zero DB Chunk IDs and cites request-scoped Evidence Alias only.
Application retains alias-to-Chunk mapping and resolves base Citation Projection plus page/offset/
Chunk provenance from persisted data. Pinned normalized `[start:end]` equals Chunk content/checksum;
page start=end. Preserve all base identity/source/heading/line/checksum/excerpt fields.

Immutable source: commit `c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`, blob
`92fb06d62d3ce926c14f4302ea60c649983c33da`; symbol
`test_question_http_contract_preserves_null_pdf_locators_for_legacy_citations`.

```json
{"evidence_id":"E1","document_id":"document-legacy","document_version_id":"version-legacy","source_key":"support/legacy","source_name":"legacy.md","heading_path":["Legacy"],"start_line":1,"end_line":1,"excerpt":"Legacy citation.","content_checksum":"sha256:legacy","page_start":null,"page_end":null,"start_offset":null,"end_offset":null}
```

### TC-07: Connected tracer bullet, tenant isolation, frozen refusal, no UI/stream

In A, run public upload → retained job → actual worker → same-job success poll → activated tuple →
unique-fact citation to that flow's Version/Chunk. In B, query-boundary observation proves B
Workspace/active Set/config before selection. B no-evidence has zero A IDs, B-only IDs if any,
provider calls 0, generation-not-called trace, and this immutable refusal payload:

```json
{"decision":"REFUSAL","answer":"Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này.","citations":[],"refusal_reason":"INSUFFICIENT_EVIDENCE","trace_id":"<present opaque value>"}
```

Source is the same pinned commit/blob, symbol `test_no_qualified_evidence_returns_deterministic_http_refusal`.
No SSE, token events, progress, streaming, or UI/frontend surface.

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

1. Reprocess audit observation contract.
2. Public lifecycle timestamp projection semantics; UTC RFC3339 is already authoritative.
3. Canonical or explicit prior-generation selector for `config_mode=same_as_job`.
4. Successful terminal-result public polling projection.

## Approval gate

Do not lock, implement, execute acceptance, update Issue #19, or change authority artifacts until
explicit human approval of `m2-issue-19-r11`.
