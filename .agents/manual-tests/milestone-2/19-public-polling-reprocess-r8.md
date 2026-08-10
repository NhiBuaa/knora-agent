# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft. Await explicit human approval. Do not lock, implement, or execute this guide.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #19 — Public polling, reprocess, and PDF citation integration
- Authority: Issue #19; `CONTEXT.md`; Architecture Standard; ADRs 0002 and 0005–0013
- Guide revision: `m2-issue-19-r8`
- Replaces: `m2-issue-19-r7`; r1–r7 remain unchanged and unapproved.

## Scope and evidence rules

- Use controlled clocks, providers, barriers, PostgreSQL/application retrieval-store observations,
  two Workspaces, and reset database/ObjectStore state. Do not use sleeps, timing luck, SQL-string
  assertions, or probabilistic races.
- Capture safe IDs, public bodies/headers, immutable configuration IDs, checksums, equality results,
  and approved spy/projection counts only.

## Locked Test Cases

### TC-01: Successful upload contract and request-idempotency boundaries

For successful created, idempotency-replay, and fingerprint-deduplication upload responses only,
require matched `ingestion_job_id`, exact `submission_outcome`, and six-state public `status` for
that same job. For `IDEMPOTENCY_KEY_CONFLICT`, require safe conflict behavior and no extra
authoritative DB job/Document Version; do not require success-schema fields.

| Setup | Required result |
| --- | --- |
| New upload key/fingerprint | One job; `created`; non-terminal `202`. |
| Same upload key/request, non-terminal/terminal | Same job; `idempotency_replay`; respectively `202`/`200`. |
| Different key, eligible equal fingerprint, non-terminal/terminal | Same job; `deduplicated`; respectively `202`/`200`. |
| Same upload key, different authoritative fingerprint | `IDEMPOTENCY_KEY_CONFLICT`; no extra DB job/version. |
| Filename-only difference with same Workspace/operation/key/canonical source/raw bytes/config IDs | Equal fingerprint; same job; `idempotency_replay`; no conflict/new job/version. |
| Missing reprocess key | Safe rejection; zero generation. |
| Same scoped reprocess key and same authoritative request | Same generation; no extra generation. |
| Same scoped reprocess key and different authoritative fingerprint | `IDEMPOTENCY_KEY_CONFLICT`; zero extra generation. |
| New reprocess key, exact same Document Version/config tuple while matching work processing | Reuse matching generation; no extra generation. |
| New reprocess key, exact same Document Version/config tuple after matching work succeeded | Reuse matching generation; no extra generation. |

Same literal key in Workspaces A/B creates independent bindings/jobs. Same literal key for upload and
reprocess in one Workspace creates independent operation-scoped bindings. Parameterize approved
barrier races for upload/reprocess. Same fingerprint: one Idempotency Record and accepted DB work.
F1/F2: one winner; loser conflict; zero loser DB work; no 500/uniqueness leak. Upload may leave a
temporary unreferenced staging object under existing orphan/sweeper semantics; reprocess creates none.

**False pass eliminated.** Error responses cannot be forced into success schema; filename inclusion,
scope leakage, ambiguous reprocess outcomes, or duplicate accepted DB work cannot pass.

### TC-02: Six public state projections and one committed serving tuple

For every fixture, public `attempt_count` and `max_attempts` are present and equal approved durable
projection; V1 fixture max is 4.

| Fixture | Required state oracle |
| --- | --- |
| Accepted before claim | `queued`; count 0/max 4; no `next_attempt_at`. |
| Claimed handler held | `processing`; count 1..4/max 4; no `next_attempt_at`. |
| Controlled transient failure/clock | `retry_scheduled`; count 1..3/max 4; public `next_attempt_at` equals durable scheduled value. |
| Success | `succeeded`; count 1..4/max 4; no failure reason/next attempt. |
| Deterministic retry exhaustion | `failed`; count=max=4; `failure_reason=retry_exhausted`; separate safe `error_code`; no next attempt/raw diagnostics. |
| TC-05 stale CAS | `superseded`; count 1..4/max 4; no failure reason/next attempt. |

Every poll has `200`, poll hint, and `Cache-Control: no-store`. This fixture proves exhaustion safety,
not all other terminal failure paths. Serving fixtures assert exact HTTP tuple `(target_document_version_id,
current_document_version_id, served_document_version_id, serving_state)`, including nullable served
ID. Valid committed S0/S1 plus one atomic pointer transition requires complete S0 or S1, never hybrid.
Auth: 401/zero lookup; 403 route mismatch/zero lookup; B-scoped A-job lookup then equal unknown-B 404.
UTC RFC3339 is authoritative; timestamp schema/semantics and successful terminal result stay blocked.

**False pass eliminated.** Range-only counters, non-durable retry time, hybrid tuple, early lookup,
or overclaimed terminal-safety coverage cannot pass.

### TC-03: Query-boundary active-only retrieval, J1 failure, and fresh J2

Build adversarial top-k corpus where high-ranked inactive B would consume global window. Approved
retrieval-store/PostgreSQL observation shows database candidates handed to selection already restricted
to Workspace, active Embedding Set, and required Embedding Configuration. Activate A. During J1 B
processing, poll target B/current B/served A/`previous` and capture A-only candidate/retrieved IDs.
After immutable J1 failed, repeat same poll tuple and A-only observation. Create fresh J2 for still-
current B using `config_mode=current` and new key; no `same_as_job`; activate and retrieve B.

