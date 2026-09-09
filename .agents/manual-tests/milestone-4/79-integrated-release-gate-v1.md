# Manual Test Guide: M4.5 integrated acceptance and release gate

## Metadata

- Feature: GitHub Issue #74 — Milestone 4 tools and human approval
- Slice: GitHub Issue #79 — M4.5 integrated acceptance and release gate
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/79
- Ticket contract: `.agents/review/m4-issue-79-revision-v2.md`
- Ticket external review: `.agents/review/m4-issue-79-ticket-external-review-v2.json`
- Structured Test Cases: `.agents/review/m4-issue-79-test-cases-v1.json`
- Guide revision: `m4-79-integrated-release-gate-v1`
- Approval status: pending independent guide review and delegated repository-owner lock
- Evaluation history: `.agents/manual-tests/milestone-4/79-integrated-release-gate-v1.evaluations.jsonl`

## Prerequisites

- Execute only in `C:/Developer/Projects/knora-agent-worktree` on the prepared Issue #79 branch.
- The worker must establish and commit `tested_subject_sha` before final verification. Evidence,
  candidate Evaluation and human approval are later append-only descendants and must prove their
  diffs are evidence-only; any other descendant change selectively invalidates affected cases.
- Use `.venv/Scripts/python.exe` and set `KNORA_DATABASE_URL` to the local Compose PostgreSQL at
  `127.0.0.1:5432/knora`. Record host/database/CWD/interpreter but never credentials.
- Load all expected public matrices from immutable fixtures independent of production result types,
  serializers, HTTP mappers and enums.
- `main` must remain `6312c4c4230032aa92ca5915803fcfaf564354fa`. The worker cannot accept,
  integrate, push, publish, merge, close Issues, or invoke `code-review`.

## Locked Test Cases

### M4-79-TC-01: Authorization-before-lookup matrix

- Purpose: verify M4.1 authorized, unauthenticated, unauthorized, cross-Workspace, malformed,
  scope-denied, not-found, unavailable and malformed-provider lookup rows.
- Steps:
  1. Execute every independently defined lookup matrix row through public HTTP.
  2. Capture status, recursive body keys/value domains, forbidden fields, lifecycle and provider-call
     counters for each row.
- Expected results:
  - Every body and status exactly matches the independent matrix.
  - Every denied row makes zero provider lookup calls; only declared authorized rows reach provider.
- Evidence to capture: matrix digest, projections, provider lookup counters and zero-call traces.

### M4-79-TC-02: Immutable proposal and human decision matrix

- Purpose: verify M4.2 material immutability, binding/actor safety and concurrent decision CAS.
- Steps:
  1. Execute every proposal create/read/approve/reject/not-found/expired/stale/validation row.
  2. Attempt model and system decisions, then race human approver/rejector contenders.
- Expected results:
  - Model/system decisions fail before persistent mutation; material fields remain immutable.
  - Exactly one human decision wins and ordered audit records both outcome and losing observation.
- Evidence to capture: independent matrix, before/after durable state, audit sequence and counters.

### M4-79-TC-03: Current execution authority and projection matrix

- Purpose: verify M4.3 current authority, compatibility checks and safe public execution results.
- Steps:
  1. Execute all independent success, each closed rejection, indeterminate, in-progress, fenced,
     idempotency-conflict, authority-denial and compatibility-stale rows.
  2. Capture admission, write and effect counters plus durable projections.
- Expected results:
  - Every result is field-for-field exact; denied/stale rows have zero admission/write/effect.
  - Valid execution retains one server-owned logical identity and fingerprint.
- Evidence to capture: matrix projections, counters, admission lineage and provider ledger rows.

### M4-79-TC-04: Duplicate-free execution race

- Purpose: prove concurrent/replayed execution cannot create duplicate provider effects.
- Steps:
  1. Race direct and replayed execution with same identity/fingerprint.
  2. Repeat with a conflicting fingerprint.
- Expected results:
  - One admission/current owner wins; same input replays, conflicting input returns typed conflict.
  - SQLite contains at most one provider ticket/effect for the logical identity.
- Evidence to capture: admission rows, SQLite idempotency ledger, effect counters and result matrix.

### M4-79-TC-05: Reconciliation, crash and closed provider-outcome matrix

- Purpose: verify M4.4 provider-owned truth, two crash windows and every terminal/non-terminal row.
- Steps:
  1. Independently restart Knora and SQLite in both crash windows.
  2. Exercise success; `target_not_found`, `validation_rejected`, `policy_rejected`; unavailable,
     timeout, malformed, not-found, in-progress and fenced reconciliation rows.
