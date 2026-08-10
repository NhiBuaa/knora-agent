# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft. Await explicit human approval. Do not lock, implement, or execute this guide.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #19 — Public polling, reprocess, and PDF citation integration
- Authority: Issue #19; `CONTEXT.md`; Architecture Standard; ADRs 0002 and 0005–0013
- Guide revision: `m2-issue-19-r7`
- Replaces: `m2-issue-19-r6`; r1–r6 remain unchanged and unapproved.

## Scope and evidence rules

- Use controlled clocks, providers, barriers, PostgreSQL/application retrieval-store observations,
  two Workspaces, and reset database/ObjectStore state. Do not use sleeps, timing luck, SQL-string
  assertions, or probabilistic races.
- Capture safe IDs, public bodies/headers, immutable configuration IDs, checksums, equality results,
  and approved spy/projection counts only.

## Locked Test Cases

### TC-01: Upload/reprocess public idempotency contract

Every upload response MUST contain its matched `ingestion_job_id`, exact branch
`submission_outcome`, and public six-state `status` for that same job; no internal state substitutes.

| Setup | Required result |
| --- | --- |
| New upload key/fingerprint | One job; `created`; non-terminal `202`. |
| Same upload key/request, non-terminal/terminal | Same job; `idempotency_replay`; respectively `202`/`200`. |
| Different key, eligible equal fingerprint, non-terminal/terminal | Same job; `deduplicated`; respectively `202`/`200`. |
| Same upload key with distinct authoritative fingerprint | `IDEMPOTENCY_KEY_CONFLICT`; no extra DB job/version. |
| Filename-only change with same Workspace/operation/key/canonical source/raw bytes/config IDs | Equal fingerprint; same job; `idempotency_replay`; no conflict/new job/version. |
| Missing reprocess key | Safe rejection; zero new generation. |
| Same reprocess key/request or different fingerprint | Same generation/no extra; or `IDEMPOTENCY_KEY_CONFLICT`/zero extra. |
| New reprocess key, equal work processing/after success | Reuse matching generation; no extra generation. |

Same literal key in A/B upload creates independent bindings/jobs. Same literal key in one Workspace
for upload/reprocess creates independent operation-scoped bindings.

For upload and reprocess, run an approved barrier concurrency seam immediately before competing
durable idempotency persistence. Same fingerprint: one Idempotency Record and one accepted DB job/
version/generation, with both responses resolving to it. Conflicting F1/F2: one winner DB binding/
work; loser `IDEMPOTENCY_KEY_CONFLICT`; zero loser DB work. No 500/uniqueness leak.

Upload may temporarily retain an unreferenced loser staging object. It must not be accepted work and
follows existing orphan/sweeper semantics. Reprocess creates no staging object.

**False pass eliminated.** Filename inclusion, scope leakage, duplicate accepted DB work, and an
incorrect requirement for immediate orphan deletion cannot pass.

### TC-02: Poll all six states, exact counters, and one committed serving tuple

Capture a safe public poll projection for each fixture. For every fixture, public `attempt_count`
and `max_attempts` are present and equal the approved read-only durable job projection. Fixtures use
the approved V1 budget `max_attempts=4`.

| Fixture | Required public result |
| --- | --- |
| Accepted job held before claim | `queued`; count 0; max 4; no `next_attempt_at`. |
| Claimed handler held | `processing`; count 1..4; max 4; no `next_attempt_at`. |
| Controlled transient failure/clock | `retry_scheduled`; count 1..3; max 4; `next_attempt_at` equals durable scheduled value. |
| Successful completion | `succeeded`; count 1..4; max 4; no failure reason or `next_attempt_at`. |
| Deterministic retry exhaustion | `failed`; `attempt_count=max_attempts=4`; `failure_reason=retry_exhausted`; separate safe `error_code`; no `next_attempt_at` or raw diagnostics. |
| TC-05 stale CAS | `superseded`; count 1..4; max 4; no failure reason or `next_attempt_at`. |

Each poll has `200`, `poll_after_seconds` or `Retry-After`, and `Cache-Control: no-store`. This
exhaustion fixture proves only its explicit failure reason; do not claim it proves other mappings.

For each unavailable/current/previous fixture, assert exact HTTP tuple
`(target_document_version_id, current_document_version_id, served_document_version_id, serving_state)`.
`served_document_version_id` may be null. S0/S1 are committed valid tuples. During one controlled
atomic pointer transition, response equals all S0 or all S1; hybrid fails. Do not require one SQL
statement.

Auth probes: invalid key → `401 UNAUTHENTICATED`/zero lookup; B principal on A route →
`403 WORKSPACE_ACCESS_DENIED`/zero lookup; B route with A job ID → authorized B-scoped lookup and
same `404 INGESTION_JOB_NOT_FOUND` body as unknown B job.

UTC RFC3339 is authoritative. Timestamp public schema/semantics and successful terminal-result
projection remain blocked below; do not invent either.

**False pass eliminated.** Range-only counters, non-durable retry time, missing nullable served ID,
hybrid tuple, early lookup, or overclaimed failure taxonomy cannot pass.

### TC-03: Query-boundary active-only retrieval; J1 failure then fresh J2

