# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft. Await explicit human approval. Do not lock, implement, or execute this guide.
- Feature/Slice: Milestone 2, GitHub Issue #19
- Authority: Issue #19, `CONTEXT.md`, Architecture Standard, ADRs 0002 and 0005–0013
- Revision: `m2-issue-19-r13`; r1–r12 remain unchanged and unapproved.

## Evidence rules

- Use controlled clocks/providers/barriers, retrieval-store observations, two Workspaces, and reset
  database/ObjectStore state. Do not use sleep, latency, SQL strings, or probabilistic races.
- Capture safe IDs, public bodies/headers, immutable configuration IDs, checksums, equality results,
  and approved spy/projection counts only.

## Locked Test Cases

### TC-01: Upload contract and immutable request-idempotency bindings

The public `status` domain MUST be exactly `queued | processing | retry_scheduled | succeeded |
superseded | failed`. The public schema MUST reject every seventh or internal value.

For successful created, replay, and dedup uploads only, require matched `ingestion_job_id`, exact
`submission_outcome`, and public `status` for that same job. Execute all four branches independently:

| Mandatory branch | Required result |
| --- | --- |
| Same scoped key/request while matched job is non-terminal | `idempotency_replay`; HTTP 202; same job; status equals matched non-terminal durable status. |
| Different new key with eligible equal fingerprint while matched job is non-terminal | `deduplicated`; HTTP 202; same job; status equals matched durable status. |
| Same scoped key/request after matched job is terminal | `idempotency_replay`; HTTP 200; same job; exact durable terminal status. |
| Different new key with eligible equal fingerprint after matched job is terminal | `deduplicated`; HTTP 200; same job; exact durable terminal status. |

A new upload separately requires `created`, HTTP 202, status `queued`, and one job. Conflict requires
only safe `IDEMPOTENCY_KEY_CONFLICT` and zero extra authoritative DB job/version.

Preserve these probes: filename-only equality; K1/F1 → conflict F2 → replay F1 with unchanged binding;
K2 fingerprint dedup → immediate K2 idempotency replay; Workspace and operation key isolation; and
same-fingerprint plus F1/F2 upload/reprocess races. Both same-fingerprint responses resolve the same
logical work and neither conflicts. Upload may leave an unreferenced staging orphan under existing
sweeper semantics; reprocess creates none.

For reprocess, execute separate branches:

- Missing `Idempotency-Key`: safe rejection, zero generation, zero worker execution.
- Same key/request: same generation through authority-defined replay.
- Same key/different fingerprint: exact `IDEMPOTENCY_KEY_CONFLICT`, zero extra generation, unchanged
  original binding, and zero worker execution.
- Fresh key that initially reuses equal processing/succeeded work: immediate repeat resolves the same
  generation through request replay. Do not invent upload outcome fields.

**False pass eliminated.** Compressed replay/dedup coverage, overwritten binding, missing dedup binding,
seventh state, scope leakage, or concurrency duplicate cannot pass.

### TC-02: Exact progression, six states, polling fields, serving tuple, and scoped 404

Run controlled progression: queued `0/4`; first claim processing `1/4`; retryable failure
retry-scheduled `1/4` with literal `next_attempt_at` equal to durable value; advance controlled time;
second claim processing `2/4`. Every non-retry state has no `next_attempt_at`.

Separately construct:

- `succeeded`, count 1..4/max 4, no failure reason/next attempt;
- exhausted `failed` `4/4`, exact `retry_exhausted`, separate safe `error_code`, no diagnostics/next attempt;
- representative non-exhaustion `failed`, reason within exactly `retry_exhausted | terminal_input |
  terminal_config | resource_limit`, a separate safe `error_code`, no next attempt, and no raw
  exception/provider/SQL/storage/object/path/credential detail; and
- `superseded`, count 1..4/max 4, no failure reason/next attempt.

Do not require the exact non-exhaustion error-code value or a complete error-code taxonomy.

Every poll has body `poll_after_seconds` or header `Retry-After` and `Cache-Control: no-store`.
Unavailable/current/previous fixtures assert exact `(target_document_version_id,
current_document_version_id,served_document_version_id,serving_state)` committed S0/S1 tuple;
served may be null; no hybrid transition.

Job polling auth/lookup:

1. Invalid/missing credential → HTTP 401 `UNAUTHENTICATED`, zero lookup.
2. Principal on another Workspace route → HTTP 403 `WORKSPACE_ACCESS_DENIED`, zero lookup.
3. Unknown authorized B job → HTTP 404 `INGESTION_JOB_NOT_FOUND`.
4. B-scoped lookup with A job ID → same 404/code/indistinguishable body, with B-scoped lookup spy.

UTC RFC3339 is authoritative. Timestamp semantics and successful terminal-result schema stay blocked.

