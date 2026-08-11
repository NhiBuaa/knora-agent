# Manual Test Guide: Object lifecycle reconciliation and operational metrics

## Metadata

- Status: Draft — pending explicit human approval; do not implement or execute from this revision.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #20 — Object lifecycle reconciliation and operational metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/20
- Design authority: `CONTEXT.md`; `docs/adr/0006-document-version-owned-source-objects.md`;
  `docs/standards/architecture.md`; `docs/design/milestone-2-module-seams.md`
- Guide revision: `m2-issue-20-r1`
- Approved by: Pending
- Approved at: Pending
- Manual-acceptance state: Draft; implementation and execution are blocked on approval.

## Fixed authority

An Original Source Object belongs to its committed Document Version. A terminal Ingestion Job
state, including `failed`, `retry_exhausted`, `resource_limit`, or `superseded`, does not make that
object eligible for cleanup.

A Failed-upload Diagnostic Artifact is only a source or staging object that never became an
Original Source Object of a committed Document Version. Knora records a durable classification
timestamp for it. It is retained for at least 24 hours from that timestamp, then becomes eligible
for asynchronous cleanup. The 24-hour rule is independent of Idempotency Record retention.

Every destructive cleanup or reconciliation delete must revalidate authoritative database
ownership, references, and Workspace scope immediately before deletion. A discovery snapshot is
not sufficient. An attached or retained object must be preserved.

## Prerequisites

- Environment: an isolated local Compose topology with PostgreSQL and MinIO. A separately
  provisioned, isolated test bucket/prefix is available for the configured production
  S3-compatible provider. No test may use a shared or production-retained object.
- Data: two authorized Workspaces; Documents with current and historical Document Versions;
  current and active references; citation, trace, and evaluation retention fixtures; committed
  Original Source Objects; failed-upload diagnostic artifacts; staging, temporary, and partial
  artifacts; and resettable Ingestion Jobs in each relevant terminal state.
- Time: a Knora-owned durable timestamp fixture for failed-upload classification and a controlled
  clock or database-time fixture that can observe before and after its 24-hour minimum. Tests must
  not use application wall time as the retention authority.
- Instrumentation: ObjectStore operation trace, SHA-256/byte-size/media-type metadata projection,
  database ownership/reference read-back, cleanup attempt and retry records, queue/lifecycle metric
  snapshots, alert events, and safe Workspace-scoped identifiers. Evidence must not expose raw
  PDFs, opaque object keys, credentials, ETags, or provider payloads.
- Fault controls: deterministic injection for an ObjectStore write/commit gap, cleanup delete
  failure, duplicate delivery, worker interruption, stale discovery, and a concurrent attachment
  of an object as an Original Source Object. Each injection has one named action and cannot be
  chosen by an operator during execution.

## Acceptance traceability matrix

| Issue #20 criterion | Test case |
| --- | --- |
| Document Version-owned originals and bounded failed-upload diagnostics | TC-01, TC-02 |
| Asynchronous, idempotent cleanup that preserves originals | TC-02, TC-03 |
| Independent cleanup retry and observable failure | TC-03 |
| Safe Workspace-scoped orphan reconciliation | TC-04 |
| SHA-256 metadata and ObjectStore behavior | TC-05 |
| Queue and lifecycle metrics | TC-06 |
| Alerts for operational degradation | TC-07 |
| MinIO and approved S3-compatible subset | TC-05 |
| MinIO and configured-provider ObjectStore contracts | TC-05 |
| Commit/object gaps and terminal-lifecycle cleanup cases | TC-08 |

## Locked test cases after approval

### TC-01: Preserve committed Original Source Objects

- Purpose: Prove that Document Version retention, not terminal Job state, owns an Original Source
  Object.
- Steps:
  1. Create committed Document Versions whose Original Source Objects are respectively associated
     with successful, failed, retry-exhausted, resource-limit, and superseded Ingestion Jobs.
  2. Run the asynchronous cleanup worker for each eligible terminal-job queue item.
  3. Attempt approved hard deletion while a current/active ownership constraint or a citation,
     trace, or evaluation retention fixture exists.
  4. Remove every blocking retention reference through the approved test-only hard-deletion path
     and repeat the deletion request.
