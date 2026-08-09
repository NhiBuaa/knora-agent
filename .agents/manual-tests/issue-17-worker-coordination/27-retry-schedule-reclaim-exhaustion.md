# Manual Test Guide: Retry Scheduling, Due Claim and Exhaustion

## Metadata

- Status: Approved and locked
- Feature: Issue #17 — PostgreSQL worker coordination lifecycle
- Slice: GitHub issue #27 — Schedule, reclaim, and exhaust a retryable attempt
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/27
- Approved design: `docs/design/issue-17-worker-coordination.md`
- Guide revision: `issue-27-v1`
- Approved by: Nhi (explicit human approval in Codex task)
- Approved at: 2026-08-09T13:25:44+07:00

## Prerequisites

- Environment: local checkout, repository virtual environment and bounded-ready PostgreSQL test
  service. Record commit, branch, concise dirty state, Python/pytest versions and non-secret
  PostgreSQL identity.
- Baseline: Ticket #26 Evaluation run `issue-26-20260809-queued-terminal-failure-passed` is the
  accepted predecessor. Run focused tests against a disposable/test-owned database.
- Time: PostgreSQL `clock_timestamp()` is authoritative for durable time, retry anchoring,
  eligibility and fencing. An injected fake monotonic clock is used only to demonstrate that local
  elapsed-time progression does not make a retry due. No test uses real sleep.
- Randomness: tests use deterministic `RandomSource` sequences and inspect consumption exactly;
  production random seeding is not a test concern.
- Scope: ownerless expiry recovery, heartbeat, timeout/supervision, bounded runner, success,
  superseded and ambiguous-commit reconciliation remain absent.

## Locked Test Cases

### TC-01: Classify observed facts only through Failure Cause V1 and Retry Policy V1

- Purpose: prove observed handler facts do not encode retryability and V1 policy is the sole
  decision owner.
- Steps:
  1. Map every actual V1 handler failure kind present in the Ticket #27 codebase through the pure,
     versioned Cause Mapping V1.
  2. Evaluate retryable and deterministic canonical causes at attempt counts 1 through 4 with a
     deterministic random sequence.
  3. Inspect policy decision, exact duration window and random-sample count.
- Expected results:
  - Mapping preserves a closed canonical cause/version without arbitrary/dynamic string fallback;
    it does not sanitize exception text or derive retryability.
  - Raw provider/SQL exception text never becomes a cause enum or persisted `safe_code`.
    `safe_code` remains separate bounded/allowlisted outcome metadata.
  - Retryable causes after attempts 1, 2 and 3 select exactly one full-jitter delay in inclusive
    windows `[0,5s]`, `[0,30s]` and `[0,120s]`; zero delay is valid.
  - Attempt 4 retryable cause returns `RetryExhausted` without sampling. A deterministic cause at
    any attempt returns `FailTerminal`, including attempt 4, without sampling.
- Evidence to capture:
  - Cause-mapping table, policy decision table, integer-duration bounds and random-source call
    counts.

### TC-02: Atomically schedule a retry and retain immutable audit

- Purpose: prove explicit `processing -> retry_scheduled` persistence without generic transition
  APIs or policy inside the store.
- Steps:
  1. Claim one queued job and supply a coordinator-computed typed `ScheduleRetry` decision with
     policy/jitter metadata, deterministic relative delay and typed Transition Operation ID.
  2. Invoke the explicit fenced `schedule_retry` operation.
  3. Reload job projection and closed attempt history.
- Expected results:
  - A short fenced transaction closes exactly the current attempt, clears current ownership and
    changes only the job projection to `retry_scheduled`.
  - Store samples one fresh PostgreSQL time after locks and anchors
    `next_attempt_at = fresh_db_now + RetryDelay`; it does not receive authoritative application
    wall time, reroll jitter or choose retryability/exhaustion.
  - The exact persisted relationship proves one transition anchor:
    `next_attempt_at - attempt.closed_at == chosen RetryDelay`, or an equivalent authoritative
    persisted anchor relationship.
  - History retains observed canonical cause/version, policy version/result, jitter version,
    selected upper bound, chosen exact delay, resulting database-anchored schedule and bound
    Transition Operation ID/request identity.
  - No generic `execute`, `transition` or `update_status` API is introduced. ACK-loss replay,
    operation-ID read-back and ambiguous-commit reconciliation remain out of scope.
- Evidence to capture:
  - Before/after projection, closed attempt audit fields, fencing predicate/result and DB-time
    anchoring relationship.

