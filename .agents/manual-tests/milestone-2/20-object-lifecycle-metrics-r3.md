# Manual Test Guide: Object lifecycle reconciliation and operational metrics

## Metadata

- Status: Draft — pending explicit human approval; do not implement or execute from this revision.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #20 — Object lifecycle reconciliation and operational metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/20
- Design authority: `CONTEXT.md`; ADR 0006; `docs/standards/architecture.md`; and
  `docs/design/milestone-2-module-seams.md`
- Guide revision: `m2-issue-20-r3`
- Supersedes: drafts `m2-issue-20-r1` and `m2-issue-20-r2`; both remain unchanged draft history.
- Approved by: Pending
- Approved at: Pending
- Manual-acceptance state: Draft; implementation and execution are blocked on approval.

## Fixed authority

- A committed Original Source Object belongs to its Document Version. No terminal Ingestion Job
  state makes it an automatic cleanup target.
- A Failed-upload Diagnostic Artifact never became an Original Source Object. Its durable
  classification starts a minimum 24-hour retention period. Before eligibility there is no
  destructive cleanup attempt; after a successful eligible cleanup it converges to cleaned/absent.
- Cleanup and reconciliation revalidate authoritative ownership, retention references, and
  Workspace scope immediately before destructive delete. A stale discovery or no-blocker
  observation cannot authorize delete.
- Operational Metrics V1 in the Architecture Standard is the only oracle for values, time,
  windows, counters, labels, and alerts. This guide does not define new formulas or thresholds.

## Prerequisites

- An isolated local Compose environment with PostgreSQL and MinIO, plus an isolated test bucket or
  prefix for the configured production S3-compatible provider.
- Authorized Workspaces `W1` and `W2`; resettable Documents, Versions, Jobs and Attempts; a
  retained Original Source Object sentinel; and independent staging, temporary, and partial
  derivation artifact fixtures.
- PostgreSQL-time control; a fixture ledger and independent metric calculator; cleanup and
  reconciliation records; ObjectStore capability/audit trace; and contract-visible histogram
  aggregation evidence.
- Deterministic barriers for terminalization, cleanup dispatch/discovery, destructive delete
  acknowledgement, bookkeeping commit, stale-reference attachment, and worker interruption.
- A Workspace access canary that records every observable ObjectStore/reconciliation access made
  under `W2` scope. Evidence contains only safe aggregate IDs/counts and approved low-cardinality
  labels; it contains no Workspace ID, object key, checksum, source bytes, credential, ETag, or
  provider payload.

## Acceptance traceability matrix

| Issue #20 criterion | Falsifiable test coverage |
| --- | --- |
| Original retention; approved hard deletion; failed-upload diagnostic retention | TC-01, TC-02 |
| Asynchronous/idempotent cleanup of staging, temporary, and partial artifacts | TC-02, TC-03, TC-04, TC-09 |
| Independent cleanup failure/retry without outcome reversal | TC-03 |
| Safe orphan reconciliation and Workspace isolation | TC-05 |
| SHA-256 metadata and Workspace-scoped ObjectStore behavior | TC-06 |
| Queue and lifecycle metric semantics | TC-07 |
| Configured alert boundary and recovery behavior | TC-08 |
| MinIO and approved S3-compatible capability subset | TC-06 |
| Contract tests on MinIO and configured provider | TC-06 |
| DB/ObjectStore gaps, duplicate delivery, crash, supersession, failed uploads, retained originals | TC-02–TC-05, TC-09 |

## Locked test cases after approval

### TC-01: Enforce independent hard-deletion blockers and stale-reference revalidation

- Setup: create six equivalent committed Original Source Objects. Fixtures A–E each retain exactly
  one blocker and remove all others: current pointer, active pointer, citation, trace, or
  evaluation retention. Fixture F starts with no blocker.
- Steps:
  1. Invoke the approved hard-deletion path for A–E and read back the one blocking reference.
  2. Start the F deletion path. Pause after its initial no-blocker observation and before its
     destructive action.
  3. Add one citation retention reference to F, commit it, and prove its visibility through the
     authoritative deletion-time read-back. Resume the path.
  4. Remove that reference and invoke the approved path again.
- Expected results:
  - A–E are each suppressed by their one independent blocker.
  - F deletion is suppressed after the committed stale-reference race.
  - F is deleted only after the later authoritative read-back finds no blocker.
  - Automatic cleanup of a superseded Job never deletes its committed Original Source Object.
- Evidence: per-fixture blocker projection; barrier/order trace; deletion-time read-backs; delete
  decisions; F object state before/after the final request; and superseded-original delete count.

### TC-02: Enforce failed-upload retention before and after eligibility

- Setup: create a failed-upload staging artifact that never commits a Document Version. Persist its
  durable classification timestamp. Keep a retained Original Source Object sentinel in `W1`.
- Steps:
  1. Run discovery/cleanup before 24 hours. Record counters from a baseline before the run.
  2. Advance authoritative PostgreSQL time past eligibility. Inject a transient delete failure.
  3. Run the independently scheduled successful retry, then deliver/read back that same operation
     again.
