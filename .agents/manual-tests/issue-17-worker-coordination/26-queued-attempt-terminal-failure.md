# Manual Test Guide: Queued Attempt to Deterministic Terminal Failure

## Metadata

- Status: Approved and locked
- Feature: Issue #17 — PostgreSQL worker coordination lifecycle
- Slice: GitHub issue #26 — Process one queued attempt to deterministic terminal failure
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/26
- Approved design: `docs/design/issue-17-worker-coordination.md`
- Guide revision: `issue-26-v1`
- Approved by: Nhi (explicit human approval in Codex task)
- Approved at: 2026-08-09T12:54:55+07:00

## Prerequisites

- Environment: local checkout with the repository virtual environment and Docker Compose
  available. Use a disposable PostgreSQL database based on the repository's
  `pgvector/pgvector:pg16` service; bound service startup/readiness and do not record credentials.
- Baseline: Ticket #25 Evaluation run `issue-25-20260809-path-b-passed` is the accepted regression
  baseline. Capture commit, branch, concise dirty state, Python/pytest versions and non-secret
  PostgreSQL identity for this run.
- Migration state: tests can create isolated databases at the pre-Issue-#26 Alembic revision and at
  the new revision without mutating a developer's durable database.
- Test data: valid Workspace, Document, Document Version, Original Source Object, immutable
  configuration references and queued Ingestion Jobs. Use allowlisted failure kinds/codes only.
- Determinism: concurrency tests use barriers/events or database locks with explicit bounds, never
  correctness-sensitive sleeps. All pytest commands and service readiness checks have explicit
  wall-time bounds.
- Scope: this guide accepts only `queued -> processing -> failed`. Retry, expired recovery,
  heartbeat, timeout/supervision, success, superseded and ambiguous-commit reconciliation remain
  absent.

## Locked Test Cases

### TC-01: Migrate known queued legacy jobs without fabricating attempt history

- Purpose: prove the coordination schema has a safe legacy policy before claim behavior depends on
  it.
- Steps:
  1. Create an isolated database at the pre-Issue-#26 revision with representative valid queued
     jobs whose `attempt_count` is zero.
  2. Upgrade to the Issue #26 revision and inspect job projection defaults, the attempt table,
     constraints, triggers and stable candidate indexes required by this slice.
  3. In separate isolated databases, create a legacy non-queued job and a legacy job with nonzero
     `attempt_count`, then attempt the same upgrade.
- Expected results:
  - Valid queued rows survive with their known identity, `attempt_count=0`, `lease_version=0`, no
    current-attempt/lease projection and no synthesized attempt-history row.
  - The attempt table and this slice's constraints/indexes are present after a valid upgrade.
  - Unknown non-queued or nonzero-attempt legacy state makes migration fail loudly and atomically;
    no worker, lease, start time or attempt history is invented.
- Evidence to capture:
  - Alembic before/after revisions, representative row projections, empty history assertion for
    legacy queued rows, schema-object assertions and both rejected legacy-state results.

### TC-02: Atomically claim one queued job and end the transaction before work

- Purpose: prove the first durable lifecycle transition and immutable fencing capability.
- Steps:
  1. Insert multiple eligible queued jobs and invoke the typed claim operation with a fixed Worker
     ID, Claim Operation ID and attempt timing profile.
  2. Inspect the returned Claimed Attempt and the committed job/open-attempt rows.
  3. Hold a deterministic fake Work Handler at its entry boundary and use an independent database
     transaction to verify the claim transaction is no longer open or holding the job lock.
- Expected results:
  - One atomic operation selects at most one queued job using `FOR UPDATE SKIP LOCKED` or an
    equivalent single-owner query; no candidate is queried then claimed in a separate operation.
  - The selected job changes to `processing`; `attempt_count` and `lease_version` each increment
    exactly once; current worker, attempt number, start/deadline and lease projection exactly match
    one newly inserted open attempt.
  - `attempt_number` equals the post-increment `attempt_count`; the attempt snapshots the initial
    lease expiry and claim generation.
  - The returned Claimed Attempt/Fencing Token is immutable data, not an ORM/session/transaction
    handle, and the handler begins only after claim commit.
- Evidence to capture:
  - Claim result projection, before/after counters, matching job/attempt fields, open-attempt count,
    capability type/immutability assertions and independent transaction/lock probe.

### TC-03: Allow only one winner under simultaneous claims

- Purpose: prove concurrent workers cannot start duplicate attempts for one queued job.
- Steps:
  1. Arrange one queued job and start two claim transactions with distinct Worker IDs and Claim
     Operation IDs behind a deterministic concurrency barrier.
  2. Release both claims and collect their typed results under an explicit timeout.
  3. Inspect durable job and attempt state after both transactions resolve.
