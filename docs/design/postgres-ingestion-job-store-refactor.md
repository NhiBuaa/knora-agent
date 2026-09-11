# PostgreSQL Ingestion Job Store Refactor

Status: Proposed for approval  
Source: [Issue #85](https://github.com/NhiBuaa/knora-agent/issues/85)  
Scope: Behavior-preserving decomposition of `PostgresIngestionJobStore`

## Decision

Keep `PostgresIngestionJobStore` at
`backend/src/knora/adapters/postgres/ingestion_job_store.py` as the one compatible PostgreSQL
adapter visible to application composition, callers, and tests. Move its implementation into three
private, transaction-family modules beneath `knora.adapters.postgres.ingestion_jobs`:

```text
backend/src/knora/adapters/postgres/
├── ingestion_job_store.py          # compatible facade and composition root
└── ingestion_jobs/
    ├── __init__.py                 # no public re-exports
    ├── lifecycle.py                # Object Lifecycle persistence
    ├── submission.py               # submission, status, reprocess, audit persistence
    └── coordination.py             # attempt coordination and fenced finalization
```

The new package is an implementation detail of the existing adapter. Application modules keep
depending on their current consumer-owned ports; no application port gains an ORM row, session,
connection, transaction, generic status update, or PostgreSQL clock parameter.

This is a full-path refactor, not fast-track work. The source adapter has several independently
changing transaction families, and its current 3,792-line implementation combines them even
though their application consumers and adapter test seams are distinct.

## Context and evidence

`PostgresIngestionJobStore` currently owns all of the following:

| Responsibility family | Current location | Existing application owner | Primary adapter evidence |
|---|---|---|---|
| Object Lifecycle work, delete preparation, hard deletion, and retention revalidation | `ingestion_job_store.py`, roughly lines 116-997 | `knora.ingestion.object_lifecycle` | `test_object_lifecycle_store.py`, `test_original_source_hard_delete.py`, `test_object_reconciliation.py` |
| PDF submission, status projection, reprocess/replay/audit, and immutable configuration persistence | roughly lines 998-1581 and 3499-3792 | `knora.ingestion.jobs.PdfSubmissionStore` | `test_ingestion_jobs.py`, `test_issue_19_public_postgres.py`, `test_issue_19_acceptance.py` |
| Expiry observation/recovery, claim, heartbeat, retry, operation replay, and terminal/fenced PDF finalization | roughly lines 1582-3498 | `knora.ingestion.job_processing.IngestionJobCoordinationStore` | `test_ingestion_job_coordination.py`, `test_pdf_derivation_finalization.py`, `test_issue_18_postgres_acceptance_harness.py` |

The Milestone 2 module seams explicitly retain `ingestion_job_store.py` as the PostgreSQL
adapter while identifying independent consumer-owned ports. ADR 0001 and the Architecture
Standard require operation-ID replay/reconciliation, fresh PostgreSQL authoritative time,
transaction-shaped operations, lease fencing, and atomic derivation/activation terminalization.
The source layout obscures these ownership boundaries; the required behavior itself must not
change.

## Goals

- Improve locality: a change to one persistence family should primarily affect one module and its
  matching adapter tests.
- Preserve the current compatible adapter and all public application-port behavior.
- Keep each transaction family deep: callers state one typed operation while the implementation
  hides locks, authoritative time, replay checks, constraints, and persistence details.
- Make transaction participation explicit only inside the private adapter implementation where one
  existing atomic transaction already spans two families.
- Make the existing test seams map directly to implementation ownership without introducing new
  application seams.

## Non-goals

- No schema, migration, table-registry, lifecycle state-machine, retry-policy, queue, scheduler,
  HTTP-contract, or configuration change.
- No move or split of `knora.adapters.postgres.tables`; the Milestone 2 design explicitly keeps it
  shared unless a separately demonstrated safety problem warrants a new decision.
- No new repository, generic persistence, `helpers`, `utils`, `common`, or generic transaction
  package.
- No change to `PdfSubmissionStore`, `IngestionJobCoordinationStore`,
  `ObjectLifecycleMaintenance`, `OperationalMetricsStore`, or any application type.
- No new public import path for internal persistence modules and no change to the construction
  signature `PostgresIngestionJobStore(session_factory)`.

## Compatibility contract

The facade keeps its existing import path, constructor, public methods, return types, error
behavior, and transaction semantics. In particular, it continues to satisfy the existing
structural application ports through these method groups:

| Public group | Contract that remains unchanged |
|---|---|
| PDF submission/status/reprocess | Workspace authorization, object-reference check, idempotency/replay, submission result, public status projection, reprocess context/replay/commit/audit |
| Worker coordination | Expiry observation/recovery, atomic claim, heartbeat, retry scheduling, success/superseded/terminal finalization, typed fenced/invalid/indeterminate results |
| Object Lifecycle | enqueue, claim, delete preparation/revalidation, complete/suppress/fail, reconciliation, and Original Source Object hard-delete capability operations |

Callers must not import `ingestion_jobs.*`. `main.py` continues to construct one facade and passes
that object into `IngestionJobs`, `ProcessIngestionJob`, and Object Lifecycle composition exactly
as it does now. Existing tests instantiate the same facade. Test-only subclasses that override
`_database_now` remain valid.

## Target modules and their internal interfaces

### Facade: `ingestion_job_store.py`

The facade is the external seam. It owns:

- the existing `PostgresIngestionJobStore` class and constructor;
- the stable `_database_now(session)` hook used by authoritative-time tests;
- construction of the three private implementations with `session_factory` and a bound
  `database_now` callable; and
- typed delegation for the existing public methods.

The facade does not open domain transactions after the refactor. It must not grow policy,
SQLAlchemy query construction, or new behavior while delegating.

Passing `self._database_now` at construction deliberately preserves dynamic dispatch for existing
test subclasses such as `AdvancingFinalizationClockStore`. Internal modules therefore receive
authoritative database time from the same hook rather than calling application wall time or
duplicating a clock implementation.

### Object Lifecycle persistence: `ingestion_jobs/lifecycle.py`

This module owns the lifecycle work and Original Source Object retention implementation:

- lifecycle enqueue, claim, expiry recovery, prepare/revalidate delete, completion, suppression,
  failure, and orphan-reconciliation persistence;
- hard-delete preparation/completion/revalidation for Original Source Objects;
- object/lifecycle claim ownership checks, retention checks, trace-reference lookup, and the
  bounded JSON identifier traversal used by retention validation; and
- the one internal operation that inserts terminal-cleanup work into a transaction already owned by
  coordination finalization.

Most lifecycle operations open and commit their own short transaction. The sole exception is an
explicitly named internal operation such as
`enqueue_terminal_cleanup_in_transaction(session, job, source_object)`. It accepts the already
locked SQLAlchemy `Session` and performs no commit. This is not an application interface: it is
the private implementation mechanism that preserves the existing atomic transaction that closes a
Job/Attempt and creates deduplicated lifecycle work together. A lifecycle method must never open a
second transaction for that insert.

### Submission/read persistence: `ingestion_jobs/submission.py`

This module owns all `PdfSubmissionStore` implementation behavior:

- Workspace authorization and Original Source Object reference checks;
- job status projection and safe serving-state resolution;
- reprocess context, replay, atomic creation/reuse, and read-only audit projection;
- PDF submission idempotency, Document/Document Version/Original Source Object persistence,
  current-version updates, job-generation deduplication, and response projection; and
- immutable Chunking and Embedding Configuration get-or-create validation.

Each mutating operation retains its current single transaction and current exception translation.
The module does not parse PDFs, read ObjectStore contents, select mutable configuration in workers,
or return a session/ORM row to application code.

### Coordination/finalization persistence: `ingestion_jobs/coordination.py`

This module owns the `IngestionJobCoordinationStore` implementation:

- immutable expired-attempt observation and conditional recovery;
- atomic eligible-job claim and open-attempt creation;
- heartbeat ownership/lease renewal;
- retry scheduling and terminal failure/superseded finalization;
- fenced PDF success finalization, including complete derivation persistence, active-pointer
  compare-and-swap, terminal job/attempt updates, and in-transaction lifecycle-work enqueue;
- operation-ID request fingerprints, replay reads, authoritative read-back after ambiguous
  persistence failure, and incompatible-operation invariants; and
- private token/attempt ownership predicates, fresh database-time sampling, and transition-input
  validation.

The coordination module receives the lifecycle implementation only for the explicit
in-transaction terminal-cleanup operation. It owns the finalization transaction, row locks,
fresh-time sample, and commit. The lifecycle module must not become a coordinator and must not
choose retry policy, fencing outcomes, or lifecycle state for an Ingestion Job.

`_FinalizationFenceLost` moves with finalization because it exists solely to roll back tentative
PDF derivation state when the final lease guard fails. It remains private.

## Transaction and time ownership

| Operation family | Transaction owner after refactor | PostgreSQL time source | Atomicity that must remain true |
|---|---|---|---|
| Submission/reprocess | submission module | bound facade `_database_now` where currently used | idempotency/audit/job generation and associated source/version/configuration writes stay in their existing transaction |
| Claim/heartbeat/recovery/retry | coordination module | fresh sample after locks through bound facade hook | current Job projection and open Attempt transition together; replay cannot rerun policy or business work |
| Success/superseded/terminal finalization | coordination module | fresh sample after locks through bound facade hook | fenced attempt closure, Job terminal state, derivation/activation CAS where applicable, and terminal lifecycle-work insert stay one transaction |
| Standalone lifecycle operations | lifecycle module | bound facade hook | work/attempt state and delete-preparation capability are committed under lifecycle fencing rules |
| Original Source hard deletion | lifecycle module | bound facade hook | retention/Workspace/reference revalidation occurs under the existing delete-preparation ownership rules |

No module may substitute `datetime.now()`, transaction-start time, or a caller-provided wall clock
for PostgreSQL authoritative time where the existing code currently samples database time. The
same operation IDs and request fingerprints continue through retries and authoritative read-back.

## Incremental implementation strategy

The final target is reached through five coherent stages. A stage is not authorization to change
code; each is implemented only after baseline evidence and the governing workflow approve it.

### Stage 0: baseline and characterization

- Verify the checkout is clean and capture the exact baseline commit.
- Run the repository-required verification suite before any structural change.
- Run the focused adapter suites listed below to establish the relevant observable behavior and
  subclass clock-hook coverage.
- Stop and classify any baseline failure as pre-existing. Do not repair it inside this refactor.

### Stage 1: establish the private package and extract lifecycle persistence

- Create the private package and move the Object Lifecycle/hard-delete implementation without
  changing facade method signatures or method results.
- Leave public facade methods as typed delegates to one lifecycle implementation instance.
- Preserve all lifecycle-owned transactions, stale/fenced results, retention predicates, and
  Object Lifecycle Work independence from Ingestion Job outcomes.
- Add only structural tests necessary to show delegation preserves the clock hook; existing
  lifecycle contract tests remain the main evidence.

### Stage 2: extract submission and read persistence

- Move submission/status/reprocess/audit/configuration behavior into the submission module.
- Preserve `PdfSubmissionStore` behavior, 24-hour idempotency semantics, public status/result
  projections, and safe Workspace-scoped lookup behavior.
- Keep object-storage I/O in the application layer and preserve existing database transaction
  boundaries and error codes.

### Stage 3: extract coordination and finalization persistence

- Move recovery, claim, heartbeat, retry, replay/reconciliation, and all finalization behavior
  into the coordination module.
- Route terminal cleanup through the lifecycle module's explicitly in-transaction operation.
- Preserve the current authoritative-time hook for the finalization test harness and verify that
  stale/fenced/expired transitions remain disjoint typed results.
- Do not move policy from `ProcessIngestionJob`, PDF derivation work from its handler, or SQL
  details into application code.

### Stage 4: facade reduction and cross-family verification

- Reduce the facade to construction, stable time hook, and typed delegation only.
- Confirm no production caller imports an internal module and no internal collaborator is exposed
  through an application port.
- Run all focused suites and the repository-required complete verification commands.

### Stage 5: pinned-diff review

- Review the final diff against this design and Issue #85.
- Remediate only review findings that preserve the approved scope; any behavioral discrepancy
  returns to the governing workflow for a new decision.

## Verification map

| Invariant or seam | Stages | Evidence and command |
|---|---|---|
| Object Lifecycle fencing, retention, delete preparation, and hard-delete protection | 0, 1, 4 | `python -m pytest backend/test/adapters/postgres/test_object_lifecycle_store.py backend/test/adapters/postgres/test_original_source_hard_delete.py backend/test/adapters/postgres/test_object_reconciliation.py` |
| Submission idempotency, public status, reprocess/audit, and serving projection | 0, 2, 4 | `python -m pytest backend/test/adapters/postgres/test_ingestion_jobs.py backend/test/adapters/postgres/test_issue_19_public_postgres.py backend/test/adapters/postgres/test_issue_19_acceptance.py` |
| Claim, fencing, recovery, retry, operation replay, and authoritative time | 0, 3, 4 | `python -m pytest backend/test/adapters/postgres/test_ingestion_job_coordination.py backend/test/adapters/postgres/test_issue_18_postgres_acceptance_harness.py` |
| PDF derivation/activation terminal atomicity | 0, 3, 4 | `python -m pytest backend/test/adapters/postgres/test_pdf_derivation_finalization.py` |
| Complete repository regression surface | 0, 4 | `./.venv/Scripts/python -m pytest`; `./.venv/Scripts/ruff check .`; `docker compose config --quiet` from repository root |

The focused commands use the virtual-environment Python in actual execution. The shorter form in
the table identifies test intent only; the repository-required commands remain authoritative.

## Data, migration, and recovery

No database schema, migration, data backfill, mixed-version deployment, or configuration change is
part of this decision. The refactor moves Python implementation ownership only.

The transactional recovery contract remains unchanged:

- operation replay returns durable results rather than rerunning work;
- ambiguous coordination persistence is reconciled authoritatively or remains indeterminate;
- a stale/expired worker cannot publish a result;
- failed cleanup cannot reverse an already-durable Ingestion Job outcome; and
- an external ObjectStore delete remains reconciled through `head`, not through a changed Job
  outcome.

## Rollback

Each stage is source-only. If a stage's focused guardrail fails or behavior drifts, revert only
that stage's source/test commit and restore the preceding compatible facade delegation. There is no
data rollback and no migration reversal. Do not proceed to a later stage with an unexplained
baseline or post-stage guardrail failure.

## Risks and replan triggers

| Risk or assumption | Mitigation | Replan trigger |
|---|---|---|
| An internal helper accidentally opens a second transaction during finalization | The only cross-family operation is explicitly named as in-transaction and performs no commit | Any test or review evidence shows lifecycle work can commit independently of the terminal Job/Attempt transition |
| Facade delegation breaks subclass-controlled database time | Bind `self._database_now` into each collaborator and retain the facade hook | Issue #18 harness no longer observes its injected finalization time sequence |
| Moving code changes operation-ID replay or typed result distinctions | Move each coordination family with its replay/read-back helpers and retain focused tests | A replay reruns policy/work, or a stale/not-expired/fenced outcome changes category |
| Private package becomes an accidental second public seam | No re-exports; application imports and construction remain unchanged | Production code outside the PostgreSQL adapter imports `ingestion_jobs.*` |
| Existing tests couple to private method placement rather than observable behavior | Retain the explicit database-time hook; otherwise update tests only to cross the compatible facade | A required test needs direct access to an internal SQLAlchemy collaborator |
| Scope expands to schema or lifecycle semantics | Pin the non-goals and stage gate | A change requires migration, new state, changed port signature, or changed HTTP behavior |

## Consequences for domain documentation

No Current World Model or ADR update is required. This decision does not change canonical concepts,
relationships, state machines, retention rules, or architecture policy; it only improves locality
inside the existing PostgreSQL adapter implementation. Any discovery that requires a changed
transaction contract, lifecycle rule, or public port is a replan trigger and must be routed to the
appropriate governance workflow.

## Approval requested

Approval of this artifact authorizes `to-plan` to treat it as the authoritative Design for an
immutable implementation-plan revision. It does not authorize worktree creation, code changes,
test changes, commits, issue decomposition, merge, or deployment.