- Expected results:
  - Cleanup does not delete any committed Original Source Object because of its Job state.
  - Each blocking reference suppresses hard deletion.
  - Only the approved path may delete the object after every required reference is absent.
- Evidence to capture:
  - Document Version/object ownership before and after each cleanup run; terminal Job state;
    delete-operation trace; blocking-reference projection; and final approved deletion result.

### TC-02: Retain and then clean a failed-upload diagnostic artifact

- Purpose: Prove the separate 24-hour diagnostic lifecycle.
- Steps:
  1. Submit a source/staging object that fails before a Document Version commits. Record its durable
     failed-upload classification timestamp and prove it has no Original Source Object reference.
  2. Run cleanup before the 24-hour minimum has elapsed.
  3. Advance the authoritative test time beyond the minimum and run cleanup twice for the same
     artifact.
- Expected results:
  - The artifact is not automatically deleted before expiry.
  - After expiry, cleanup may delete it asynchronously; no exact deletion time is required.
  - Repeated cleanup delivery is idempotent and leaves one consistent final artifact/record state.
  - This result does not depend on, or mutate, an Idempotency Record retention value.
- Evidence to capture:
  - Classification timestamp; authoritative before/after-expiry time samples; ownership read-back;
    two cleanup-operation IDs/results; final object/record state; and Idempotency Record unchanged.

### TC-03: Retry cleanup independently without reversing ingestion

- Purpose: Prove cleanup failure isolation and observability.
- Steps:
  1. Create one expired failed-upload diagnostic artifact and one successful ingestion with a
     retained Original Source Object.
  2. Force the first diagnostic-artifact delete to fail with a transient storage failure.
  3. Observe the cleanup record and lifecycle metrics, then run the independently scheduled retry.
  4. Inspect the successful ingestion and its retained original before and after both runs.
- Expected results:
  - The failure creates an observable cleanup-failure signal and a separately retryable cleanup
    attempt.
  - The submission and ingestion outcomes remain unchanged.
  - The retry may complete cleanup of the diagnostic artifact and never deletes the retained
    original.
- Evidence to capture:
  - Cleanup attempt/failure/retry projection; metric samples; alert event if configured; Job and
    submission outcomes; and Original Source Object delete count of zero.

### TC-04: Reconcile orphans with delete-time ownership checks

- Purpose: Prove safe handling of unreferenced objects and inconsistent database object records.
- Steps:
  1. Seed, in separate Workspaces, an old unreferenced staging object, a too-young unreferenced
     object, an object with an inconsistent database record, and a retained Original Source Object.
  2. Run the sweeper and inspect each discovery disposition.
  3. Between discovery and destructive delete, attach the old unreferenced object to a committed
     Document Version as its Original Source Object.
  4. Run the delete phase and a second reconciliation pass.
- Expected results:
  - The sweeper repairs or reports each inconsistent record according to its safe disposition.
  - Age and Workspace guards preserve the too-young and cross-Workspace objects.
  - Delete-time revalidation suppresses deletion of the newly attached retained object.
  - No operation reads, reports, repairs, or deletes an object through another Workspace.
- Evidence to capture:
  - Discovery and delete-time ownership/reference snapshots; age/Workspace guard result;
    repair/report disposition; object and database record counts by Workspace; and suppressed-delete
    trace.

### TC-05: Verify the ObjectStore contract against both S3-compatible targets

- Purpose: Prove the approved streaming capability subset in MinIO and the configured production
  S3-compatible provider.
- Steps:
  1. For each target, stream a test object through `put_stream` and record returned metadata.
  2. Stream it through `open_read`, compute and compare its SHA-256, and inspect `head` metadata.
  3. Attempt a second write at the same opaque key and attempt idempotent deletion twice.
  4. Repeat with a controlled ETag value that differs from the SHA-256 value.
