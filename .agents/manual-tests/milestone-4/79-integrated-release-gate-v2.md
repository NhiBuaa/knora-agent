# Manual Test Guide: M4.5 integrated acceptance and release gate

## Metadata

- Feature: GitHub Issue #74 — Milestone 4 tools and human approval
- Slice: GitHub Issue #79 — M4.5 integrated acceptance and release gate
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/79
- Ticket contract: `.agents/review/m4-issue-79-revision-v2.md`
- Ticket external review: `.agents/review/m4-issue-79-ticket-external-review-v2.json`
- Supersedes: `m4-79-integrated-release-gate-v1` after guide-review findings
- Structured Test Cases: `.agents/review/m4-issue-79-test-cases-v2.json`
- Guide revision: `m4-79-integrated-release-gate-v2`
- Approval status: pending independent guide review and delegated repository-owner lock
- Evaluation history: `.agents/manual-tests/milestone-4/79-integrated-release-gate-v2.evaluations.jsonl`

## Prerequisites

- Execute only in `C:/Developer/Projects/knora-agent-worktree` on `codex/issue-79-m4-release-gate`.
- The immutable native frontier is source base `5af5c5c914ea904fe1e14de1acff859113d53244`.
  Before any case, collect and validate the immutable accepted-run, integrated-commit, merged-PR
  and closed-Issue identities for #75, #76, #77 and #78 from
  `.agents/review/m4-issue-79-frontier-baseline-v2.json`; reject the candidate if any identity is
  absent, differs, or its source-base lineage is inconsistent.
- Commit implementation/harness changes as `tested_subject_sha` before final verification.
  Later release evidence, candidate Evaluation and human approval are append-only evidence-only
  descendants; any production, test, fixture, command, dependency, config, roadmap or release-ledger
  change selectively invalidates affected cases.
- Use `C:/Developer/Projects/knora-agent-worktree/.venv/Scripts/python.exe`; set only
  `KNORA_DATABASE_URL` to local Compose PostgreSQL at `127.0.0.1:5432/knora`. Record CWD,
  interpreter, sanitized effective host/database and exit; never record credentials.
- Expected public matrices must be immutable fixtures independent of production result types,
  serializers, HTTP mappers and enums. `main` must remain
  `6312c4c4230032aa92ca5915803fcfaf564354fa`.
- The worker cannot accept, integrate, push, publish, merge, close Issues or invoke `code-review`.

## Locked Test Cases

### M4-79-TC-01: Authorization-before-lookup matrix

- Steps: execute every independently defined authorized, unauthenticated, unauthorized,
  cross-Workspace, malformed, scope-denied, not-found, unavailable and malformed-provider HTTP row.
- Expected results: each status/body recursively matches its independent allowlist; every denied row
  has zero provider lookup calls and only declared authorized rows reach the provider.
- Evidence: matrix digest, public projections, lifecycle and provider lookup counters/zero-call traces.

### M4-79-TC-02: Immutable proposal and human decision matrix

- Steps: execute each proposal create/read/approve/reject/not-found/expired/stale/validation row;
  attempt model/system decisions and race human approver/rejector contenders.
- Expected results: model/system failure precedes persistent mutation; material remains immutable;
  exactly one human CAS decision wins and the audit includes its loser observation.
- Evidence: independent matrix, durable before/after state, audit ordering and counters.

### M4-79-TC-03: Current execution authority and projection matrix

- Steps: execute success, every closed rejection, indeterminate, in-progress, fenced,
  idempotency-conflict, authority-denial and compatibility-stale matrix rows.
- Expected results: each field/status is exact; denied or stale rows make zero admission/write/effect;
  valid execution has one server-owned logical identity and fingerprint.
- Evidence: matrix projections, admission/write/effect counts, lineage and provider ledger rows.

### M4-79-TC-04: Duplicate-free execution race

- Steps: race direct/replayed execution with the same identity/fingerprint, then with a conflicting
  fingerprint.
- Expected results: one current admission wins; same input replays; conflicting input is a typed
  conflict; SQLite stores at most one provider ticket/effect for the logical identity.
- Evidence: admission rows, SQLite idempotency ledger, effect counters and independent result matrix.

### M4-79-TC-05: Reconciliation, crash and closed provider-outcome matrix

- Steps: independently restart Knora and SQLite in both crash windows; exercise success,
  `target_not_found`, `validation_rejected`, `policy_rejected`, unavailable, timeout, malformed,
  not-found, in-progress and fenced rows.
- Expected results: success and all three closed rejections are distinct restart-stable exact rows
  with no provider ticket/effect; ambiguous/no-receipt is non-terminal until separately authorized
  same-identity recovery.
