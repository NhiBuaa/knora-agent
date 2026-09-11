# Implementation Plan: PostgreSQL Ingestion Job Store Refactor

Manifest: `docs/plans/postgres-ingestion-job-store-refactor--gh-85/revisions/r0001/manifest.json`

Authoritative Specification: `tracker:github/NhiBuaa/knora-agent#85`

Authoritative Design: `docs/design/postgres-ingestion-job-store-refactor.md`

## Approach

Retain `PostgresIngestionJobStore` at its current import path as the compatible external seam and
turn it into a composition facade. Its implementation is decomposed into three private deep
modules under `knora.adapters.postgres.ingestion_jobs`: Object Lifecycle persistence, PDF
submission/read persistence, and worker coordination/finalization persistence. Each module owns a
complete transaction family and hides SQLAlchemy/session details from application callers.

The sequence extracts the independent Object Lifecycle family first, then submission/read behavior,
then the high-risk coordination/finalization family. The facade retains the existing
`_database_now(session)` hook and passes its bound callable to every private module. This preserves
authoritative PostgreSQL-time behavior and existing subclass-driven finalization tests without
introducing a new application clock seam.

The only cross-module operation is explicit and private: coordination finalization asks lifecycle
persistence to enqueue terminal cleanup in the already-open finalization transaction. That method
does not begin or commit a transaction. This is necessary to retain atomic Job/Attempt terminal
state and deduplicated Object Lifecycle Work creation.

## Source decisions

| Decision | Authoritative reference | Effect on this plan |
|---|---|---|
| Preserve consumer-owned application ports and PostgreSQL adapter location | `docs/design/milestone-2-module-seams.md` | Keep the facade import path and public methods unchanged; private implementation is adapter-only. |
| Preserve fenced leases, operation replay, authoritative database time, and terminal atomicity | `docs/adr/0001-postgresql-ingestion-job-store.md`; `docs/standards/architecture.md` | Coordination owns complete transactions and replay/read-back; no lifecycle enqueue may commit separately. |
| Preserve Object Lifecycle independence and destructive-delete revalidation | `CONTEXT.md`; `docs/standards/architecture.md` | Lifecycle is its own private module and does not own Ingestion Job outcome policy. |
| Keep `tables.py` shared | `docs/design/milestone-2-module-seams.md` | No table registry move or migration is planned. |
| Approved target shape and slice order | `docs/design/postgres-ingestion-job-store-refactor.md` | Use the three private modules and five-stage sequence below. |

## Target feature structure

```text
backend/src/knora/adapters/postgres/
├── ingestion_job_store.py                  [modify]
└── ingestion_jobs/
    ├── __init__.py                         [create]
    ├── lifecycle.py                        [create]
    ├── submission.py                       [create]
    └── coordination.py                     [create]
```

| Path | Operation | Owning module | Responsibility | Plan stage | Evidence / confidence |
|---|---|---|---|---|---|
| `backend/src/knora/adapters/postgres/ingestion_job_store.py` | modify | Compatible PostgreSQL adapter facade | Stable constructor, authoritative-time hook, and typed delegation; no business persistence implementation after the final stage | 1-4 | Approved Design; current callers import this path |
| `backend/src/knora/adapters/postgres/ingestion_jobs/__init__.py` | create | Private PostgreSQL ingestion-jobs package | Declares private implementation package and exposes no alternative public adapter seam | 1 | Approved Design |
| `backend/src/knora/adapters/postgres/ingestion_jobs/lifecycle.py` | create | Object Lifecycle persistence | Lifecycle work, retention, delete preparation/completion/revalidation, hard-delete protection, and in-transaction terminal-cleanup enqueue | 1 | Existing Object Lifecycle port and adapter tests |
| `backend/src/knora/adapters/postgres/ingestion_jobs/submission.py` | create | Submission/read persistence | Submission, status, reprocess, audit, source/version/job creation, and immutable configuration validation | 2 | Existing `PdfSubmissionStore` and public projection tests |
| `backend/src/knora/adapters/postgres/ingestion_jobs/coordination.py` | create | Worker coordination/finalization persistence | Recovery, claim, heartbeat, retry, operation replay, fenced terminalization, derivation/activation persistence | 3 | Existing coordination and finalization harnesses |

No test file is planned to change solely to accommodate moved implementation. Existing adapter
contract suites are the behavior guardrails. A newly required test path is a replan trigger unless
it verifies an observable facade contract without exposing a private collaborator.

## Responsibility and seam map

