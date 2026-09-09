# Issue #79 contract revision 1 — M4.5 integrated acceptance and release gate

Status: review candidate  
Issue: https://github.com/NhiBuaa/knora-agent/issues/79  
Source base: `5af5c5c914ea904fe1e14de1acff859113d53244`  
Issue branch/worktree: `codex/issue-79-m4-release-gate` / `C:/Developer/Projects/knora-agent-worktree`

## Outcome

Produce the exact-SHA, append-only acceptance and release evidence for the integrated Milestone 4
behavior delivered by Issues #75–#78. Repair only integration or acceptance-harness gaps needed to
make that evidence trustworthy. Do not redesign the approved M4 seams or perform the final
feature-level `code-review` in this Issue session.

## Required acceptance contract

1. Lock one manual acceptance guide covering M4.1–M4.4 and append every run to one Evaluation
   history without rewriting earlier results.
2. Demonstrate authorization-before-lookup for authorized, unauthenticated/unauthorized, and
   cross-Workspace read-only requests, including zero provider lookup on denied paths.
3. Prove immutable proposal material and exact target, capability, external-scope binding, policy,
   actor, and revision-CAS semantics; model/system approval is forbidden and concurrent decisions
   have one deterministic durable winner.
4. Prove execution uses current execution authority, fails closed after authority revocation,
   retains one server-owned logical idempotency identity and fingerprint, and creates at most one
   external effect across direct execution and retries.
5. Prove the SQLite reference provider independently owns external state and idempotency, covers
   both crash windows, provider-not-found recovery, strict stale-owner fencing, and the closed
   success/failure/non-terminal result matrix.
6. Reconstruct append-only audit evidence for caller, proposal actor, human approver/rejector,
   execution authority, immutable policy/binding snapshots, attempts/generations, provider
   identity, observations, and terminal outcome/failure without leaking secrets or raw routing.
7. Run focused M4 acceptance plus complete M1–M3 regression verification on one exact candidate
   SHA. Record changed-scope invalidation and rerun every affected accepted case.
8. Preserve `main` at `6312c4c4230032aa92ca5915803fcfaf564354fa`, record integration readiness,
   and prepare—but do not invoke—the single final feature `code-review`. Never claim M4 complete
   before Issue #79 is accepted, integrated, and closed and the later final review passes.

## Mandatory integration-gap remediation

The approved baseline is not green: 967 tests produced 963 passed, 3 skipped, and 1 failure from
the repository root. The failing node is
`backend/test/tools/test_reconciliation_postgres.py::test_reconciliation_migration_round_trips_persisted_takeover_audit`.
`backend/alembic.ini` currently resolves `script_location = migrations` relative to the process
CWD. The same focused behavior passed in the prior diagnostic when executed from `backend/`.

The worker owns a minimal, test-backed fix that makes this round-trip CWD-independent. Completion
requires the focused test from repository root and the complete repository verification to pass on
the exact candidate SHA. The worker must not classify the starting baseline as green or remove,
skip, xfail, or weaken the assertion.

## Test and evidence obligations

- Build a deterministic integrated M4 release-evidence harness whose output binds the exact
  candidate SHA, locked guide revision/digest, test-case IDs, executed node IDs, verification
  commands, environment identity, and sanitized per-case observations.
- Cover the public HTTP projections as exact allowlists and prove denial-before-side-effect ordering
  with observable call/effect counters.
- Exercise PostgreSQL concurrency and restart boundaries serially against the pinned worktree
  database; use `127.0.0.1`, not `localhost`, for the local Compose binding.
- Prove SQLite provider truth survives adapter/application restart independently of PostgreSQL.
- Record a scope manifest from source base to candidate. Dependency, lockfile, plugin/marketplace,
  provider-vendor, public-API, migration, or approved-seam expansion is forbidden unless the leader
  first routes it back through governed design/replan.
- Record Ruff, Compose configuration, Alembic upgrade/downgrade/re-upgrade, focused M4 tests, the
  complete repository suite, and exact exit status. No raw command output or secret value belongs
  in committed evidence.
- Append manual acceptance Evaluation evidence; do not overwrite prior guide or Evaluation data.

## Allowed scope

- `.agents/manual-tests/milestone-4/79-*`
- `.agents/review/m4-issue-79-*`
- `evals/fixtures/m4_79_*` and `evals/test/test_m4_79_*`
- The minimum Alembic configuration/test-harness files required for the declared CWD defect.
- A production file only when an integrated criterion demonstrably cannot be satisfied without a
  minimal fix that stays inside the approved M4 design; report any such path and justification.

## Prohibited actions

- Do not accept the Issue, integrate it, advance the feature, invoke `code-review`, merge, push,
  publish, deploy, or close Issue #79/#74.
- Do not mutate `main`, the feature integration branch, another Issue branch, or another worktree.
- Do not weaken assertions, suppress the known failure, fabricate evidence, or treat a focused pass
  from the wrong CWD as closure.
- Do not add dynamic plugins, capability discovery, runtime provider registration, a vendor SDK, or
  a marketplace.

## Required verification

Run from `C:/Developer/Projects/knora-agent-worktree` unless the command explicitly changes CWD:

```powershell
$env:DATABASE_URL='postgresql+psycopg://knora:knora@127.0.0.1:5432/knora?connect_timeout=3'
.\.venv\Scripts\python -m pytest backend/test/tools/test_reconciliation_postgres.py::test_reconciliation_migration_round_trips_persisted_takeover_audit
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\ruff check .
docker compose config --quiet
```

Also run a clean Alembic upgrade, downgrade/re-upgrade lifecycle using the repository-supported
invocation and record revision `20260824_0040` as the expected head.

## Return contract

Commit the bounded implementation and return through the reserved Issue-session Resume Contract.
Report exact candidate SHA, changed paths/scope classification, focused and full verification,
structural evidence, guide/evidence artifacts, any design-required finding, and the immutable
return/result-evidence paths. The leader alone validates, accepts, integrates, and advances.
