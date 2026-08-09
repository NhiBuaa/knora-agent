# Manual Test Guide: Issue #29 Attempt Supervision

## Metadata

- Feature: Issue #17 worker coordination
- Slice: #29 — bounded attempt supervision
- Authoritative specification: GitHub Issue #29 and `docs/design/issue-17-worker-coordination.md`
- Guide revision: issue-29-v1
- Approved by: user
- Approved at: 2026-08-09T11:05:39Z

## Prerequisites

- Environment: local Docker PostgreSQL and the isolated Issue #29 worktree.
- Data and state: migrations upgraded through `20260809_0011`.
- Credentials and permissions: local repository and Docker access.

## Locked Test Cases

### TC-01: Bounded admission and safe runner start failure

- Purpose: capacity is reserved before claim and a post-claim start failure schedules a fenced retry.
- Steps:
  1. Run `python -m pytest backend/test/ingestion/test_job_processing.py -q`.
- Expected results:
  - Capacity exhaustion does not claim a job.
  - Start failure produces `RetryScheduled`; no attempt remains stranded in processing.
- Evidence to capture: pytest output.

### TC-02: Heartbeat and fencing supervision

- Purpose: heartbeat renews one current lease and fencing vetoes finalization.
- Steps:
  1. Run `python -m pytest backend/test/adapters/postgres/test_ingestion_job_coordination.py backend/test/ingestion/test_job_processing.py -q`.
- Expected results:
  - Lease version remains stable, history retains initial expiry, and heartbeat fencing causes logical detach.
- Evidence to capture: pytest output.

### TC-03: Deadline, detach, and late physical exit

- Purpose: equality at deadline times out; detached work retains capacity until its thread exits.
- Steps:
  1. Run `python -m pytest backend/test/adapters/execution/test_thread_attempt_runner.py backend/test/ingestion/test_job_processing.py -q`.
- Expected results:
  - Timeout cancellation/detach is non-blocking; capacity is unavailable until late exit.
- Evidence to capture: pytest output.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
