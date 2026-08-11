# Manual Test Guide: Milestone 2 regression and release gate

## Metadata

- Status: Draft — do not implement or execute until explicit human approval.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #21 — Regression and release gate
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/21
- Parent ledger: https://github.com/NhiBuaa/knora-agent/issues/14
- Guide revision: `m2-issue-21-r1`
- Baseline: local `main` at `1ac2aac7259d2dcd0faf307883aeafb471e8ac0d`
- Approved by: pending
- Approved at: pending

## Purpose and boundaries

This is a verification-only release gate. It may drive a narrowly-scoped repair when an observed
criterion fails, but it must not add new production behavior. Evidence must contain only safe IDs,
checksums, counts, timestamps, allowlisted errors and redacted logs—never credentials, raw PDF
contents, object keys, SQL text or provider payloads.

Earlier locked guides remain evidence inputs, not substitutes for this gate: #15 submission, #16
extraction, #18 derivation/activation, #19 public polling/reprocess and #20 lifecycle/metrics.
The Evaluation record must link those append-only histories and record fresh results against this
candidate.

## Prerequisites

- Clean release-candidate worktree; local PostgreSQL/pgvector and MinIO from Compose; API and worker.
- Two authorized Workspace credentials; safe PostgreSQL and metrics/alert test projections.
- Resettable Workspaces; valid, changed, malformed, encrypted, textless and boundary PDFs; fixed
  immutable configuration profiles; clean lifecycle work and metrics state per case.
- Run repository verification with `./.venv/Scripts/python -m pytest`,
  `./.venv/Scripts/ruff check .`, and `docker compose config --quiet`.

## Locked Test Cases

### TC-01: Release health and Milestone 1 compatibility

- Purpose: Issue #21 full verification and no Milestone 1 regression.
- Steps:
  1. Record candidate SHA and clean worktree.
  2. Run full pytest, Ruff and Compose config from the repository root.
  3. Run existing synchronous ingestion, question/citation/refusal, authentication and evaluation suites.
- Expected results:
  - Every required command passes; no unexpected skip, xfail or collection error masks a case.
  - Markdown/plain-text ingestion and existing cited-answer/refusal contracts remain unchanged.
- Evidence: command/selectors, pass/skip counts, candidate SHA, lint/Compose outputs and safe samples.

### TC-02: Authenticated PDF upload-to-cited-answer integration

- Purpose: prove upload -> durable Job -> worker -> polling -> active PDF cited answer.
- Steps:
  1. Upload a valid text PDF in Workspace A with a fresh scoped Idempotency-Key.
  2. Poll the Workspace-scoped Job through terminal completion while a worker processes it.
  3. Ask a PDF-specific question after success; repeat a matching submission and cross-Workspace lookup.
- Expected results:
  - Upload/polling obey public status, safe metadata, no-store and retry-hint contracts; success is
    visible only after complete activation.
  - The answer cites only active PDF evidence with version-pinned page/offset provenance and
    backward-compatible line fields; duplicate and tenant-isolation behavior is correct.
- Evidence: redacted HTTP sequence, worker-stage trace, current/active/served IDs, citation and 404 result.

### TC-03: PostgreSQL lifecycle, concurrency and atomicity matrix

- Purpose: prove #17/#18/#19 durable coordination obligations.
- Steps:
  1. Run deterministic PostgreSQL/integration cases for request/document/derivation deduplication,
     atomic claim, heartbeat, stale-worker fencing, expiry recovery, retries/exhaustion and CAS supersession.
  2. Run duplicate-delivery and definite pre-commit finalization rollback cases.
  3. Inspect Job, immutable Attempt, derivation and pointer projections after each case.
- Expected results:
  - One current leased attempt at most; stale calls never mutate outcomes; recovery commits before a
    later claim; exhausted work is terminal.
  - One visible complete success only; rollback leaves no partial chain/pointer/terminal success;
    an older target is `superseded` without retry.
- Evidence: focused selectors/pass counts, safe lease/operation trace, attempts and before/after rows/pointers.

### TC-04: PDF parser rejection and resource-budget matrix