| Owning module | Current responsibility | Planned responsibility change | Approved interface / seam |
|---|---|---|---|
| `PostgresIngestionJobStore` facade | All persistence families plus public adapter methods | Construction, `_database_now`, and delegation only | Existing facade import path and application structural ports |
| lifecycle persistence | Mixed into facade | Own all Object Lifecycle and Original Source Object retention persistence; accept a session only for explicit in-transaction terminal cleanup | Private adapter implementation; `ObjectLifecycleMaintenance` stays application-owned |
| submission persistence | Mixed into facade | Own all `PdfSubmissionStore` behavior and read projections | Existing `PdfSubmissionStore` seam remains unchanged |
| coordination persistence | Mixed into facade | Own all `IngestionJobCoordinationStore` behavior and finalization transaction | Existing `IngestionJobCoordinationStore` seam remains unchanged |
| `tables.py` | Shared table registry | No responsibility change | Existing shared SQLAlchemy registry |

## Implementation sequence

### Stage 0: baseline and source guardrails

- **Outcome:** The exact checkpoint commit and current observable behavior are recorded before a
  structural edit.
- **Why first:** A refactor may not absorb a pre-existing failure or assert behavior from an
  unverified baseline.
- **Uses:** Current compatible facade, focused PostgreSQL adapter suites, repository verification
  commands, and the approved Design.
- **Changes:** No source change.
- **Preserves:** The boundary between a baseline defect and refactor-caused drift.
- **Verification checkpoint:** Run the focused suites in this plan and then the repository-required
  pytest, Ruff, and Compose-config commands. Stop on a baseline failure.

### Stage 1: private package and lifecycle extraction

- **Outcome:** Lifecycle and Original Source Object persistence become local to `lifecycle.py`; the
  facade delegates the unchanged lifecycle methods.
- **Why first:** This family has bounded adapter tests and validates collaborator construction,
  facade delegation, and the bound database-time hook before the larger coordination move.
- **Uses:** Existing lifecycle typed values and `ObjectLifecycleMaintenance` behavior; shared table
  registry; bound session factory and time hook.
- **Changes:** Create the package and lifecycle module; move lifecycle transaction code and
  retention helpers; retain only facade delegates.
- **Preserves:** Workspace predicates, lifecycle fencing, retention checks, delete-preparation
  capability behavior, external-delete reconciliation, and the separation of cleanup from Job
  outcome.
- **Verification checkpoint:** Run lifecycle, hard-delete, and object-reconciliation adapter
  suites. Confirm the finalization path still invokes lifecycle enqueue only in its existing
  transaction after Stage 3, not through a second transaction.

### Stage 2: submission and read extraction

- **Outcome:** Submission, status/reprocess/audit reads, source/version/job persistence, and
  immutable configuration checks become local to `submission.py`.
- **Why next:** These methods share one application port and common short transactions but are
  independent of worker operation-ID/fencing mechanics.
- **Uses:** Existing `PdfSubmissionStore`, source object metadata, configuration value objects, and
  public projection types.
- **Changes:** Move the submission/read method family and its private result/configuration helpers;
  make facade methods typed delegates.
- **Preserves:** Idempotency binding, source/version identity, current-version update semantics,
  safe status projection, reprocess configuration selection, audit projection, error translation,
  and absence of ObjectStore I/O in persistence.
- **Verification checkpoint:** Run submission, public projection, reprocess/audit, and integrated
  acceptance suites.

### Stage 3: coordination and finalization extraction

- **Outcome:** All lease-sensitive worker coordination and PDF finalization are local to
  `coordination.py`; the facade delegates unchanged methods.
- **Why last:** This is the largest and highest-risk transaction family. Earlier stages prove the
  private-package pattern without changing the claim/finalization machinery.
- **Uses:** Existing typed coordination values, operation IDs, retry decisions, lifecycle
  in-transaction cleanup operation, derivation tables, and bound database-time hook.
- **Changes:** Move recovery/claim/heartbeat/retry/finalization methods together with token checks,
  fingerprints, replay/read-back, fresh-time sampling, and `_FinalizationFenceLost`.
- **Preserves:** One atomic claim/open-attempt transaction; stale/not-expired/fenced result
  distinctions; no policy reroll on replay; heartbeat fencing; activation CAS; terminal Job/Attempt
  closure; lifecycle enqueue within finalization; and explicit indeterminate persistence behavior.
- **Verification checkpoint:** Run coordination, PDF finalization, and Issue-18 harness suites,
  including subclass-controlled finalization-time coverage.

### Stage 4: facade reduction and final review

- **Outcome:** The facade is only the stable seam and composition root; every persistence family is
  owned by exactly one private deep module.
- **Why last:** It is safe only after each family independently passes its closest guardrails.
- **Uses:** All private modules and all existing adapter/application callers.
- **Changes:** Remove obsolete facade implementation helpers only after every delegate reaches its
  target module; do not move `tables.py`.
- **Preserves:** Existing imports, constructor, application ports, HTTP behavior, and composition.
- **Verification checkpoint:** Run all focused suites, complete repository verification, and a
  pinned-diff code review against this plan and the approved Design.

## Data and migration