- Expected results:
  - Before eligibility, the artifact remains present, ObjectStore destructive delete count is zero,
    no durable cleanup-attempt record exists, and cleanup-attempt/failure counter deltas are zero.
  - The eligible failed attempt preserves the artifact, records one observable cleanup failure, and
    does not change submission or ingestion outcome.
  - The independently scheduled successful retry converges to cleaned/absent; replay has no second
    effect. The retained sentinel remains present.
- Evidence: baseline/delta metric snapshots; classification/eligibility timestamps; cleanup records;
  ObjectStore trace; artifact state after every step; outcome projection; and sentinel delete count.

### TC-03: Prove terminalization wires asynchronous cleanup without waiting for it

- Setup: run a real Job toward the canonical `succeeded` terminal transition with temporary and
  partial-derivation artifacts owned by that Job. Hold cleanup execution at a deterministic barrier
  after work is produced/discoverable but before destructive delete.
- Steps:
  1. Complete the real terminal transition and read back its durable `succeeded` Job/Attempt result
     while the cleanup barrier remains held.
  2. Prove no terminalization transaction waits for destructive cleanup and the terminal outcome is
     already visible.
  3. Release cleanup discovery/execution. Inject one temporary-artifact delete failure.
  4. Observe the cleanup failure, then run its independently scheduled successful retry.
- Expected results:
  - Terminalization is durable and `succeeded` before cleanup may run; it does not wait for delete.
  - Terminal outcome produces or makes discoverable real cleanup work. A disconnected cleanup worker
    cannot pass.
  - The injected cleanup failure leaves the Job `succeeded`, emits the observable failure signal,
    and does not reverse ingestion.
  - The independent retry cleans the temporary artifact. The partial artifact also reaches
    cleaned/absent state. A retained Original Source Object sentinel is never deleted.
- Evidence: terminalization/cleanup barrier ordering; transaction/commit trace; Job/Attempt state;
  cleanup-work discovery record; delete/failure/retry records; artifact states; metric deltas; and
  sentinel delete count.

### TC-04: Close the terminal-outcome × artifact-class cleanup matrix

- Setup: use the canonical terminal Job states `succeeded`, `superseded`, and `failed`. For each
  state, create every applicable temporary and partial-derivation artifact that the existing
  authoritative execution path produces; do not invent a failure subtype to manufacture an
  inapplicable artifact.
- Steps:
  1. Complete each fixture through its canonical terminal state.
  2. Execute the produced/discovered cleanup work successfully and deliver it twice.
- Expected results:
  - Each applicable state/class cell reaches cleaned/absent state after successful cleanup.
  - Successful terminal cleanup is directly proven, not inferred from an Original Source Object
    sentinel.
  - Duplicate cleanup delivery is idempotent. Committed Original Source Objects remain retained in
    every state, including superseded.
- Evidence: completed matrix with explicit `not applicable` rationale only where no authoritative
  path produces that class; terminal state; produced cleanup work; final artifact state; duplicate
  delivery result; and retained-original trace.

### TC-05: Reconcile orphans with delete-time and cross-Workspace read canaries

- Setup: in `W1`, create old candidate O1, old eligible orphan O2, a too-young object, an
  inconsistent database-object record, and a retained-original sentinel. In `W2`, create an
  adversarial object and enable its access canary.
- Steps:
  1. Start W1 reconciliation and pause immediately after O1 discovery.
  2. Attach O1 to a committed Document Version as its Original Source Object; commit and prove the
     attachment is visible through an authoritative read-back. Resume deletion.
  3. Run a second W1 reconciliation pass and inspect the W2 canary.
- Expected results:
  - Delete-time revalidation suppresses O1 deletion. O2 is cleaned, so a no-op sweeper cannot pass.
  - The too-young and retained objects are preserved; the inconsistent record is repaired or
    reported with a durable safe disposition.
  - W1 reconciliation records zero W2 ObjectStore `head`/read/delete and zero W2 reconciliation
    access. No SQL or query shape is prescribed.
- Evidence: barrier/attachment ordering; per-object disposition; O2 absent state; repair/report
  record; W2 canary report; and retained-object trace.

### TC-06: Prove ObjectStore contract, bounded streaming, and Workspace denial

- Run every step against MinIO and the configured production S3-compatible test target.
- Steps:
  1. Under W1, stream content A through `put_stream` to receive K1, then different content B to
     receive K2. Require K1 and K2 to differ. Re-open and `head` K1 after B.
  2. Consume K1 with a bounded/incremental stream sentinel that fails on whole-object application
     access or simultaneous retention of all source bytes.
  3. Verify SHA-256, byte size, media type, and a controlled ETag different from SHA-256. Delete K1
     twice through the approved seam.
  4. Create a fresh W1 K1. Attempt `head`, open, and delete under W2 scope. Then prove under W1
     that K1 bytes and metadata remain intact.
  5. Inspect the capability-boundary audit.
- Expected results:
  - K1 is immutable after K2 is written; callers never select either key.
  - Bounded streaming passes and whole-object access cannot pass. SHA-256, not ETag, is identity.
  - W2 receives neither K1 bytes nor metadata and does not mutate K1; no specific exception code is
    required.
  - The audit fails if the provider boundary receives an operation outside `put_stream`,
    `open_read`, `head`, or idempotent `delete`; it does not rely only on application method logs or
    assert SDK internals.
