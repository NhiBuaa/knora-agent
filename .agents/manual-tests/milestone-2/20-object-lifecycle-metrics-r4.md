# Manual Test Guide: Object lifecycle reconciliation and operational metrics

## Metadata

- Status: Draft — pending explicit human approval; do not implement or execute from this revision.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #20 — Object lifecycle reconciliation and operational metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/20
- Design authority: `CONTEXT.md`; ADR 0006; `docs/standards/architecture.md`; and
  `docs/design/milestone-2-module-seams.md`
- Guide revision: `m2-issue-20-r4`
- Supersedes: drafts `m2-issue-20-r1`, `m2-issue-20-r2`, and `m2-issue-20-r3`; all remain
  unchanged draft history.
- Approved by: Pending
- Approved at: Pending
- Manual-acceptance state: Draft; implementation and execution are blocked on approval.

## Fixed authority

- A committed Original Source Object belongs to its Document Version. No terminal Ingestion Job
  state makes it an automatic cleanup target.
- A Failed-upload Diagnostic Artifact never became an Original Source Object. Its durable
  classification starts a minimum 24-hour retention period. Before eligibility there is no
  destructive cleanup attempt; after a successful eligible cleanup it converges to cleaned/absent.
- Cleanup, reconciliation, and approved hard deletion revalidate authoritative ownership,
  retention references, and Workspace scope immediately before destructive delete.
- Operational Metrics V1 in the Architecture Standard is the only oracle for values, time,
  windows, counters, labels, and alerts. This guide adds no formula or threshold.

## Prerequisites

- The canonical local Compose topology provisions and starts the MinIO target used by TC-07. Test
  evidence identifies that Compose service and startup/health result. A separately launched MinIO
  endpoint does not satisfy this prerequisite.
- An isolated test target is also provisioned for the configured production S3-compatible provider.
  No test object shares storage with a retained or production object.
- Authorized Workspaces `W1` and `W2`; resettable Documents, Versions, Jobs and Attempts; a
  retained Original Source Object sentinel; and independent staging, temporary, and partial
  derivation artifact fixtures.
- PostgreSQL-time control; durable cleanup/reconciliation records; independent metric calculator;
  contract-visible histogram aggregation; ObjectStore capability-boundary audit; and W2 access
  canary.
- Deterministic barriers for terminalization, cleanup discovery, delete acknowledgement,
  bookkeeping commit, hard-delete reference attachment, cleanup-path ownership attachment, and
  worker interruption. Test fixtures use existing authoritative seams; they do not add a production
  attachment API.

## Acceptance traceability matrix

| Issue #20 criterion | Falsifiable test coverage |
| --- | --- |
| Original retention; approved hard deletion; failed-upload diagnostic retention | TC-01, TC-02, TC-05 |
| Async/idempotent cleanup of staging, temporary, and partial artifacts | TC-02–TC-04, TC-10 |
| Independent cleanup failure/retry without outcome reversal | TC-03, TC-08 |
| Safe orphan reconciliation and Workspace isolation | TC-06 |
| SHA-256 metadata and Workspace-scoped ObjectStore behavior | TC-07 |
| Queue and lifecycle metric semantics | TC-08 |
| Configured alert boundary and recovery behavior | TC-09 |
| MinIO and approved S3-compatible subset | TC-07 |
| Contract tests on Compose MinIO and configured provider | TC-07 |
| DB/ObjectStore gaps, duplicate delivery, crash, supersession, failed uploads, retained originals | TC-01–TC-06, TC-10 |

## Locked test cases after approval

### TC-01: Enforce independent hard-deletion blockers, including superseded originals

- Setup: create current-pointer and active-pointer single-blocker fixtures. Create citation, trace,
  and evaluation single-blocker fixtures from committed Original Source Objects owned by superseded
  Document Versions/Jobs. Each fixture retains exactly its named blocker and removes every other
  retention reference. Create no-blocker fixture F.
- Steps:
  1. Invoke approved hard deletion for every single-blocker fixture.
  2. Start F deletion, pause after its initial no-blocker observation, attach one citation reference
     through the authoritative fixture, commit it, prove visibility, and resume deletion.
  3. Remove F's reference and invoke approved hard deletion again.
- Expected results:
  - Each single blocker suppresses deletion. Citation, trace, and evaluation independently suppress
    approved hard deletion of a superseded original.
  - F is suppressed by the stale-reference race and is deleted only after the later no-blocker
    authoritative read-back.
  - Automatic cleanup never deletes a committed Original Source Object of a superseded Job.
- Evidence: fixture blocker projections; superseded version/Job ownership; barrier/read-back trace;
  delete decisions; and final F state.

### TC-02: Enforce failed-upload retention before and after eligibility

