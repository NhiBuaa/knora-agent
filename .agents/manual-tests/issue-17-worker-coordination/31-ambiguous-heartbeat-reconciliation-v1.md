# Manual Test Guide: Issue #31 Ambiguous Heartbeat Reconciliation

## Metadata

- Feature: Issue #17 worker coordination
- Slice: #31 — ambiguous heartbeat reconciliation
- Authoritative specification: GitHub Issue #31 and `docs/design/issue-17-worker-coordination.md`
- Guide revision: issue-31-v1
- Approved by: user
- Approved at: 2026-08-09T18:45:40+07:00

## Prerequisites

- Environment: local Docker PostgreSQL and the isolated Issue #31 worktree.
- Data and state: migrations upgraded through `20260809_0011`; `PYTHONPATH` set to this worktree's `backend/src` because the shared virtual environment remains editable-installed from the primary worktree.
- Credentials and permissions: local repository and Docker access.

## Locked Test Cases

### TC-01: Ambiguous heartbeat safety and reconciliation

- Purpose: prove same-ID replay/read-back does not renew a lease again; an acknowledgement loss reuses its operation ID; incompatible bindings fence or fail safely; unresolved ambiguity cancels/detaches and cannot finalize an outcome.
- Steps:
  1. Run `$env:PYTHONPATH = "$PWD\backend\src"; .\.venv\Scripts\python -m pytest backend/test/ingestion/test_job_processing.py backend/test/adapters/postgres/test_ingestion_job_coordination.py -q` from this worktree.
- Expected results:
  - All focused tests pass.
  - PostgreSQL tests cover stored-expiry replay, acknowledgement-loss reconciliation with one ID, incompatible fingerprint rejection, and deterministic fencing.
  - Supervisor tests cover completion behind the heartbeat barrier and propagation of an indeterminate heartbeat without policy/finalization.
- Evidence to capture:
  - Complete pytest output with pass count.

### TC-02: Repository regression and configuration gates

- Purpose: prove the slice does not regress the repository and its Compose configuration remains valid.
- Steps:
  1. Run `.\.venv\Scripts\python -m ruff check .`.
  2. Run `docker compose config --quiet`.
  3. Run `$env:PYTHONPATH = "$PWD\backend\src"; .\.venv\Scripts\python -m pytest`.
- Expected results:
  - Ruff reports no violations.
  - Docker Compose configuration exits successfully.
  - The complete test suite passes, with only the repository's existing skipped tests and deprecation warnings.
- Evidence to capture:
  - Ruff output, Compose exit status, and complete pytest output.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL
Evaluation records.