**False pass eliminated.** Global query/application filtering, hidden inactive candidates, or reopening
J1 cannot pass.

### TC-04: Configuration-sensitive current-mode fresh reprocess

Fixture: current Document Version V has exactly one prior succeeded J1 with immutable tuple C1. Change
active/current immutable configuration selection to C2 where C2 != C1. Submit new-key
`config_mode=current` reprocess. Require fresh J2, not J1 reuse; J2 `reprocess_of_job_id=J1`;
attempt_count 0/full reset budget; immutable J1; and exact C2 snapshot. Hold worker, mutate later
current selection, release, then require worker still uses C2, succeeds, activates, serves current,
and retrieves active Set.

Require reprocess 401 → 403 → B-scoped lookup of A Document Version, no A generation, and safe
no-existence leakage response. Historical target is `409 DOCUMENT_VERSION_NOT_CURRENT`. Unavailable
source creates no generation; approved ObjectStore spy observes availability check without read/parse.
Do not test exact `same_as_job` configuration.

**False pass eliminated.** Document-Version-only deduplication, missing linkage/reset, predecessor
mutation, late config resolution, or cross-Workspace generation cannot pass.

### TC-05: Exact-tuple reuse and stale-CAS supersession

Use exact same Document Version and immutable tuple for both positive reuse probes: matching work
processing and matching work succeeded. Hold A before finalization, advance current/served state,
release A. Require immutable reuse; A `superseded`; started attempt counted; no added retry/pointer
replacement; old jobs immutable.

**False pass eliminated.** Config-insensitive reuse, post-success duplicate, predecessor mutation,
or stale retry cannot pass.

### TC-06: Server-resolved additive PDF citation provenance and frozen legacy baseline

Use deterministic multi-page PDF and GenerationProvider spy. Provider input contains zero database
Chunk IDs. Provider result cites only request-scoped Evidence Alias IDs; application keeps alias →
persisted Chunk mapping. After provider returns, application resolves final Citation Projection from
persisted Chunk/Document Version provenance, never provider source metadata.

Require complete existing Citation Projection on PDF citation: Document/document-version identity,
source key/display name, heading and line metadata where contract provides it, checksum, and
server-resolved excerpt within existing size contract. Require additive PDF page/half-open offset/
persisted Chunk identity. Derive normalized page text from pinned extractor/normalizer; `[start:end]`
equals persisted Chunk content/checksum and `page_start == page_end`.

Frozen legacy baseline remains pre-Issue-19-implementation (Issue #18 merge) commit
`c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`, blob `92fb06d62d3ce926c14f4302ea60c649983c33da`:

```json
{"evidence_id":"E1","document_id":"document-legacy","document_version_id":"version-legacy","source_key":"support/legacy","source_name":"legacy.md","heading_path":["Legacy"],"start_line":1,"end_line":1,"excerpt":"Legacy citation.","content_checksum":"sha256:legacy","page_start":null,"page_end":null,"start_offset":null,"end_offset":null}
```

**False pass eliminated.** Provider-trusted metadata, lost base citation fields, wrong provenance,
or moved legacy baseline cannot pass.

### TC-07: Connected tracer bullet, tenant query isolation, frozen refusal, no streaming/UI

In A: public upload unique PDF; retain returned job ID; run actual worker for it; poll same job to
success; assert activated target/current/served tuple; ask unique fact; require citation resolves to
that flow's Document Version/Chunk. Do not compose seeded fixtures.

In B, adversarial top-k retrieval-store observation requires B Workspace/B active Set/B config before
selection. B no-evidence question has zero A Set/candidate/retrieved IDs, B-only identities if any,
Generation Provider count zero, and trace generation-not-called. Frozen refusal remains commit/blob
above: `REFUSAL`, existing standard answer, empty citations, `INSUFFICIENT_EVIDENCE`, opaque trace ID.
No-call rule excludes qualified-evidence structured refusal. No SSE, token events, progress, streaming,
or UI/frontend change surface.

**False pass eliminated.** Disconnected tracer proof, global filtering, retrieve-then-refuse,
baseline movement, streaming, or untested UI cannot pass.

## Acceptance-criteria traceability matrix

| Issue #19 criterion | Tests | Coverage |
| --- | --- | --- |
| Upload response: status, job ID, outcome, public state | TC-01 | PASS |
| Six public states and terminal metadata | TC-02 | PARTIAL |
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

1. **Reprocess audit.** Define observable audit correlation, safe observation seam, and audit/enqueue
   relationship or atomicity.
2. **Public timestamp projection.** UTC RFC3339 is defined. Define public schema/names,
   lifecycle/retry/nullability semantics, and durable-source mapping.
3. **`same_as_job` selection.** Define canonical prior generation or explicit selector for multiple
   historical generations.
4. **Successful terminal-result projection.** Authority says terminal result or safe error, but has
   no canonical public field name, shape, contents, or succeeded/superseded semantics.

## Approval gate

Do not lock, implement, execute acceptance, update Issue #19, or change authority artifacts until
explicit human approval of `m2-issue-19-r8`.