- Expected results:
  - `put_stream`, `open_read`, `head`, and idempotent `delete` work without a whole-object read.
  - Metadata preserves Workspace scope, opaque server-generated key, SHA-256, byte size, and media
    type. ETag is not used as the content hash.
  - Objects are immutable: a conflicting second write is rejected without replacing bytes.
  - The second delete is safe and produces no new error or cross-Workspace effect.
- Evidence to capture:
  - Per-target streaming trace; read chunk count; SHA-256 comparison; metadata projection; immutable
    write result; two delete results; and safe ETag-versus-SHA-256 evidence.

### TC-06: Expose queue and lifecycle metrics

- Purpose: Prove each required metric has a correct, Workspace-safe source observation.
- Steps:
  1. Seed queued, due-retry, processing, succeeded, and expired-lease-recovery fixtures with known
     durable timestamps and attempt history.
  2. Create one cleanup success, one cleanup failure, one orphan discovery, and one reconciliation.
  3. Collect the operational metrics snapshot.
- Expected results:
  - Queue metrics include depth, oldest-job age, claim latency, retry rate, and lease-expiry
    recovery.
  - Lifecycle metrics include cleanup attempts, cleanup failures, orphan discovery, and orphan
    reconciliation.
  - Metric values match the seeded observations and do not expose object keys, raw source data, or
    cross-Workspace identifiers.
- Evidence to capture:
  - Fixture ledger; metric snapshot with labels/dimensions; calculation input counts/timestamps;
    lease-recovery record; and redacted-safety review.

### TC-07: Raise alerts for sustained degradation

- Purpose: Prove all required alert classes use the metric signals without changing lifecycle
  outcomes.
- Steps:
  1. In an isolated alert test environment, sustain each configured trigger condition separately:
     queue age/contention, repeated lease-expiry recovery, cleanup backlog, and unreconciled orphan
     growth.
  2. Collect the resulting alert events and corresponding metric windows.
  3. Clear each condition and observe the configured recovery behavior.
- Expected results:
  - Each sustained condition produces its defined alert with the matching metric evidence.
  - Alerts use safe identifiers and do not expose source bytes, opaque keys, or credentials.
  - Alerting neither changes a successful ingestion result nor performs destructive cleanup.
- Evidence to capture:
  - Trigger configuration reference; metric window; alert type/state/timestamp; recovery event; and
    unchanged ingestion/cleanup outcome projection.

### TC-08: Reconcile transaction gaps and terminal cleanup delivery

- Purpose: Cover object/database gaps and the lifecycle races named by Issue #20.
- Steps:
  1. Force an ObjectStore write that succeeds before the database transaction fails or rolls back.
  2. Force a database object record that references an object absent from ObjectStore.
  3. Deliver the same cleanup intent twice, interrupt a cleanup worker after its destructive call,
     and resume reconciliation.
  4. Repeat the relevant cleanup path for a superseded Job, a failed upload, and a successful Job
     with a retained Original Source Object.
- Expected results:
  - Reconciliation records or repairs each gap without inventing a successful ingestion.
  - Duplicate delivery and worker interruption converge idempotently.
  - Superseded and failed-upload artifacts follow their own eligible cleanup rules.
  - A successful Job's retained Original Source Object remains untouched.
- Evidence to capture:
  - Object/database before-and-after projections; reconciliation report; cleanup operation IDs and
    retry history; worker-interruption trace; Job outcomes; and retained-original delete count.

## Approval checklist

- [ ] The guide uses the explicit Issue #20 24-hour failed-upload diagnostic retention decision,
  not the Idempotency Record policy.
- [ ] Every destructive case requires authoritative delete-time revalidation and Workspace scope.
- [ ] Every Issue #20 acceptance criterion has an observable test case and evidence requirement.
- [ ] The guide introduces no implementation mechanism beyond the approved ObjectStore seam and
  authority documents.
- [ ] Human approval is recorded before implementation starts.

This guide becomes immutable after explicit human approval. Any semantic change requires a new
guide revision. Store execution observations separately in the matching Evaluation JSONL file.
