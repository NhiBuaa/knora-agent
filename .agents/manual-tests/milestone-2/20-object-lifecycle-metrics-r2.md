# Manual Test Guide: Object lifecycle reconciliation and operational metrics

## Metadata

- Status: Draft — pending explicit human approval; do not implement or execute from this revision.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #20 — Object lifecycle reconciliation and operational metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/20
- Design authority: `CONTEXT.md`; ADR 0006; `docs/standards/architecture.md`; and
  `docs/design/milestone-2-module-seams.md`
- Guide revision: `m2-issue-20-r2`
- Supersedes: draft `m2-issue-20-r1`, which remains unchanged as draft history.
- Approved by: Pending
- Approved at: Pending
- Manual-acceptance state: Draft; implementation and execution are blocked on approval.

## Fixed authority

- A committed Original Source Object belongs to its Document Version. A Job's terminal state never
  makes it an automatic cleanup target.
- A Failed-upload Diagnostic Artifact is a source or staging object that never became an Original
  Source Object. Its durable failed-upload classification starts a minimum 24-hour retention
  period. Cleanup before expiry is forbidden. A successful eligible cleanup must converge the
  artifact to the cleaned/absent state; asynchronous cleanup has no exact wall-clock SLA.
- Before any destructive delete, cleanup and reconciliation revalidate authoritative ownership,
  retention references, and Workspace scope. A stale discovery snapshot cannot authorize delete.
- Operational Metrics V1 in the Architecture Standard is the sole oracle for queue/lifecycle
  metric values, timestamps, windows, counters, labels, and alert behavior.

## Prerequisites

- An isolated local Compose environment with PostgreSQL and MinIO, plus an isolated test bucket or
  prefix for the configured production S3-compatible provider. No test object shares storage with
  a retained or production object.
- Two authorized Workspaces, `W1` and `W2`; resettable Document/Version/Job/Attempt data; a
  retained Original Source Object sentinel in `W1`; and separate staging, temporary, and partial
  derivation artifact fixtures.
- A deterministic PostgreSQL-time fixture, durable cleanup/reconciliation records, ObjectStore
  operation trace, and a fixture ledger that independently calculates expected metric values.
- Deterministic barriers for discovery, deletion, cleanup acknowledgement, bookkeeping commit,
  worker interruption, and concurrent Document Version attachment. Each injection has one fixed
  action; an operator cannot select behavior during execution.
- Evidence uses only safe IDs, aggregate counts, allowlisted codes, timestamps, and permitted
  low-cardinality labels. It contains no Workspace ID, object key, checksum, filename, raw source,
  credential, ETag, or provider payload.

## Acceptance traceability matrix

| Issue #20 criterion | Falsifiable test coverage |
| --- | --- |
| Original/PDF retention and bounded failed-upload diagnostics | TC-01, TC-02 |
| Async/idempotent staging, temporary, and partial cleanup | TC-02, TC-03, TC-08 |
| Independent cleanup retry without outcome reversal | TC-02, TC-03 |
| Safe orphan detection/reconciliation | TC-04 |
| SHA-256 metadata and Workspace-scoped ObjectStore behavior | TC-05 |
| Queue and lifecycle metric semantics | TC-06 |
| Sustained-condition alerts and recovery | TC-07 |
| MinIO and approved S3-compatible subset | TC-05 |
| Contract tests on MinIO and configured provider | TC-05 |
| DB/ObjectStore gaps, duplicate delivery, crash, supersession, failed uploads, retained originals | TC-02, TC-03, TC-04, TC-08 |

## Locked test cases after approval

### TC-01: Enforce every hard-deletion blocker independently

- Setup: create six equivalent committed Original Source Object fixtures. For each of the first five,
  retain exactly one blocker and remove all other blockers: (A) current pointer, (B) active pointer,
  (C) citation retention, (D) trace retention, or (E) evaluation retention. Fixture F has none.
- Steps:
  1. Invoke the approved hard-deletion path once for each fixture.
  2. Read back ownership, pointer/reference state, and ObjectStore delete trace.
- Expected results:
  - A through E each suppress deletion for their one remaining blocker.
  - F succeeds through the approved path and only after the deletion-time authoritative read-back
    finds no blocker.
  - No terminal Job state changes this result.
- Evidence: one blocker projection per fixture, delete decision, final object presence/absence, and
  Job-state projection.

### TC-02: Enforce failed-upload diagnostic retention and retry convergence

