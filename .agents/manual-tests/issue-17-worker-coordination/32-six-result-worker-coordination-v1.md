# Manual Test Guide: Issue #32 Six-Result Worker Coordination

## Metadata

- Feature: Issue #17 worker coordination
- Slice: #32 — complete the six-result worker coordination contract
- Authoritative specification: GitHub Issue #32 and `docs/design/issue-17-worker-coordination.md`
- Guide revision: issue-32-v1
- Approved by: user
- Approved at: 2026-08-09T20:34:47+07:00

## Prerequisites

- Environment: local PostgreSQL from the configured Knora Docker environment and the isolated
  Issue #32 worktree.
- Data and state: migrations upgraded through `20260809_0013`; `PYTHONPATH` set to this
  worktree's `backend/src`. The shared virtual environment is
  `D:\Developer\Projects\knora-agent\.venv`.
- Credentials and permissions: local repository, Docker, and GitHub access.

## Locked Test Cases

### TC-01: Six tagged `run_once` results through their approved seams

- Purpose: prove that no eligible job, generic fake success, typed supersession, retry scheduled,
  terminal failure, and lease loss remain disjoint authoritative outcomes; verify the fake typed
  success path and recovery/capacity behavior without production success persistence.
- Steps:
  1. From this worktree, run:
     `$env:PYTHONPATH = "$PWD\backend\src"; & 'D:\Developer\Projects\knora-agent\.venv\Scripts\python.exe' -m pytest backend/test/ingestion/test_job_processing.py backend/test/adapters/postgres/test_ingestion_job_coordination.py -q`.
- Expected results:
  - All focused tests pass.
  - Application tests cover all six tagged outcomes and retain the authoritative
    `next_attempt_at` on retry.
  - PostgreSQL tests cover stale-target supersession, valid and invalid replacement identifiers,
    fencing precedence, operation replay, acknowledgement-loss reconciliation, immutable attempt
    history, and the explicit Issue #18 generic-success boundary.
- Evidence to capture:
  - Complete focused pytest output with pass count.

### TC-02: Migration and repository regression gates

- Purpose: prove the new terminal outcome schema is the active migration head and the Issue #32
  slice does not regress the repository.
- Steps:
  1. From `backend/`, run:
     `$env:PYTHONPATH = "$PWD\src"; & 'D:\Developer\Projects\knora-agent\.venv\Scripts\python.exe' -m alembic -c alembic.ini current`.
  2. From the worktree root, run:
     `& 'D:\Developer\Projects\knora-agent\.venv\Scripts\python.exe' -m ruff check .`.
  3. Run:
     `$env:PYTHONPATH = "$PWD\backend\src"; & 'D:\Developer\Projects\knora-agent\.venv\Scripts\python.exe' -m pytest`.
  4. Run `docker compose config --quiet`.
- Expected results:
  - Alembic reports `20260809_0013 (head)`.
  - Ruff reports no violations.
  - The complete suite passes with only the repository's existing skipped tests and deprecation
    warnings.
  - Docker Compose configuration exits successfully.
- Evidence to capture:
  - Alembic current output, Ruff output, complete pytest output, and Compose exit status.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
