# Manual Test Guide: Expired Attempt Recovery Through Scheduled Retry

## Metadata

- Status: Approved and locked
- Feature: Issue #17 — PostgreSQL worker coordination lifecycle
- Slice: GitHub issue #28 — Recover an expired attempt through scheduled retry
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/28
- Approved design: `docs/design/issue-17-worker-coordination.md`
- Guide revision: `issue-28-v1`
- Approved by: Nhi (explicit human approval in Codex task)
- Approved at: 2026-08-09T14:28:29+07:00

## Prerequisites

- Environment: isolated `codex/issue-28-expired-recovery` worktree from checkpoint `06ec3b4`,
  repository virtual environment, and the local PostgreSQL test service.
- Baseline: Ticket #27 Evaluation run
  `issue-27-20260809-retry-schedule-reclaim-exhaustion-passed` is the accepted predecessor.
- Time: PostgreSQL `clock_timestamp()` owns observation, expiry, recovery fencing and retry
  anchoring. Tests use deterministic database state and no real sleep.
- Randomness: deterministic `RandomSource` inputs prove exact policy/RNG behavior; production
  random seeding is not under test.
- Scope: active-owner heartbeat scheduling, timeout/supervision, bounded runner, success,
  supersession and ambiguous-commit reconciliation remain out of scope.

## Locked Test Cases

### TC-01: Recover before claiming or executing new work

- Purpose: prove `ProcessIngestionJob.run_once()` treats a successful expired-attempt recovery as
  its one operation for the invocation.
- Steps:
  1. Run the deterministic application seam with one immutable expired-attempt observation and a
     retryable `LEASE_EXPIRED` policy decision.
  2. Run the stale-observation and final-count expiry variants.
  3. Inspect the tagged result, store trace, handler input list and random-source calls.
- Expected results:
  - Applied recovery returns `RETRY_SCHEDULED` or `FAILED_TERMINAL` for exhaustion, with safe code
    `lease_expired`.
  - Applied recovery neither claims a new attempt nor invokes the Work Handler.
  - A stale observation falls through once to normal claim; a final counted expiry exhausts without
    drawing jitter.
- Evidence to capture:
  - Focused application test output and assertion trace for result, claim, handler and RNG counts.

### TC-02: Observe and atomically schedule recovery

- Purpose: prove ownerless expiry follows one optimistic observe/apply protocol rather than direct
  reclaim.
- Steps:
  1. Claim one test-owned job, make its current lease expired with PostgreSQL-owned time, then call
     `observe_expired_attempt`.
  2. Apply a zero-delay typed `ScheduleRetry` using the observation and canonical
     `LEASE_EXPIRED` failure.
  3. Reload the job and attempt row, then run a separate normal claim transaction.
- Expected results:
  - Observation contains job/attempt/worker/lease identity, attempt budget and exact lease expiry;
    it grants no processing ownership.
  - Apply closes the observed attempt and atomically writes `retry_scheduled`, complete retry audit
    and observed `lease_expired` closure cause.
  - Even zero delay requires the separate subsequent claim transaction, which creates attempt 2;
    recovery never directly claims it.
- Evidence to capture:
  - PostgreSQL focused-test output and before/after job/attempt audit assertions.

### TC-03: Reject stale or current observations deterministically

- Purpose: prove exact observed expiry protects heartbeats and concurrent recovery winners.
- Steps:
  1. Observe an expired attempt, renew its recorded lease expiry, then apply the old observation.
  2. Apply a current (not expired) observation.
  3. Submit the same expired observation through two concurrent recovery calls.
- Expected results:
  - Renewed lease returns `STALE_OBSERVATION`; current lease returns `NOT_EXPIRED`; neither closes
    the attempt or changes the job projection.
  - Concurrent recovery has exactly one `RecoveryRetryScheduled` winner and one
    `StaleObservation` result, leaving one closed attempt history row.
- Evidence to capture:
  - Result matrix and reloaded durable job/attempt state from the PostgreSQL tests.

### TC-04: Exhaust the final expired attempt

- Purpose: prove the recovery path honors the counted attempt budget and remains auditable.
- Steps:
  1. Create a test-owned processing job on its final allowed attempt and make the lease expired.
  2. Observe it and apply the policy's typed `RetryExhausted` decision.
  3. Reload durable state and try another normal claim.
- Expected results:
  - Job is atomically `failed` with `failure_reason=retry_exhausted`; ownership and schedule clear.
  - History records observed `lease_expired` separately as closure/failure cause, plus V1 policy
    result `retry_exhausted`.
  - No second/new attempt is claimable.
- Evidence to capture:
  - Final projection, ordered history assertions and no-claim result.

### TC-05: Reject an invalid recovery decision without mutation

- Purpose: ensure recovery accepts only `ScheduleRetry` or `RetryExhausted` from Retry Policy V1.
- Steps:
  1. Observe an expired test attempt.
  2. Submit a non-recovery `FailTerminal` decision to the explicit recovery operation.
  3. Reload the job and open attempt.
- Expected results:
  - The store raises `CoordinationInvariantError` before changing durable lifecycle state.
  - The job remains `processing` and its attempt remains open.
- Evidence to capture:
  - Focused test exception assertion and post-operation state assertions.

## Regression Gate

- Run `backend/test/ingestion/test_job_processing.py` and
  `backend/test/adapters/postgres/test_ingestion_job_coordination.py` first.
- Run the bounded relevant suite: `backend/test/ingestion backend/test/adapters/postgres -q`.
- Run `ruff check .`, `docker compose config --quiet` and `git diff --check`.
- The repository-wide pytest command remains bounded-inconclusive under Ticket #25; do not replace
  the focused and relevant gates with an unbounded run.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
