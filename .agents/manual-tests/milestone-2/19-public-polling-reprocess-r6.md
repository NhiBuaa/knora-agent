# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft. Await explicit human approval. Do not lock, implement, or execute this guide.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #19 — Public polling, reprocess, and PDF citation integration
- Authority: Issue #19; `CONTEXT.md`; Architecture Standard; ADRs 0002 and 0005–0013
- Guide revision: `m2-issue-19-r6`
- Replaces: `m2-issue-19-r5`; r1–r5 remain unchanged and unapproved.

## Scope and evidence rules

- Use controlled clocks, providers, barriers, PostgreSQL/application retrieval-store observations,
  two Workspaces, and reset database/ObjectStore state. Do not use sleeps or probabilistic races.
- Capture safe IDs, public bodies/headers, configuration IDs, checksums, equality results, and
  approved spy/projection counts only. Do not capture raw internal details or assert SQL text.

## Locked Test Cases

### TC-01: Prove response contract, idempotency scope, and durable race outcomes

Every upload response MUST contain `ingestion_job_id` for the matched logical job, exact listed
`submission_outcome`, and public `status` from exactly `queued`, `processing`, `retry_scheduled`,
`succeeded`, `superseded`, or `failed`. Status MUST describe that job; no internal state substitutes.

| Request setup | Required result |
| --- | --- |
| New upload key/new authoritative fingerprint | One job; `created`; non-terminal `202 Accepted`. |
| Same upload key/request while non-terminal | Same job; `idempotency_replay`; `202 Accepted`. |
| Same upload key/request after terminal | Same job; `idempotency_replay`; `200 OK`. |
| Different key, eligible equal fingerprint, non-terminal/terminal match | Same matched job; `deduplicated`; respectively `202`/`200`. |
| Same upload key, different authoritative fingerprint | `IDEMPOTENCY_KEY_CONFLICT`; no extra DB job/Document Version. |
| Filename-only change: same Workspace/operation/key/canonical source/raw bytes/immutable config IDs | Equal request fingerprint; same job; `idempotency_replay`; no conflict/new job/Document Version. |
| Missing reprocess key | Safe rejection; zero new generation. No unapproved error/status required. |
| Same scoped reprocess key/request | Same generation; no extra generation. |
| Same scoped reprocess key, authoritative fingerprint difference | `IDEMPOTENCY_KEY_CONFLICT`; zero extra generation. |
| New reprocess key with equal work during processing/after success | Reuse matching generation; no extra generation. |

Use one literal key in A and B for independent uploads: independent bindings/jobs, no replay/conflict/
cross-Workspace reuse. In one Workspace, use one literal key for upload and reprocess: independent
operation-scoped bindings, no cross-operation replay/conflict.

**Concurrent probes.** Parameterize approved application/PostgreSQL barriers for upload and
reprocess. Same Workspace+operation+key+fingerprint requests: exactly one authoritative Idempotency
Record and one accepted DB job/Document Version/generation; both responses resolve to it; no 500 or
uniqueness leak. Distinct F1/F2 requests: one winner binding/accepted DB work; loser returns
`IDEMPOTENCY_KEY_CONFLICT`; no loser-side authoritative DB job/version/generation.

For upload only, do not require immediate absence of a loser staging object. If present, it is
unreferenced by accepted work and follows existing orphan/sweeper semantics. Reprocess races invent
no source staging object.

**False pass eliminated.** Filename inclusion, scope leakage, duplicate authoritative DB work, and
an invalid demand for cross-system transactional staging cleanup cannot pass.

### TC-02: Poll all six public states from one committed snapshot

Capture one safe poll projection for every fixture:

| Fixture | Required state oracle |
| --- | --- |
| Accepted job held before claim | `queued`; `attempt_count=0`; no `next_attempt_at`. |
| Claimed handler held | `processing`; attempt count 1..max; no `next_attempt_at`. |
| Controlled classified transient failure with deterministic clock | `retry_scheduled`; attempt count 1..max-1; `next_attempt_at` present. |
| Successful completion | `succeeded`; attempt count 1..max; terminal result; no failure reason/`next_attempt_at`. |
| Deterministic retry exhaustion | `failed`; `failure_reason=retry_exhausted`; final counted attempt; separate safe `error_code`; no `next_attempt_at` or raw diagnostics. |
| TC-05 stale CAS | `superseded`; attempt count 1..max; no failure reason/`next_attempt_at`. |

Every poll returns `200 OK`, `poll_after_seconds` or `Retry-After`, and `Cache-Control: no-store`.
Serving/snapshot/auth probes are mandatory: all `unavailable`/`current`/`previous` meanings; valid
committed S0/S1 separated by one atomic pointer transition with hybrid FAIL; 401 then zero lookup;
403 route mismatch then zero lookup; authorized scoped B lookup of A job then same 404 body as
unknown B job.

UTC RFC3339 format is authoritative. Do not mark timestamp projection PASS until public schema and
semantics are decided; do not invent timestamp field names.

**False pass eliminated.** State vocabulary alone, missing retry exhaustion mapping, invalid failure
reason, hybrid snapshots, early lookup, and terminal diagnostics cannot pass.

### TC-03: Query-boundary active-only retrieval and fresh B reprocess

1. Build adversarial top-k corpus where high-ranking inactive historical B candidates would consume
   the candidate window if global retrieval were filtered afterward. Use approved PostgreSQL
   retrieval-store observation to capture database-result candidates handed to application evidence
   selection. Require them already constrained to Workspace, active Embedding Set, and required
   Embedding Configuration; do not assert SQL syntax.
