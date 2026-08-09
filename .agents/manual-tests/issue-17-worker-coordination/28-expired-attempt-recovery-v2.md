# Manual Test Guide: Expired Attempt Recovery After Heartbeat Integration

## Metadata

- Status: Approved and locked
- Feature: Issue #17 — PostgreSQL worker coordination lifecycle
- Slice: GitHub issue #28 — Expired-attempt recovery, rebased onto completed Issue #29
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/28
- Approved design: `docs/design/issue-17-worker-coordination.md` and ADR 0005
- Guide revision: `issue-28-v2`
- Approved by: Nhi (explicit human approval in Codex task)
- Approved at: 2026-08-09T18:21:39+07:00

## Prerequisites

- Environment: `codex/issue-28-expired-recovery` rebased on local `main` commit `8e6bdcc`, with
  the committed `20260809_0011_attempt_heartbeat` migration installed in the PostgreSQL test
  service.
- Baseline: Issue #28 Evaluation `issue-28-20260809-expired-attempt-recovery-passed` remains an
  immutable record for the pre-rebase snapshot; it is not evidence for this guide revision.
- Time: PostgreSQL `clock_timestamp()` owns durable expiry, heartbeat fencing and recovery apply.
  Tests use deterministic fixtures and no real sleep.
- Scope: this guide verifies Issue #28 recovery integrated with the completed heartbeat schema. It
  does not re-accept timeout/detach execution, success, supersession or ambiguous reconciliation.

## Locked Test Cases

### TC-01: Recover before runner reservation, claim or handler execution

- Purpose: ensure recovery remains the first `run_once()` action after Issue #29 adds bounded
  runner admission.
- Steps:
  1. Run successful recovery, stale-observation fallback and final-attempt exhaustion through the
     deterministic application seam with an available runner.
  2. Inspect result, runner/claim trace, handler inputs and policy RNG calls.
- Expected results:
  - Applied recovery returns retry scheduled or retry exhausted without reserving work capacity,
    claiming a replacement or calling the handler.
  - Stale observation falls through once; its later normal attempt reserves capacity normally.
  - Final expiry returns `failed/retry_exhausted` without jitter sampling.
- Evidence to capture:
  - Focused `test_job_processing.py` output and operation assertions.

### TC-02: Observe and atomically schedule one ownerless expiry

- Purpose: prove optimistic recovery remains a separate, durable operation.
- Steps:
  1. Create one test-owned expired processing attempt and obtain its PostgreSQL observation.
  2. Apply typed `ScheduleRetry` with zero delay and reload job/history state.
  3. Run a separate normal claim transaction.
- Expected results:
  - History closes with `lease_expired`, V1 retry audit and `retry_scheduled` projection atomically.
  - The separate later claim creates attempt 2; recovery never directly claims it.
- Evidence to capture:
  - PostgreSQL test output and durable job/attempt assertions.

### TC-03: Preserve immutable history across heartbeat/recovery race

- Purpose: prove a real heartbeat only updates the mutable job lease and makes the prior recovery
  observation stale.
- Steps:
  1. Claim a job and retain its immutable initial lease expiry in an optimistic observation fixture.
  2. Call the public PostgreSQL `heartbeat` operation with the current fencing token.
  3. Apply the earlier observation and reload the job/attempt; separately run concurrent recovery
     contenders for the same expired observation.
- Expected results:
  - Heartbeat returns `HeartbeatApplied`, preserves lease generation and leaves
    `initial_lease_expires_at` unchanged while updating only the job lease projection.
  - Recovery returns `StaleObservation`, leaves the attempt open and does not overwrite the
    renewed lease.
  - Concurrent recovery has exactly one applied winner and one stale loser.
- Evidence to capture:
  - Heartbeat and recovery result matrix, job lease fields and immutable attempt-history assertion.

### TC-04: Keep NotExpired, exhaustion and invalid decision disjoint

- Purpose: prove recovery boundaries do not create a replacement attempt or a fabricated result.
- Steps:
  1. Apply a current observation, a final expired observation and an invalid `FailTerminal`
     decision in isolated test-owned jobs.
  2. Reload durable rows and attempt an additional claim after exhaustion.
- Expected results:
  - Current observation returns `NotExpired` without mutation.
  - Final expiry becomes `failed/retry_exhausted` with no additional claimable attempt.
  - Invalid decision raises before lifecycle mutation.
- Evidence to capture:
  - Tagged result matrix, final projection/history and no-claim assertion.

## Regression Gate

- Run `backend/test/ingestion/test_job_processing.py -q` and
  `backend/test/adapters/postgres/test_ingestion_job_coordination.py -q`.
- Run `backend/test/adapters/postgres/test_ingestion_job_coordination_migration.py -q`.
- Run the bounded relevant suite: `backend/test/ingestion backend/test/adapters/postgres -q`.
- Run `ruff check .`, `docker compose config --quiet` and `git diff --check`.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