- Setup: create a failed-upload staging artifact that never commits a Document Version. Persist its
  durable classification timestamp. Keep the retained Original Source Object sentinel available.
- Steps:
  1. Run cleanup before the minimum 24 hours expires.
  2. Advance PostgreSQL-owned test time past eligibility. Inject one transient delete failure.
  3. Run the independently scheduled retry with successful ObjectStore delete.
  4. Repeat the successful cleanup delivery/read-back.
- Expected results:
  - Before expiry, the artifact remains present and is not deleted.
  - The failed first eligible attempt preserves the artifact, records one cleanup failure, and does
    not change the submission or ingestion outcome.
  - The successful independent retry converges the artifact to cleaned/absent state. Replay leaves
    the same final state and does not create a second successful effect.
  - The retained Original Source Object sentinel is never deleted.
- Evidence: durable classification/eligibility timestamps, cleanup attempt/failure/retry records,
  ObjectStore trace, artifact state after each step, immutable Job/submission projection, and
  sentinel delete count of zero.

### TC-03: Clean every temporary artifact class without deleting an original

- Setup: create separate eligible artifacts for (A) failed-upload staging after 24 hours,
  (B) terminal-job temporary work, and (C) terminal-job partial derivation work. Keep one retained
  Original Source Object sentinel in the same Workspace.
- Steps:
  1. Dispatch asynchronous cleanup for A, B, and C.
  2. Deliver each cleanup intent twice and read authoritative state after completion.
- Expected results:
  - Each A/B/C artifact reaches cleaned/absent state after its successful eligible cleanup.
  - Duplicate delivery is idempotent for every artifact class.
  - The sentinel remains present; its delete trace remains zero.
- Evidence: class-tagged safe cleanup disposition, two delivery results per class, final object and
  record state, and sentinel ownership/delete trace.

### TC-04: Reconcile orphans with a deterministic attach-before-delete race

- Setup: in `W1`, create an old candidate O1 and a second old eligible orphan O2; create a
  too-young candidate, an inconsistent database-object record, and a retained-original sentinel.
  In `W2`, create an adversarial ownership sentinel that must never be read or mutated by W1 work.
- Steps:
  1. Start reconciliation and pause at the deterministic barrier immediately after O1 discovery.
  2. Attach O1 to a committed Document Version as its Original Source Object; commit and prove the
     attachment is visible through an authoritative read-back.
  3. Resume the destructive phase and then run a second reconciliation pass.
- Expected results:
  - Delete-time revalidation suppresses O1 deletion after the visible attachment.
  - O2 is still unreferenced and old, so it is cleaned successfully; a no-op sweeper cannot pass.
  - The too-young, retained, and cross-Workspace sentinels are preserved.
  - The inconsistent record is repaired or reported with a durable safe disposition.
- Evidence: barrier ordering trace; committed attachment read-back before resume; per-object
  disposition; O2 absent state; W2 unchanged projection; and repair/report record.

### TC-05: Prove the ObjectStore contract on both S3-compatible targets

- Run every step once against MinIO and once against the configured production S3-compatible test
  target.
- Steps:
  1. Stream content A through `put_stream`; receive server-generated K1. Stream different content B
     through `put_stream`; receive K2.
  2. Require K1 and K2 to differ. Re-open and `head` K1 after B is written.
  3. Read K1 through a bounded/incremental stream sentinel that fails if application code performs
     whole-object access or retains all source bytes simultaneously.
  4. Verify Workspace scope, SHA-256, byte size, and media type; use a controlled ETag that differs
     from SHA-256. Delete K1 twice through the approved seam.
  5. Inspect provider-operation evidence for the full run.
- Expected results:
  - K1 bytes and metadata remain unchanged after B creates K2. The test never selects an object key.
  - Bounded/incremental streaming passes; whole-object application access cannot pass.
  - SHA-256, not ETag, is the content identity. The second delete is idempotent.
  - Provider evidence shows only `put_stream`, `open_read`, `head`, and idempotent `delete`; it does
    not require or assert SDK internals.
- Evidence: per-target capability trace, stream-sentinel report, safe metadata comparison, K1/K2
  inequality, K1 before/after projection, two delete results, and approved-subset audit.

### TC-06: Calculate Operational Metrics V1 independently