- Purpose: prove #16 deterministic extraction and every safe terminal boundary.
- Steps:
  1. Run malformed, encrypted/password-protected, unsupported and textless/insufficient-text fixtures.
  2. Run raw-size, page-count, per-page/aggregate stream, child-timeout and child-memory cases.
  3. Inspect public Job/Attempt projections and prior active knowledge after each failure.
- Expected results:
  - Each fixture returns its stable allowlisted code/reason; budget violations are
    `PDF_RESOURCE_LIMIT_EXCEEDED` with the approved safe reason evidence.
  - Child limits hold; no partial derivation activates; previous active knowledge stays served.
- Evidence: fixture category, code/reason, child-limit trace, call counts and before/after pointers.

### TC-05: Reprocess, serving state and citation contracts

- Purpose: prove #19 public lifecycle/serving separation and immutable reprocessing.
- Steps:
  1. Observe unavailable/current/previous serving in a processing/failure/newer-version sequence.
  2. Reprocess the current Document Version with `same_as_job` plus explicit source selector, then
     with `current`; cover idempotency replay/conflict, reuse and generation history.
  3. Exercise non-current and superseded paths and verify tenant-isolated polling.
- Expected results:
  - Serving state never replaces Job state; timestamps, safe errors, pointers, cache policy and
    citations follow the locked #19 contract.
  - Reprocess snapshots configuration, preserves prior Jobs and rejects non-current/cross-Workspace access.
- Evidence: safe response sequence, audit/idempotency trace, configuration IDs, links and citation fields.

### TC-06: Object lifecycle, reconciliation, metrics and alerts

- Purpose: prove #20 retention/cleanup and operational safety.
- Steps:
  1. Run success, supersession, failed upload, duplicate delivery, worker-crash and object/database-gap cases.
  2. Run cleanup/reconciliation for unreferenced and inconsistent records with age and Workspace guards.
  3. Generate queue/lease/retry/cleanup/orphan scenarios and evaluate Alert Configuration V1.
- Expected results:
  - Retained Original Source Objects are never terminal-cleaned; cleanup retry never changes Job outcome;
    deletion is idempotent/fenced and reconciliation is Workspace-scoped.
  - Required low-cardinality metrics/alerts reflect scenarios without identity labels or annotations.
- Evidence: lifecycle/attempt projections, delete/head trace, retention references, metric/alert snapshots and label audit.

### TC-07: Migration, documentation and release traceability

- Purpose: prove upgrade safety, operator usability and every parent/child criterion is evidenced.
- Steps:
  1. Upgrade clean PostgreSQL through all migrations; run focused invalid-pointer, uniqueness and
     protected-hard-delete constraint cases.
  2. Follow README/operations instructions for MinIO, API/worker startup, polling, reprocess,
     retry/lease, retention, metrics and failure diagnosis.
  3. Map every #14 and #15–#21 criterion to TC-01–TC-06 or linked accepted prior Evaluation evidence.
- Expected results:
  - Migrations and database constraints reject invalid commits atomically.
  - Documentation works from a clean environment without stale commands or secret/object-key leakage.
  - No criterion passes without candidate-specific observable evidence; only explicit human approval
    can produce a `PASSED` release Evaluation.
- Evidence: migration output, constraint class/projections, documentation transcript, criterion matrix and history links.

## Traceability matrix

| Authority | Cases |
| --- | --- |
| Issue #14 lifecycle, active-only retrieval, retries, isolation and test seams | TC-01–TC-07 |
| Issue #15 submission/idempotency | TC-02, TC-03, TC-05 |
| Issue #16 extraction/normalization/budgets | TC-04 |
| Issue #17 coordination/leases/retry | TC-03 |
| Issue #18 derivation/activation/CAS | TC-02–TC-04 |
| Issue #19 polling/reprocess/citations/serving | TC-02, TC-05 |
| Issue #20 retention/reconciliation/metrics | TC-06 |
| Issue #21 acceptance criteria | TC-01–TC-07 |

This guide becomes immutable only after explicit human approval. A semantic change requires a new
revision; execution observations belong in a separate append-only JSONL Evaluation history.