- Evidence: per-target capability-boundary trace; stream-sentinel report; safe metadata comparison;
  K1/K2 and K1 before/after projections; W2 denial observations; W1 intact read-back; and two
  delete results.

### TC-07: Calculate Operational Metrics V1 with adversarial controls

- Setup: record a counter baseline, then seed an independent durable fixture ledger with:
  - two eligible Jobs, one future retry, and an empty-eligible-population control;
  - an older due retry whose `created_at` differs from `next_attempt_at`, to distinguish the required
    `created_at` oldest-age semantics;
  - one first claim and one retry claim with known durable eligibility/claim timestamps;
  - three closed Attempts in window W, two scheduled for retry, plus an empty W control;
  - two applied `LEASE_EXPIRED` recoveries, one schedule-retry and one retry-exhausted; stale,
    not-expired, and replay controls;
  - cleanup creation, replay/read-back, one durable failure classification and its replay; and
  - first orphan discovery, re-observation, two corrective dispositions, and retained,
    cross-Workspace, report-only, too-young, and delete-suppressed controls.
- Steps:
  1. Calculate expected gauges, histogram aggregation effects, rates, and counter deltas from the
     ledger without calling metrics implementation.
  2. Collect the contract-visible Operational Metrics V1 representation at the same observation.
  3. Run empty-population and replay controls and compare deltas from the recorded baseline.
- Expected results:
  - `queue_depth = 2`; future retry is excluded. Empty population gives `queue_depth = 0` and
    `oldest_job_age = 0`.
  - Oldest age uses the eligible Job's `created_at`, not retry `next_attempt_at`.
  - `claim_latency` receives exactly two observations, proven by its contract-visible histogram
    count/sum/bucket effects, not raw individual samples.
  - `retry_rate = 2/3` in populated W and emits no sample in empty W.
  - Lease-expiry recovery delta is two; stale/not-expired/replay do not add delta. Cleanup-attempt
    replay and cleanup-failure-classification replay add no delta. Orphan reconciliation delta is
    two; retained/cross-Workspace and all excluded controls add none.
  - Labels/annotations contain only approved low-cardinality values.
- Evidence: ledger/calculator output; durable timestamps and closure records; baseline/delta metric
  snapshots; histogram aggregation evidence; no-sample observation; and label/annotation audit.

### TC-08: Test each configured alert negative control separately

- For each configured alert definition—queue age/contention, repeated lease-expiry recovery,
  cleanup backlog, and unreconciled orphan growth—use its versioned predicate, threshold, sustain
  window, and recovery condition as the oracle.
- Steps:
  1. Hold the metric below predicate/threshold for at least its full sustain duration.
  2. Satisfy the predicate but hold it for less than its sustain window.
  3. Sustain the breach for the configured window.
  4. Clear the condition.
- Expected results:
  - Steps 1 and 2 each produce no alert independently.
  - Step 3 produces the matching alert. Step 4 follows configured recovery behavior.
  - Alerting neither changes successful ingestion nor starts destructive cleanup.
- Evidence: alert-definition version; four metric-window traces; alert/recovery events; and unchanged
  ingestion/cleanup projections.

### TC-09: Reconcile DB/ObjectStore gaps and crash after delete acknowledgement

- Steps:
  1. Force ObjectStore write success followed by database rollback. Classify the object durably as a
     Failed-upload Diagnostic Artifact; prove pre-24-hour preservation, then successful eligible
     cleanup after 24 hours.
  2. Create a database object record for an absent object and reconcile it without inventing a
     successful ingestion result.
  3. Acknowledge destructive delete, pause before cleanup bookkeeping commits, interrupt the worker,
     then resume reconciliation.
  4. Repeat applicable cleanup delivery for superseded and failed-upload Jobs while retaining a
     successful Job's Original Source Object sentinel.
- Expected results:
  - Compensation does not delete the write/rollback diagnostic artifact before its retention ends.
  - Resume converges the acknowledged-delete case to one auditable final disposition, idempotently.
  - No gap, crash, or retry reverses successful ingestion or deletes the retained sentinel.
- Evidence: ordered write/rollback/classification/eligibility/delete/ack/bookkeeping/crash/resume
  trace; object/database projections; reconciliation record; outcome projections; and sentinel
  delete count.

## Review gate before approval

- [ ] Every matrix row has a falsifiable oracle and named evidence.
- [ ] Terminalization→cleanup wiring, not manual cleanup dispatch alone, is proven end to end.
- [ ] All applicable terminal-state/artifact-class cells are explicit; no failure subtype is invented.
- [ ] Cross-Workspace reads, not only writes, fail observably.
- [ ] Excluded metric populations, replay controls, and separate alert negatives cannot false-pass.
- [ ] No case requires caller-selected keys, SDK internals, raw labels, or a wall-clock cleanup SLA.

This guide becomes immutable only after explicit human approval. Any semantic change creates a new
revision. Execution observations belong in a separate Evaluation JSONL record.