- Setup: seed a durable fixture ledger at one PostgreSQL observation time:
  - two eligible Jobs (one `queued`, one due retry), one future retry, and no other eligible Job;
  - eligible `created_at` values that make the oldest age independently calculable;
  - one first claim and one retry claim with known durable eligibility and claim timestamps;
  - three closed Attempts in `W`, two with `retry_policy_result = schedule_retry`; then an empty
    `W` control window;
  - one applied `LEASE_EXPIRED` recovery, one stale observation, one not-expired observation, and a
    replay/read-back of the applied recovery;
  - two cleanup attempts, one durable failure, one retry attempt; one first orphan discovery, a
    re-observation of that orphan, one completed repair, one completed eligible deletion, and
    report-only/too-young/delete-suppressed controls.
- Steps:
  1. Derive each expected value from the fixture ledger without calling the metrics implementation.
  2. Collect the Operational Metrics V1 snapshot at the same observation point.
  3. Compare exact gauge/counter values, claim-latency samples, retry-rate value, and no-sample
     behavior for the empty retry window.
- Expected results:
  - `queue_depth = 2`; the future retry is excluded.
  - `oldest_job_age` equals `clock_timestamp() - created_at` for the older eligible Job.
  - `claim_latency` contains exactly the two independently calculated non-negative samples.
  - `retry_rate = 2/3` in populated `W`, and emits no sample in empty `W`.
  - Lease-expiry recovery increments once; cleanup attempts/failures count 3/1; orphan
    discovery/reconciliation count 1/2. Controls do not increment their excluded counters.
  - Labels and annotations contain only the approved low-cardinality values.
- Evidence: fixture ledger and independent calculation, durable timestamp/closure records, metric
  snapshot, sample/counter comparison, no-sample observation, and label/annotation redaction audit.

### TC-07: Test configured alert definitions at their boundaries

- For each configured definition—queue age/contention, repeated lease-expiry recovery, cleanup
  backlog, and unreconciled orphan growth—use its versioned predicate, threshold, sustain window,
  and recovery condition as the only oracle.
- Steps:
  1. Produce a value below threshold or a breach shorter than the configured sustain window.
  2. Maintain a breach at/above threshold for the configured sustain window.
  3. Clear the condition and observe the configured recovery behavior.
- Expected results:
  - Step 1 produces no alert.
  - Step 2 produces the matching defined alert.
  - Step 3 follows the configured recovery behavior.
  - Alerting does not mutate a successful ingestion or trigger destructive cleanup.
- Evidence: alert-definition version, metric window, alert state/timestamp, recovery event, and
  unchanged ingestion/cleanup projection.

### TC-08: Reconcile DB/ObjectStore gaps and crash after delete acknowledgement

- Steps:
  1. Force `ObjectStore` write success followed by database rollback. Classify the object durably as
     a Failed-upload Diagnostic Artifact; prove pre-24-hour preservation, then successful eligible
     cleanup after 24 hours.
  2. Create a database object record for an absent object and verify reconciliation repairs or
     reports the inconsistency without inventing ingestion success.
  3. At a deterministic checkpoint, acknowledge destructive delete, pause before cleanup
     bookkeeping commits, interrupt the worker, then resume reconciliation.
  4. Repeat the relevant cleanup delivery for superseded and failed-upload Jobs while retaining a
     successful Job's Original Source Object sentinel.
- Expected results:
  - The write/rollback artifact follows the same 24-hour diagnostic lifecycle; compensation does
    not delete it immediately.
  - Resumed reconciliation converges the acknowledged-delete case idempotently with one auditable
    final disposition.
  - No gap or retry reverses a successful ingestion or deletes the retained sentinel.
- Evidence: ordered write/rollback/classification/eligibility/delete/bookkeeping/crash/resume trace;
  object and database projections; reconciliation record; Job outcomes; and sentinel delete count.

## Review gate before approval

- [ ] Every criterion has a falsifiable result and evidence, not only a named surface.
- [ ] Staging, temporary, and partial artifacts each have a passing cleanup case.
- [ ] All destructive paths include authoritative delete-time revalidation and a retained-original
  sentinel.
- [ ] Metric and alert expected values use Operational Metrics V1 and an independent fixture ledger.
- [ ] No case relies on caller-selected object keys, SDK internals, raw metric labels, or an exact
  asynchronous deletion SLA.

This guide becomes immutable only after explicit human approval. Any semantic change creates a new
revision. Execution observations belong in a separate Evaluation JSONL record.