Create adversarial top-k data where high-ranked inactive historical B candidates would consume a
global window before filtering. Approved retrieval-store/PostgreSQL observation must show database
candidates handed to selection already limited to authorized Workspace, active Set, and required
Embedding Configuration. Do not assert SQL formatting.

Activate A. Submit changed B as J1. While J1 processes, poll J1 and require target B/current B/
served A/`previous`; ask A question and capture candidate/retrieved IDs. After J1 terminally fails,
poll J1 again and require the same tuple/`previous`; capture A-only candidates/retrieval again. J1
remains immutable failed.

Create fresh eligible J2 for still-current B using `config_mode=current` and new scoped key. Do not
use `same_as_job`. Complete J2; require B activation and B-only retrieval.

**False pass eliminated.** Global query then application filtering, hidden inactive B candidates,
and terminal J1 reopening cannot pass.

### TC-04: Fresh current-mode reprocess linkage, reset, configuration, and activation

Use one-prior-job fixture. Before claim, new current-mode reprocess differs from sole prior job,
has `reprocess_of_job_id` to it, `attempt_count=0`, full approved budget, and unchanged prior
count/history/state. Hold worker, mutate mutable current config, release worker, then require
snapshotted IDs, success, active complete derivation, served=current, and active-set retrieval.

For reprocess, verify 401 → 403 → scoped B lookup of A Document Version. The B-scoped lookup creates
no A generation and returns safe no-existence-leak behavior; do not require job-specific 404.
Historical target is `409 DOCUMENT_VERSION_NOT_CURRENT`. Unavailable source creates no generation;
approved ObjectStore spy proves enqueue availability check without read/parse. Do not test
`same_as_job` exact configuration.

**False pass eliminated.** Missing linkage/reset budget, predecessor mutation, late config use,
success without activation, or cross-Workspace generation cannot pass.

### TC-05: Equal-work reuse and stale-CAS supersession

Run equal-work branches during processing and after success. Hold A before finalization, advance
current/served state, then release A. Require immutable reuse; A `superseded`; started attempt counted;
no added retry; no pointer replacement; old jobs immutable.

**False pass eliminated.** Post-success duplication, old-job mutation, or stale retry cannot pass.

### TC-06: PDF provenance and immutable legacy citation baseline

Use deterministic multi-page PDF. Get normalized page text from pinned extractor/normalizer, then
compare cited Document Version, persisted Chunk ID, 1-based page, half-open offsets, checksum, and
`page_start == page_end`. `[start:end]` in normalized text equals persisted Chunk content/checksum.

The unchanged pre-Issue-19-implementation baseline (Issue #18 merge state) is commit
`c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`, blob `92fb06d62d3ce926c14f4302ea60c649983c33da`:

```json
{"evidence_id":"E1","document_id":"document-legacy","document_version_id":"version-legacy","source_key":"support/legacy","source_name":"legacy.md","heading_path":["Legacy"],"start_line":1,"end_line":1,"excerpt":"Legacy citation.","content_checksum":"sha256:legacy","page_start":null,"page_end":null,"start_offset":null,"end_offset":null}
```

**False pass eliminated.** Wrong Chunk/offset/checksum/cross-page locator or moved legacy baseline
cannot pass.

### TC-07: Connected tracer bullet, tenant query isolation, frozen refusal, no streaming/UI

Run one connected A scenario: upload one unique deterministic PDF through public endpoint; retain its
returned job ID; run actual approved worker path for that job; poll that same job to success; assert
activated target/current/served tuple; ask fact unique to that PDF; require citation resolves to the
Document Version/Chunk from exactly that upload/worker flow. Do not compose seeded fixtures.

For B, use adversarial top-k data where A candidates would consume global B window. Retrieval-store
observation must show candidate set handed to selection already B Workspace/B active Set/B required
configuration. B no-evidence question has zero A Set/candidate/retrieved IDs, B-only identities if
any, provider invocation count zero, and trace generation-not-called disposition.

Frozen refusal baseline remains commit `c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`, blob
`92fb06d62d3ce926c14f4302ea60c649983c33da`: `REFUSAL`; existing standard answer; empty citations;
`INSUFFICIENT_EVIDENCE`; present opaque trace ID. No-call rule does not apply to qualified-evidence
structured refusal. Inspect transport/change set: no SSE, token events, percentage progress,
streaming, or UI/frontend surface.

**False pass eliminated.** Disconnected tracer proof, global-filtered retrieval, retrieve-then-refuse,
baseline movement, streaming, or untested UI cannot pass.

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

1. **Reprocess audit.** Define observable audit correlation, safe observation seam, and
   audit/enqueue relationship or atomicity.
2. **Public timestamp projection.** UTC RFC3339 is defined. Define public schema/names, lifecycle/
   retry/nullability semantics, and durable-source mapping.
3. **`same_as_job` selection.** Define canonical prior generation or explicit selector for multiple
   historical generations.
4. **Successful terminal-result projection.** Search found only “terminal result or safe error,”
   not public field name, result shape, IDs/outcome contents, or succeeded/superseded semantics.

## Approval gate

Do not lock, implement, execute acceptance, update Issue #19, or change authority artifacts until
explicit human approval of `m2-issue-19-r7`.