- Evidence: SQLite snapshots, HTTP/application matrix, restart trace and effect counts.

### M4-79-TC-06: PostgreSQL strict-expiry takeover

- Steps: race current, foreign, stale and generation-mismatched owners over a lock barrier; capture
  fresh database time, lease/generation transitions and writes.
- Expected results: exactly one post-lock strict-expiry takeover increments generation once;
  stale/losing owners are fenced and only current unexpired owner observes/finalizes.
- Evidence: clock tuple, durable rows, contender results and no-stale-write proof.

### M4-79-TC-07: Audit reconstruction and sanitization

- Steps: reconstruct ordered audit over lookup, proposal, decision, admission, authority, crash,
  takeover/retry, observation and terminal outcomes; recursively scan public/audit/release evidence
  for forbidden secret, routing, envelope and key material.
- Expected results: actor, authority/binding snapshot, generation and terminal facts are complete;
  forbidden-value scan has zero hits.
- Evidence: audit timeline, independent SQLite comparison and sanitized scan report.

### M4-79-TC-08: Root-CWD Alembic regression repair

- Steps:
  1. At repository root, set `KNORA_DATABASE_URL` and run exactly
     `C:/Developer/Projects/knora-agent-worktree/.venv/Scripts/python.exe -m pytest --collect-only -q backend/test/tools/test_reconciliation_postgres.py::test_reconciliation_migration_round_trips_persisted_takeover_audit`,
     then exactly the same command without `--collect-only`. The latter node must execute and pass.
  2. From the same root CWD and interpreter, run literal lifecycle commands:
     `-m alembic -c backend/alembic.ini upgrade 20260824_0040`,
     `-m alembic -c backend/alembic.ini downgrade 20260824_0039`,
     `-m alembic -c backend/alembic.ini upgrade 20260824_0040`, and
     `-m alembic -c backend/alembic.ini current`.
  3. Compare focused-test source, its assertion-bearing fixture/configuration and collection
     identity at source base and `tested_subject_sha`; record the diff and reject any suppression.
- Expected results: every command exits zero, the focused node is collected and passes from root CWD,
  current revision is `20260824_0040`, and evidence binds CWD/interpreter/sanitized database/revision.
  Skip, xfail, deselection, assertion weakening and a backend-CWD substitute are failures.
- Evidence: literal command/argv records and exits, collected/executed node IDs, source/fixture/config
  integrity diff, revision records and sanitized environment identity.

### M4-79-TC-09: Exact-subject full regression evidence

- Steps: at `tested_subject_sha`, run focused M4 matrices, complete repository pytest, Ruff and
  Compose; capture collected/pass/fail/skip/xfail node inventory before tracked-content changes.
- Expected results: every required node passes; only the three locked PDF baseline skips remain; no
  new skip/xfail exists; deterministic release evidence binds subject SHA, guide digest and invocations.
- Evidence: node inventory, command records, clean status and release-evidence digest.

### M4-79-TC-10: Native frontier, scope/invalidation and deferred final review

- Steps:
  1. Before execution, capture the #75–#78 accepted-run, integrated-commit, merged-PR and closed
     state identities from the immutable frontier baseline; validate all against source base
     `5af5c5c914ea904fe1e14de1acff859113d53244` and reject any missing/inconsistent identity.
  2. Bind those frontier identities, source base and `tested_subject_sha` to the scope/invalidation
     manifest; classify every descendant and show an evidence-only descendant cannot change behavior.
  3. Verify roadmap/release projection precedes execution, `main` remains unchanged, and only a
     non-binding final-review readiness checklist/template exists.
- Expected results: any product/test/fixture/config/dependency/roadmap change invalidates affected
  acceptance; no actual fixed-point descriptor is created, pinned, validated or reviewed.
- Evidence: frontier-identity validation record, source-base scope manifest, descendant
  invalidation decisions, `main` SHA and readiness template.

### M4-79-TC-11: Guide lock and append-only Evaluation lifecycle

- Steps: before execution record exact guide digest/lock approval/initial history digest; append a
  candidate Evaluation binding tested/evidence heads and technical verdict; append separate human
  approval for that exact PASSED candidate.
- Expected results: guide bytes/earlier history do not change; candidate/approval records are
  append-only exact-identity bindings and approval never rewrites candidate.
- Evidence: guide digest, approval artifact, history before/after digests and JSONL rows.

This guide becomes immutable only after its independent external review is `APPROVE` and the
repository-owner delegated approval binds this exact digest. Every run appends to the named history;
a semantic change requires another revision.