- Setup: create a failed-upload staging artifact that never commits a Document Version and persist
  its durable classification timestamp. Keep a retained Original Source Object sentinel in `W1`.
- Steps:
  1. Run discovery/cleanup before 24 hours, recording counter baseline and delete trace.
  2. Advance PostgreSQL time past eligibility; inject transient delete failure.
  3. Run the independently scheduled successful retry and replay/read back its operation.
- Expected results:
  - Before eligibility the artifact remains present, destructive delete count is zero, no durable
    cleanup attempt exists, and cleanup attempt/failure counter deltas are zero.
  - The failed eligible attempt preserves the artifact and leaves submission/ingestion unchanged.
  - The successful retry converges to cleaned/absent; replay adds no effect; sentinel is retained.
- Evidence: baseline/delta metrics; durable times; cleanup records; ObjectStore trace; artifact and
  outcome projections; sentinel delete count.

### TC-03: Prove succeeded terminalization wires asynchronous cleanup

- Setup: run a real Job toward `succeeded` with temporary and partial artifacts. Hold cleanup after
  work is produced/discoverable and before destructive delete.
- Steps:
  1. Complete terminal transition and read durable succeeded Job/Attempt result while cleanup holds.
  2. Prove terminalization did not wait for delete. Release cleanup, inject one temporary delete
     failure, observe it, then run independently scheduled successful retry.
- Expected results:
  - The terminal result is durable before cleanup executes; terminalization produces/discovers real
    cleanup work and does not wait for destructive cleanup.
  - Failure leaves Job succeeded and emits cleanup failure. Retry cleans temporary artifact; partial
    artifact also converges to absent; retained original remains.
- Evidence: terminal/cleanup barrier ordering; commit trace; cleanup discovery; failure/retry records;
  artifact state; metric delta; sentinel delete count.

### TC-04: Prove asynchronous ordering for superseded and failed cleanup

- Setup: for each canonical terminal state `superseded` and `failed`, create each applicable
  temporary and partial-derivation artifact through its existing authoritative execution fixture.
  Do not invent a failure subtype for an inapplicable cell.
- Steps for each applicable state/class cell:
  1. Hold destructive cleanup at its deterministic barrier.
  2. Complete terminal transition and read durable Job/Attempt terminal state.
  3. Prove the artifact remains present and terminalization did not wait for destructive cleanup.
  4. Release cleanup and read final state.
- Expected results:
  - Each terminal transition is durable before cleanup runs; synchronous-only failed or superseded
    cleanup cannot pass.
  - Each applicable artifact converges to cleaned/absent after release; duplicate delivery remains
    idempotent.
  - Committed Original Source Objects remain retained in both states.
- Evidence: completed state/class matrix with `not applicable` rationale only when the existing path
  produces no artifact; barrier/commit/artifact ordering; final state; duplicate result; original
  retention trace.

### TC-05: Revalidate stale ownership through the actual asynchronous cleanup path

- Setup: create an otherwise eligible source/staging cleanup candidate in `W1` and hold its actual
  cleanup path after discovery and before destructive delete.
- Steps:
  1. Pause cleanup at the barrier.
  2. Through the existing deterministic authoritative fixture, attach/reclassify the candidate as a
     retained Original Source Object or add its authoritative blocking ownership/reference. Commit
     and prove visibility through authoritative read-back.
  3. Resume the cleanup path.
- Expected results:
  - Cleanup revalidates at delete time and suppresses deletion. It does not trust stale discovery.
  - The now-retained object remains present and its delete trace is zero.
- Evidence: discovery/attachment/commit/read-back/resume ordering; cleanup decision; object state;
  ObjectStore delete trace.

### TC-06: Reconcile orphans with delete-time and cross-Workspace read canaries

- Setup: in `W1`, create old candidate O1, old eligible orphan O2, a too-young object, inconsistent
  database-object record, and retained-original sentinel. In `W2`, create adversarial object with
  access canary.
- Steps:
  1. Pause W1 reconciliation after O1 discovery. Attach O1 as an Original Source Object, commit,
     prove visibility, and resume destructive phase.
  2. Run a second W1 reconciliation pass and inspect W2 canary.
- Expected results:
  - O1 deletion is suppressed; O2 is cleaned; too-young/retained objects are preserved; inconsistent
    record is repaired or reported.
  - W1 records zero W2 `head`/read/delete/reconciliation access, without prescribing SQL shape.
- Evidence: barrier/attachment trace; per-object disposition; O2 absent state; repair/report record;
  W2 canary report.

### TC-07: Prove ObjectStore contract on canonical Compose MinIO and configured provider