Not applicable. This is source-only implementation ownership change. It creates no database
schema, migration, backfill, data movement, mixed-version deployment contract, configuration, or
table-registry change.

## Compatibility and recovery

Compatibility is maintained by retaining the facade's import path, constructor, typed method
surface, return values, errors, and test-time database-clock hook. Application code continues to
receive one compatible object through existing ports and never imports private persistence modules.

Transaction recovery semantics remain unchanged: operation-ID replay reads durable results without
rerunning policy or work; an ambiguous coordination commit is authoritatively reconciled or stays
indeterminate; stale workers cannot finalize; and Object Lifecycle failure cannot reverse a
durable Ingestion Job result. A lifecycle insert initiated by finalization participates in the
coordinator's open transaction and cannot independently commit.

Rollback is source-only and stage-local. If a focused guardrail fails or observable behavior drifts,
revert the current stage's commit, restore the preceding facade delegation, and stop. There is no
data or migration rollback.

## Verification strategy

| Specification criterion / Test seam | Plan stage | Observable verification | Expected command or checkpoint |
|---|---|---|---|
| Public application-port and HTTP behavior do not change | 0, 2, 4 | Existing submission/public projection/integrated acceptance suites retain results and errors | `./.venv/Scripts/python -m pytest backend/test/adapters/postgres/test_ingestion_jobs.py backend/test/adapters/postgres/test_issue_19_public_postgres.py backend/test/adapters/postgres/test_issue_19_acceptance.py` |
| Lifecycle work remains independent, fenced, and retention-safe | 0, 1, 4 | Lifecycle claims, delete preparation, hard-delete checks, and reconciliation contracts pass | `./.venv/Scripts/python -m pytest backend/test/adapters/postgres/test_object_lifecycle_store.py backend/test/adapters/postgres/test_original_source_hard_delete.py backend/test/adapters/postgres/test_object_reconciliation.py` |
| Claim, lease, recovery, retry, operation replay, and authoritative time remain exact | 0, 3, 4 | Typed outcome categories and timing harness observations pass | `./.venv/Scripts/python -m pytest backend/test/adapters/postgres/test_ingestion_job_coordination.py backend/test/adapters/postgres/test_issue_18_postgres_acceptance_harness.py` |
| Derivation/activation and terminalization remain atomic | 0, 3, 4 | PDF finalization and fenced activation behavior pass | `./.venv/Scripts/python -m pytest backend/test/adapters/postgres/test_pdf_derivation_finalization.py` |
| Repository regression, lint, and deployment configuration remain valid | 0, 4 | Complete test, lint, and Compose configuration succeed | `./.venv/Scripts/python -m pytest`; `./.venv/Scripts/ruff check .`; `docker compose config --quiet` |

## Risks and assumptions

| Type | Statement | Evidence | Impact if false | Replan trigger |
|---|---|---|---|---|
| risk | A helper extracted to lifecycle could accidentally open a second finalization transaction | Approved Design requires explicit in-transaction enqueue | Terminal Job/Attempt and lifecycle work could diverge | Test or review shows an independently committed lifecycle row from finalization |
| risk | Delegation could bypass subclass-controlled database time | Existing finalization harness overrides `_database_now` | Lease/fencing timing behavior is no longer testable or exact | Harness no longer observes the injected time sequence |
| risk | Moving coordination code could separate replay helpers from their mutations | Current store co-locates fingerprints, mutations, and read-back | Replay may rerun policy/work or return a wrong result category | Any replay/fencing/recovery suite fails |
| assumption | Existing contract suites adequately characterize behavior | Tests are organized by current application/adapter seam | A necessary observable behavior lacks coverage | A stage requires a new test that cannot be justified as a facade contract test |
| assumption | No schema concern is hidden in the code movement | Approved Design prohibits table/migration change | The refactor would expand into migration behavior | Any required table, migration, or constraint change |

## Blocking decisions

None.

## Replan triggers

- A required application-port, HTTP, state-machine, retry-policy, schema, migration, or table-registry change.
- Any need to expose a private collaborator, session, transaction, ORM row, or PostgreSQL clock to application code.
- Any finalization path that cannot preserve atomic lifecycle-work enqueue in the same transaction.
- Any focused baseline failure, behavioral drift, or review finding that cannot be resolved without changing the approved Design.
- A required test path that reaches through the compatible facade into private implementation state.

## Out of scope

Changing Document, Ingestion Job, Attempt, Object Lifecycle Work, retry-policy, ObjectStore,
authorization, public status, reprocess, schema, migration, or queue semantics; splitting
`tables.py`; adding a broker; and changing application ports, HTTP contracts, or deployment
configuration are out of scope.

## Non-authorities

This plan does not authorize implementation, ticket publication, default-branch mutation, merge,
push, publication, deployment, or destructive cleanup. Those permissions remain with the owning
workflow and the human.