**False pass eliminated.** Missing safe non-exhaustion code, weak auth/error contract, wrong progression,
renamed retry fields, or hybrid tuple cannot pass.

### TC-03: Query-boundary active retrieval and joined previous-serving lifecycle

Adversarial top-k data makes inactive B consume a global window if filtering occurs late. Retrieval-
store observation proves candidates passed to selection are already scoped by Workspace, active Set,
and embedding config. While J1 is held, poll status `processing`, target B/current B/served A/
`previous`. After immutable J1 failure, poll status `failed` with the same B/B/A/previous tuple.
Both retrieval observations contain A-only IDs. Fresh J2 uses `config_mode=current` and a new key,
never same-as-job; J2 activates B and retrieval moves to B.

### TC-04: Reprocess auth, invalid mode, historical rejection, and C1→C2 activation

Use a Document-Version lookup spy. Invalid credential → exact 401/zero lookup. B principal on A route
→ exact 403/zero lookup. B principal on B route with A Version ID → B-scoped lookup only, no A
generation, safe no-existence leak. Missing/unsupported `config_mode` → safe rejection, zero generation,
zero worker execution.

Historical/non-current Version → HTTP 409, exact `DOCUMENT_VERSION_NOT_CURRENT`, zero new job/
generation, zero enqueue/worker execution, unchanged current and served/active pointers, and unchanged
existing job/version projections. Do not assert audit behavior.

Sole prior succeeded J1 for V uses C1. Set C2 != C1. New current-mode J2 links J1, has count 0/max 4,
full reset, immutable J1, exact C2 snapshot. Hold worker, mutate later selection, release; worker uses
C2, succeeds, activates, serves current, retrieves active Set. Unavailable source creates none;
ObjectStore spy records availability check only. Do not resolve same-as-job selection.

### TC-05: Exact-tuple reuse and manual-reprocess stale supersession

Both positive reuse probes use exact same Version/config tuple: one while matching work processes and
one after it succeeds.

For supersession, make V current. Create manual `config_mode=current` reprocess generation A for V
with a new scoped key. Hold A before finalization/activation. Accept and complete newer source V2 so
V2 becomes current with the appropriate serving state. Release A. Require A terminal
`status=superseded`; its started attempt stays counted; no retry is scheduled or consumed; A does not
replace current or served pointers; and old job/generation stays immutable.

**False pass eliminated.** Generic stale ingestion cannot substitute for superseded manual reprocess.

### TC-06: Server-resolved PDF citation, independent page index, and frozen baseline

GenerationProvider spy receives zero DB Chunk IDs and cites Evidence Aliases only. Application retains
alias-to-Chunk mapping and resolves the complete base Citation Projection plus PDF provenance from
persisted data. Excerpt is server-resolved and at most 500 characters.

Use deterministic multi-page PDF with fact independently known on physical page P > 1. From the PDF
fixture, establish first physical page=1 and fact page=P. Require `page_start=P`, `page_end=P`, and
normalized inclusive/exclusive `[start:end]` from page P. Substring equals persisted Chunk content/
checksum. Do not derive P solely from the Chunk row.

Immutable source: commit `c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`, blob
`92fb06d62d3ce926c14f4302ea60c649983c33da`; symbol
`test_question_http_contract_preserves_null_pdf_locators_for_legacy_citations`.

```json
{"evidence_id":"E1","document_id":"document-legacy","document_version_id":"version-legacy","source_key":"support/legacy","source_name":"legacy.md","heading_path":["Legacy"],"start_line":1,"end_line":1,"excerpt":"Legacy citation.","content_checksum":"sha256:legacy","page_start":null,"page_end":null,"start_offset":null,"end_offset":null}
```

### TC-07: Connected tracer bullet, tenant isolation, frozen refusal, and no UI/stream

In A, run public upload → retained job → actual worker → same-job success poll → activated tuple →
unique-fact citation to that flow's Version/Chunk. In B, query-boundary observation proves B Workspace/
active Set/config before selection. B no-evidence has zero A IDs, B-only IDs if any, provider calls
zero, generation-not-called trace, and immutable refusal payload:

```json
{"decision":"REFUSAL","answer":"Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này.","citations":[],"refusal_reason":"INSUFFICIENT_EVIDENCE","trace_id":"<present opaque value>"}
```

Source: same pinned commit/blob, symbol `test_no_qualified_evidence_returns_deterministic_http_refusal`.

For upload, polling, reprocess, and question endpoints, observe normal completed HTTP responses with
no SSE content/contract, token-event stream, or percentage-progress response contract. At acceptance,
inspect the Issue #19 implementation change set and require zero introduced UI/frontend artifact or
behavior attributable to this slice. Do not assume a framework, directory, or file extension.

**False pass eliminated.** Route-only no-UI claim, hidden streaming/progress contract, or introduced
frontend surface cannot pass.

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
explicit human approval of `m2-issue-19-r13`.