2. Activate A. Submit changed B as J1. During J1 processing and after immutable terminal J1 failure,
   ask A question. Require every observed candidate/retrieved chunk belongs to active A.
3. Create fresh eligible J2 for still-current B using `config_mode=current` and new scoped key. Do
   not use `same_as_job`. Complete J2, then require B activation and retrieval.

**False pass eliminated.** A global query plus application filtering fails even when final Trace is
legal; a failed J1 cannot reopen instead of a fresh J2.

### TC-04: Current-mode fresh reprocess linkage, budget, config, and activation

Use a fixture with exactly one prior job for the Document Version. Establish eligible fresh
`config_mode=current` work with no equal processing/succeeded generation. Immediately after new
generation creation and before claim require: different new ID; `reprocess_of_job_id` points to sole
prior job; `attempt_count=0`; full approved attempt budget; and unchanged prior job count/history/
state. Hold worker, mutate mutable current config, release, then require snapshotted IDs, success,
active complete derivation, served=current, and retrieval from active Set.

Also enforce reprocess 401 → 403 → scoped lookup ordering; historical target returns
`409 DOCUMENT_VERSION_NOT_CURRENT`; unavailable source yields no generation and enqueue checks only
availability without read/parse (approved ObjectStore spy). Do not test `same_as_job` exact config.

**False pass eliminated.** A “fresh” job cannot omit linkage/reset budget, mutate the predecessor,
resolve config late, or succeed before activation.

### TC-05: Reuse equal work and supersede stale work

Run TC-01 equal-work branches during processing and after success. Hold A before finalization, advance
current/served state, then release A. Require immutable reuse; A `superseded`; started attempt
counted; no added retry; no current/served replacement; old jobs immutable.

**False pass eliminated.** Duplicate post-success work, predecessor mutation, or stale retry cannot
appear as valid supersession.

### TC-06: Exact PDF provenance and frozen legacy baseline

Use deterministic multi-page PDF. Derive normalized page text through pinned extractor/normalizer,
not page-text persistence. Compare cited Document Version, persisted Chunk ID, physical 1-based page,
half-open offsets and checksum. Apply `[start:end]` to normalized page text; require Chunk content/
checksum equality and `page_start == page_end`.

The compatibility payload is unchanged from pre-Issue-19-implementation baseline (Issue #18 merge
state), commit `c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`, blob
`92fb06d62d3ce926c14f4302ea60c649983c33da`:

```json
{"evidence_id":"E1","document_id":"document-legacy","document_version_id":"version-legacy","source_key":"support/legacy","source_name":"legacy.md","heading_path":["Legacy"],"start_line":1,"end_line":1,"excerpt":"Legacy citation.","content_checksum":"sha256:legacy","page_start":null,"page_end":null,"start_offset":null,"end_offset":null}
```

**False pass eliminated.** Correct page cannot hide wrong Chunk/offset/checksum/cross-page locator,
and tests cannot move this compatibility baseline.

### TC-07: Query-boundary tenant isolation, frozen refusal, no streaming/UI

Create adversarial top-k corpus where high-ranking Workspace-A candidates would consume global B
candidate window. Using approved PostgreSQL retrieval-store observation, require candidates handed to
selection already restricted to B Workspace, B active Set, and required B Embedding Configuration.
Ask B's no-qualified-evidence question. Require zero A Set/candidate/retrieved IDs, B-only identities
if any, Generation Provider count zero, and Question Trace established generation-not-called state.

The unchanged pre-Issue-19-implementation refusal payload uses commit
`c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`, blob
`92fb06d62d3ce926c14f4302ea60c649983c33da`: `decision="REFUSAL"`; answer
`"Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này."`; `citations=[]`;
`refusal_reason="INSUFFICIENT_EVIDENCE"`; present opaque trace ID. This no-call rule does not apply
when qualified evidence exists and provider returns structured refusal.

Observe transport and Issue #19 change surface. Require no SSE, token events, percentage progress,
streaming response, or UI/frontend artifact/behavior.

**False pass eliminated.** Global retrieval then filtering, retrieve-then-refuse, baseline movement,
streaming, and untested UI cannot pass.

## Acceptance-criteria traceability matrix

| Issue #19 criterion | Tests | Coverage |
| --- | --- | --- |
| Upload response: status, job ID, outcome, public state | TC-01 | PASS |
| Six public states and safe terminal metadata | TC-02 | PASS |
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

1. **Reprocess audit.** Define minimum observable audit correlation semantics, safe observation seam,
   and audit/enqueue relationship or atomicity.
2. **Public timestamp projection.** UTC RFC3339 is defined. Define public schema/field names,
   lifecycle/retry/nullability semantics, and durable-source mapping.
3. **`same_as_job` selection.** Define canonical prior-generation selection or explicit selector for
   a Document Version with multiple historical generations.

## Frontier evidence

Native GitHub dependencies remain authoritative; #18 is closed:

```powershell
gh issue view 18 --repo NhiBuaa/knora-agent --json number,state,closedAt,url
# {"closedAt":"2026-08-10T01:08:25Z","number":18,"state":"CLOSED",...}
```

## Approval gate

Do not lock, implement, execute acceptance, update Issue #19, or change authority artifacts until
explicit human approval of `m2-issue-19-r6`.