- Run steps once against MinIO started by canonical Compose and once against the configured provider.
- Steps:
  1. Capture Compose service startup/health evidence for MinIO. Under W1, stream A to server-generated
     K1 and B to K2; require K1 != K2; re-open/head K1 after B.
  2. Consume K1 through bounded/incremental stream sentinel. Verify SHA-256, size, media type, and
     controlled ETag differing from SHA-256; delete K1 twice.
  3. Create fresh W1 K1. Attempt head/open/delete under W2, then prove W1 K1 intact.
  4. Inspect provider capability-boundary audit.
- Expected results:
  - Compose, not an external endpoint, provides the MinIO target. K1 remains immutable and caller
    never selects keys.
  - Whole-object application access cannot pass; SHA-256, not ETag, is identity; delete is idempotent.
  - W2 receives no K1 bytes/metadata and cannot mutate K1; no particular error code is required.
  - Boundary audit fails on a capability outside `put_stream`, `open_read`, `head`, idempotent
    `delete`, without asserting SDK internals.
- Evidence: Compose configuration/startup/health and target identity; per-target boundary trace;
  stream report; safe metadata; W2 observations; W1 intact read-back; delete results.

### TC-08: Calculate Operational Metrics V1 with baseline deltas and replay controls

- Setup: capture metric-counter baseline and seed ledger with two eligible Jobs, future retry,
  empty-population control, older due retry whose `created_at` differs from `next_attempt_at`, two
  claims, populated/empty retry windows, two applied `LEASE_EXPIRED` recoveries (schedule-retry and
  retry-exhausted), stale/not-expired/replay controls, and excluded orphan controls.
- Cleanup fixture: durable attempt A is created and fails; independently scheduled attempt B is
  created and succeeds. Replay/read-back A or B and replay A's durable failure classification.
  First orphan discovery is followed by re-observation of the same unresolved identity.
- Steps:
  1. Independently calculate gauges, histogram effects, rate, and counter deltas from ledger.
  2. Collect contract-visible metric representation at same observation and run controls.
- Expected results:
  - `queue_depth = 2`; empty population gives queue depth/oldest age `0/0`; oldest uses `created_at`.
  - Claim histogram has exactly two observations by visible count/sum/bucket effects. Retry rate is
    `2/3` in populated W and no sample in empty W.
  - Lease-recovery delta is 2; stale/not-expired/replay add zero.
  - Cleanup attempt/failure deltas are exactly `2/1`; A/B and failure replay add zero.
  - First orphan discovery delta is 1 and re-observation delta is 0. Retained, cross-Workspace,
    report-only, too-young, and delete-suppressed dispositions do not increment reconciliation.
  - Labels/annotations are low-cardinality and safe.
- Evidence: ledger/calculator; durable records; baseline/delta snapshots; histogram aggregation;
  no-sample proof; label audit.

### TC-09: Test each configured alert negative control separately

- For every configured alert definition, use its versioned predicate, threshold, sustain window,
  and recovery condition.
- Steps: hold below threshold for full sustain duration; separately hold a breach shorter than its
  window; sustain a breach for configured window; then clear it.
- Expected results: first two controls independently produce no alert; sustained breach alerts;
  clear follows configured recovery; alerting does not mutate ingestion or start cleanup.
- Evidence: definition version; four metric-window traces; alert/recovery events; unchanged states.

### TC-10: Reconcile DB/ObjectStore gaps and crash after delete acknowledgement

- Steps: force ObjectStore write success/database rollback; classify resulting object as failed-upload
  diagnostic and prove pre-24-hour preservation then successful eligible cleanup. Reconcile a database
  record for absent object. Acknowledge delete, pause before bookkeeping commit, interrupt worker,
  then resume reconciliation. Repeat applicable cleanup for superseded/failed Jobs with successful
  Job Original Source Object sentinel.
- Expected results: compensation never deletes the diagnostic early; resume converges idempotently
  to one auditable disposition; no gap/crash/retry reverses success or deletes sentinel.
- Evidence: ordered write/rollback/classification/eligibility/delete/ack/bookkeeping/crash/resume
  trace; object/database projections; reconciliation/outcome records; sentinel delete count.

## Final adversarial audit before approval

- [ ] Superseded citation/trace/evaluation retention cannot false-pass.
- [ ] Every applicable terminal state proves asynchronous ordering, not synchronous cleanup.
- [ ] Cleanup itself revalidates stale discovery at delete time.
- [ ] MinIO evidence is from canonical Compose, not an external endpoint.
- [ ] Cleanup counters are per durable attempt, not per artifact or replay.
- [ ] Every matrix row has a falsifiable result and safe evidence; no key selection, SDK internal,
  raw label, or exact cleanup-SLA assertion exists.

This guide becomes immutable only after explicit human approval. Any semantic change creates a new
revision. Execution observations belong in a separate Evaluation JSONL record.