- Expected results:
  - Exactly one worker receives the immutable claim; the other receives no claim and does not run a
    handler for that job.
  - Durable state has `attempt_count=1`, one lease-generation increment and exactly one matching
    open attempt; there is never a second open attempt or attempt number.
  - Transactions terminate within the bound and no correctness assertion relies on query-plan or
    timing luck.
- Evidence to capture:
  - Worker/result pairing, bounded concurrency trace, final counters/token and open-attempt query.

### TC-04: Finalize a typed deterministic failure through the deep application seam

- Purpose: prove the complete tracer bullet from `run_once()` through typed cause mapping and the
  explicit terminal-failure transaction.
- Steps:
  1. Configure a deterministic fake Work Handler to return a closed/versioned non-retryable failure
     kind with an allowlisted bounded safe code.
  2. Invoke `ProcessIngestionJob.run_once(worker_id)` for one queued job.
  3. Reload the job projection and its attempt history from PostgreSQL.
- Expected results:
  - The handler receives data-only work and no persistence capability; its failure kind maps
    exhaustively through the versioned cause boundary.
  - `run_once()` processes only this attempt and returns the tagged `FAILED_TERMINAL` result after
    authoritative durable finalization.
  - The explicit fenced terminal-failure operation atomically closes the open attempt and changes
    the job from `processing` to public `failed`; terminal timestamp, canonical cause/version,
    failure reason and allowlisted safe code agree across projection/history.
  - Current worker/lease/current-attempt fields are cleared, `next_attempt_at` is absent, and no raw
    exception, provider/SQL text, path, content or secret is persisted.
- Evidence to capture:
  - Handler input/outcome types, mapping identity, tagged result, post-commit job/attempt rows and
    sanitized metadata inspection.

### TC-05: Fence stale terminal writes before transition legality

- Purpose: prove database ownership—not local coordinator state—prevents stale outcome commits.
- Steps:
  1. Create a current processing attempt and construct wrong-worker, wrong-lease-version and
     expired-lease variants of its otherwise matching fencing token.
  2. Attempt terminal failure finalization for each stale variant, including a case whose target
     transition would otherwise be invalid.
  3. Finalize once with the current unexpired capability and then try a duplicate/stale terminal
     write.
- Expected results:
  - Every ownership mismatch or expired lease returns typed `FENCED` before transition-legality
    disclosure and leaves job/attempt state unchanged.
  - The current capability applies exactly one atomic closure; a later terminal write cannot mutate
    the projection or closed history.
  - PostgreSQL fresh-time ownership predicates include job identity, worker, lease generation,
    unexpired lease and expected processing/open-attempt state.
- Evidence to capture:
  - Variant/result matrix, unchanged-state snapshots for fenced writes, successful closure and
    duplicate-write result.

### TC-06: Enforce projection/history, immutability and minimal operation binding

- Purpose: prove defense-in-depth constraints for this slice without prematurely implementing
  ambiguous read-back.
- Steps:
  1. Attempt to commit mismatched job/open-attempt counters, identities or current-attempt timing;
     also attempt a second open attempt for one job.
  2. After a valid terminal closure, attempt normal-application-role UPDATE and DELETE operations on
     the closed history row.
  3. Exercise claim and terminal-transition Operation ID uniqueness/request binding with compatible
     and incompatible identities within each retained operation kind.
- Expected results:
  - Commit-time cross-table validation rejects a processing projection without exactly one matching
    open attempt and rejects counter/timing/token mismatches while permitting valid claim and
    finalization transaction ordering.
  - The partial uniqueness rule rejects a second open attempt. A closed attempt permits no further
    normal application mutation or delete.
  - Retained Claim and Transition Operation IDs are bound to immutable request identity and unique
    within their kinds; incompatible reuse is an invariant failure.
  - No generic operation ledger, historical read-back, transport retry or ambiguous-commit replay
    is introduced.
- Evidence to capture:
  - Constraint/trigger failure matrix, valid commit evidence, closed-row update/delete rejection and
    Operation ID binding/uniqueness assertions.

## Regression Gate

- Run the focused application and PostgreSQL tests introduced or extended for Ticket #26 under
  explicit bounds.
- Rerun Ticket #25's bounded green application and PostgreSQL commands and compare collected/passed
  totals with their accepted baseline or document legitimate additions from Ticket #26.
- Run `.\.venv\Scripts\ruff check .`, `docker compose config --quiet` and `git diff --check`.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