### TC-03: Prove retry eligibility with independent valid positive- and zero-delay schedules

- Purpose: prove retry eligibility remains in the database clock domain.
- Steps:
  1. Case A: schedule a retry using a deterministic positive delay (for example 5 seconds). Attempt
     normal claim immediately, then advance only a fake monotonic clock and attempt normal claim
     again.
  2. Case B: schedule a retry using deterministic zero delay. In a separate subsequent
     `run_once()`/claim transaction, attempt normal claim without real sleep.
  3. Inspect every projection/history row without raw-updating any durable retry timestamp.
- Expected results:
  - The positive database-anchored schedule is not due immediately; local monotonic advancement
    does not make it eligible.
  - The zero-delay database-anchored schedule is immediately due only to the separate subsequent
    claim transaction, without mutating persisted retry history or using real sleep.
  - Each valid due claim increments `attempt_count` and
    `lease_version` once, inserts the matching next open attempt and never selects a processing row.
  - No direct reclaim path exists for processing rows.
- Evidence to capture:
  - Independent-clock trace, positive-delay no-claim results, zero-delay separate-claim result,
    durable audit rows and job/attempt counters.

### TC-04: Exhaust retryable work on the fourth counted attempt

- Purpose: prove budget enforcement and explicit terminal exhaustion transition.
- Steps:
  1. Drive one retryable job through three successful schedule-and-due-claim cycles.
  2. Return the same retryable observed failure from attempt 4.
  3. Inspect the final job and all attempt rows, then attempt another claim.
- Expected results:
  - Attempts 1–3 record their distinct V1 retry audit; attempt 4 records the observed canonical
    cause plus `RetryExhausted` policy result and finalizes through explicit terminal failure.
  - Public job state is `failed` with `failure_reason=retry_exhausted`, ownership and
    `next_attempt_at` are clear, and no fifth attempt exists or can be claimed.
  - `retry_scheduled` is valid only while `attempt_count < max_attempts`; the fourth retryable
    failure creates neither a transient nor durable retry-scheduled projection.
  - Exhaustion performs no random sample and does not overwrite observed cause with policy result.
- Evidence to capture:
  - Ordered attempt-history projection, policy/RNG trace, final job projection and no-fifth-claim
    assertion.

### TC-05: Keep deterministic failure terminal at every count

- Purpose: prevent attempt count from reclassifying a non-retryable observed fact as exhaustion.
- Steps:
  1. Run a non-retryable handler failure at attempt 1 and separately at attempt 4.
  2. Inspect the policy result, public failure reason and random-source consumption.
- Expected results:
  - Both calls use `FailTerminal`, not `RetryExhausted`; no jitter sample is consumed.
  - Public terminal reason remains the deterministic mapped reason, and history retains the actual
    cause/version and safe code.
- Evidence to capture:
  - Attempt-count/result matrix, public metadata and random-source call counts.

### TC-06: Report authoritative retry/exhaustion outcomes through `run_once()`

- Purpose: keep the deep worker seam observable without adding continuous-loop behavior.
- Steps:
  1. Use deterministic fake store/handler/random/clock inputs to run retry scheduling, due retry
     claim, exhausted terminal, deterministic terminal and fenced-finalization cases through
     `ProcessIngestionJob.run_once(worker_id)`.
  2. Inspect tagged result and operation sequence for each invocation.
- Expected results:
  - A successful retry schedule returns `RETRY_SCHEDULED`; exhausted or deterministic terminal
    failure returns `FAILED_TERMINAL`; existing fenced finalization returns `LEASE_LOST`; no
    invocation runs more than one handler attempt.
  - A zero delay still returns after durable scheduling; a later invocation owns the due claim.
  - Ordinary persistence failure is never fabricated into a successful lifecycle result.
    Commit-ACK-loss/idempotent ambiguous-commit reconciliation is not implemented or acceptance
    tested in this ticket.
- Evidence to capture:
  - Tagged-result matrix, fake store operation trace, random count and per-invocation handler count.

## Regression Gate

- Run focused `job_processing`, retry policy and PostgreSQL coordination tests under explicit
  bounds, including migration tests if retry schema changes.
- Rerun the bounded Ticket #25 application/PostgreSQL gate and document test-total changes caused
  by Ticket #27.
- Run `.\.venv\Scripts\ruff check .`, `docker compose config --quiet` and `git diff --check`.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