- Expected results:
  - Success and all three closed rejections are distinct, restart-stable and exact; rejection rows
    create no provider ticket/effect.
  - Ambiguous/no-receipt rows remain non-terminal until separately authorized same-identity recovery.
- Evidence to capture: SQLite snapshots, HTTP/application matrix, restart trace and effect counts.

### M4-79-TC-06: PostgreSQL strict-expiry takeover

- Purpose: prove post-lock database time, generation fencing and sole current-owner finalization.
- Steps:
  1. Race current, foreign, stale and generation-mismatched owners over a lock barrier.
  2. Capture fresh database time, lease/generation transitions and write attempts.
- Expected results:
  - Exactly one strict-expiry takeover increments generation once.
  - Stale/losing owners are fenced and only the current unexpired owner observes/finalizes.
- Evidence to capture: clock tuple, rows, contender results and no-stale-write proof.

### M4-79-TC-07: Audit reconstruction and sanitization

- Purpose: prove integrated M4 is reconstructable without private leakage.
- Steps:
  1. Reconstruct ordered audit across lookup, proposal, decision, admission, authority, crash,
     takeover/retry, observation and terminal outcome paths.
  2. Recursively scan public/audit/release evidence for forbidden secret, routing, envelope and key
     material.
- Expected results:
  - Required actors, authority/binding snapshots, generations and terminal facts are complete.
  - Sanitization scan reports zero forbidden value hits.
- Evidence to capture: audit timeline, independent SQLite comparison and sanitization report.

### M4-79-TC-08: Root-CWD Alembic regression repair

- Purpose: close the known baseline failure without hiding it.
- Steps:
  1. From repository root, set `KNORA_DATABASE_URL` for 127.0.0.1 and run the exact focused
     reconciliation migration round-trip test.
  2. Recreate/migrate as supported, upgrade to `20260824_0040`, downgrade one revision, re-upgrade
     and confirm current head.
- Expected results:
  - All commands exit zero with CWD/interpreter/effective database identity recorded.
  - No skip, xfail, assertion weakening or backend-CWD-only substitute is used.
- Evidence to capture: commands/exits, revisions, sanitized environment identity and focused nodes.

### M4-79-TC-09: Exact-subject full regression evidence

- Purpose: prove M1–M3 and M4 stay green on the immutable candidate.
- Steps:
  1. At `tested_subject_sha`, run focused M4 matrices, complete repository pytest, Ruff and Compose.
  2. Capture complete collected/pass/fail/skip/xfail node inventory before tracked content changes.
- Expected results:
  - Every required node passes. Only the three already-classified locked PDF baseline skips remain;
    no newly skipped or xfailed node exists.
  - Deterministic release evidence binds subject SHA, guide digest, environment and invocations.
- Evidence to capture: node inventory, command records, clean status and release-evidence digest.

### M4-79-TC-10: Scope/invalidation and deferred final review

- Purpose: protect the integration/default branch and prevent premature final review.
- Steps:
  1. Produce source-base-to-tested-subject scope manifest and classify every later descendant.
  2. Verify roadmap/release projection is included before execution, `main` is unchanged, and only a
     non-binding final-review readiness checklist/template exists.
- Expected results:
  - Any product/test/fixture/config/dependency/roadmap change invalidates affected acceptance;
    evidence-only descendants do not alter tested behavior.
  - No fixed-point descriptor is created, pinned, validated or reviewed by this worker.
- Evidence to capture: scope manifests, invalidation decisions, main SHA and readiness template.

### M4-79-TC-11: Guide lock and append-only Evaluation lifecycle

- Purpose: prove manual acceptance authority itself is immutable and traceable.
- Steps:
  1. Before execution, record exact guide digest, lock approval artifact and initial history digest.
  2. Append a candidate Evaluation binding tested/evidence heads and technical verdict.
  3. Append a separate human-approval record for the exact PASSED candidate.
- Expected results:
  - Guide bytes and all earlier history records are unchanged.
  - Candidate and approval records are append-only and bind exact identities; approval never rewrites
    the candidate.
- Evidence to capture: guide digest, approval artifact, history before/after digests and JSONL rows.

This guide becomes immutable only after its independent external review is `APPROVE` and the
repository-owner delegated approval is recorded against this exact guide digest. Every later run is
appended to the named Evaluation history; a semantic change requires a new guide revision.
