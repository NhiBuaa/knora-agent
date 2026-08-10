# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft. Await explicit human approval. Do not lock, implement, or execute this guide.
- Feature/Slice: Milestone 2, GitHub Issue #19
- Authority: Issue #19, `CONTEXT.md`, Architecture Standard, ADRs 0002 and 0005–0013
- Revision: `m2-issue-19-r9`; r1–r8 remain unchanged and unapproved.

## Evidence rules

- Use controlled clocks/providers/barriers, retrieval-store observations, two Workspaces, and reset
  database/ObjectStore state. Never use sleep, timing luck, SQL strings, or probabilistic races.
- Capture safe IDs, public bodies/headers, immutable configuration IDs, checksums, equality results,
  and approved spy/projection counts only.

## Locked Test Cases

### TC-01: Success response contract and request idempotency

For successful created, replay, and dedup uploads only, require matched `ingestion_job_id`, exact
`submission_outcome`, and six-state `status`. Conflict requires safe
`IDEMPOTENCY_KEY_CONFLICT` and zero extra DB job/version, not success fields.

| Setup | Required result |
| --- | --- |
| New upload | One job; `created`; non-terminal `202`. |
| Same key/request, non-terminal or terminal | Same job; `idempotency_replay`; `202` or `200`. |
| Different key, eligible equal fingerprint, non-terminal or terminal | Same job; `deduplicated`; `202` or `200`. |
| Same key, different authoritative fingerprint | Conflict; zero extra DB job/version. |
| Filename-only difference with same Workspace/operation/key/source/raw bytes/config IDs | Equal fingerprint; same job; replay; no conflict/new work. |
| Missing reprocess key | Safe rejection; zero generation. |
| Same reprocess key/same request | Same generation; zero extra generation. |
| Same reprocess key/different fingerprint | Conflict; zero extra generation. |
| New reprocess key, exact same Version/config while matching work processing or succeeded | Reuse matching generation; zero extra generation. |

Same literal key in A/B upload has independent bindings/jobs. Same literal key for upload/reprocess in
one Workspace has independent operation bindings. Race upload and reprocess separately through an
approved barrier. Same fingerprint gives one durable Idempotency Record, one accepted DB job/generation,
and both responses resolve to it; no conflict for either request and no 500/uniqueness detail. Upload
before worker progress returns created/replay for same non-terminal job; reprocess uses only defined
same-generation replay behavior. F1/F2 gives one winner, one conflict, and zero loser DB work. Upload
orphan staging may remain unreferenced under existing sweeper semantics; reprocess creates none.

**False pass eliminated.** Filename inclusion, scope leakage, same-fingerprint conflict, duplicate DB
work, or temporary-orphan over-specification fails.

### TC-02: Exact attempt progression, six states, and serving tuple

Use controlled database/clock sequence on one fresh job:

| Event | Required public/durable projection |
| --- | --- |
| Accepted before claim | `queued`; count 0; max 4; no next attempt. |
| First claim | `processing`; count 1; max 4; no next attempt. |
| First retryable failure | `retry_scheduled`; count 1; max 4; public retry time equals durable value. |
| Advance only until due; second claim | `processing`; count 2; max 4; no next attempt. |

Separately verify success has count 1..4/max 4, no failure reason/next attempt. Retry exhaustion has
failed/count=max=4/reason `retry_exhausted`/safe error code/no next attempt/no raw diagnostics. An
approved malformed, unsupported, or textless fixture gives non-exhaustion failed with a reason in
exact domain `retry_exhausted | terminal_input | terminal_config | resource_limit`, safe code, no raw
detail, and no next attempt. Do not require which non-exhaustion reason applies. Stale CAS gives
superseded/count 1..4/max 4/no failure reason/no next attempt.

Every poll has 200, hint, no-store. For unavailable/current/previous, assert HTTP tuple
`(target_document_version_id,current_document_version_id,served_document_version_id,serving_state)`
equals all committed S0 or all S1; served may be null; controlled transition has no hybrid. Auth is
401/zero lookup, 403 route mismatch/zero lookup, then B-scoped A-job lookup equals unknown-B 404.
Timestamp schema/semantics and successful terminal result stay blocked.

**False pass eliminated.** Double/skipped/decremented count, unsafe non-exhaustion failure, hybrid
tuple, or pre-auth lookup fails.

### TC-03: Query-boundary active retrieval, J1 failure, fresh J2

Adversarial top-k data makes inactive B consume global window if filtering occurs late. Retrieval-store
observation proves database candidates handed to selection already have Workspace, active Set, and
embedding-config predicates. During J1 processing and after immutable J1 failure, poll B/B/A/previous
and capture A-only candidates/retrieval. Fresh J2 uses current mode plus new key, never same-as-job;
J2 activates B and retrieval moves to B.

### TC-04: C1→C2 current-mode fresh reprocess

Sole prior succeeded J1 for V uses C1. Set current config to C2 != C1. New current-mode J2 is fresh,
links to J1, has count 0/max 4/full reset budget, leaves J1 unchanged, and snapshots C2. Hold worker,
mutate later selection, release; worker uses C2, succeeds, activates, serves current, retrieves active
Set. Reprocess 401→403→B-scoped A-version lookup creates no A generation and returns safe no-leak
response. Historical target 409; unavailable source creates none; object-store spy sees availability
check only. Do not test exact same-as-job configuration.

### TC-05: Exact-tuple reuse and stale supersession

Both reuse probes use exact Version/config tuple while match processes and after success. Hold A before
finalization, advance current/served, release A. Require immutable reuse, superseded A, counted started
attempt, no retry/pointer replacement, and immutable old jobs.

### TC-06: Server-resolved PDF citation and frozen baseline

Provider spy sees zero DB Chunk IDs and cites request-scoped Evidence Alias only. Application retains
alias-to-Chunk map and resolves base Citation Projection plus page/offset/Chunk provenance from
persisted data. Pinned normalized `[start:end]` equals Chunk content/checksum; page start=end.
Legacy baseline remains commit `c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`, blob
`92fb06d62d3ce926c14f4302ea60c649983c33da`, with r8 embedded JSON unchanged.

### TC-07: Connected tracer bullet, tenant isolation, frozen refusal, no UI/stream

In A: public upload → retained job → actual worker → same-job success poll → activated pointer tuple
→ unique-fact citation to that flow's Version/Chunk. In B, adversarial retrieval-store observation
proves B Workspace/active Set/config before selection. B no-evidence has zero A IDs, B-only IDs if any,
provider calls 0, trace generation-not-called, and frozen commit/blob refusal: REFUSAL, existing answer,
empty citations, INSUFFICIENT_EVIDENCE, opaque trace ID. No SSE/events/progress/streaming/UI surface.

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

1. Reprocess audit: observable correlation, safe observation seam, audit/enqueue relationship.
2. Public timestamp projection: schema/names, lifecycle/retry/nullability semantics, durable mapping.
   UTC RFC3339 is defined.
3. `same_as_job`: canonical prior generation or explicit selector for multiple prior generations.
4. Successful terminal result: public field/shape/contents and succeeded/superseded semantics.

## Approval gate

Do not lock, implement, execute acceptance, update Issue #19, or change authority artifacts until
explicit human approval of `m2-issue-19-r9`.
