# Manual Test Guide: M4.5 final-review remediation

## Metadata

- Feature: GitHub Issue #74 — Milestone 4 tools and human approval
- Slice: GitHub Issue #79 — integrated release gate remediation
- Specification: `docs/design/milestone-4-tools-human-approval.md`
- Review findings: `C:/Developer/Projects/knora-agent/.git/feature-delivery/m4-tools-human-approval/final-review-result-v1.json`
- Structured Test Cases: `.agents/review/m4-issue-79-test-cases-v4.json`
- Guide revision: `m4-79-integrated-release-gate-v4`
- Supersedes: `m4-79-integrated-release-gate-v3` after external review `EXT-V3-01` and `EXT-V3-02`
- Approval status: pending external guide review and explicit repository-owner approval
- Evaluation history: `.agents/manual-tests/milestone-4/79-integrated-release-gate-v4.evaluations.jsonl`

## Prerequisites

- Execute only in the fresh Issue #79 remediation worktree and at its committed `tested_subject_sha`.
- Preserve an explicit `KNORA_DATABASE_URL` when supplied. Otherwise the test bootstrap must use the bounded local IPv4 fallback; record only sanitized host/database identity and never credentials.
- `main` remains `6312c4c4230032aa92ca5915803fcfaf564354fa`. The worker cannot accept, integrate, push, publish, merge, close GitHub Issues, or invoke `code-review`.
- Existing #75–#78 accepted/integrated frontier evidence is immutable. The remediation is limited to satisfying the two final-review public execution/reconciliation contract findings.
- Every execution/reconciliation matrix must use fixtures and expected envelopes independently authored from the production implementation. It must not import, derive, mirror or read expected values from production mappers, serializers, enums or types.
- The recursive forbidden-field scan applies to every public projection, error envelope and captured audit snapshot. It must have zero hits for `rejection_code`, raw provider data, provider routing data, keys, credentials and internal exception material.

## Locked Test Cases

### M4-79-TC-01 — Authorization-before-lookup

Execute all authorized and denied lookup rows. Each status/body must match the independent recursive allowlist, and denied rows must make zero provider lookup calls. Capture the matrix digest, counters and sanitized projections.

### M4-79-TC-02 — Immutable proposal and human decision

Exercise create/read/approve/reject/not-found/expired/stale/validation rows and race human decision contenders. Model/system denial precedes mutation; exactly one human CAS decision wins; material and audit ordering are immutable. Capture durable before/after state, audit and matrix evidence.

### M4-79-TC-03 — Execution public envelopes and current projection

Use the required independently-authored execution HTTP matrix for success, each terminal provider rejection, indeterminate, in-progress, fenced, authority-denial and compatibility-stale outcomes. Its fixtures and expected envelopes must not derive from production mappers, serializers, enums or types. Verify terminal failure is `502` with `error.code: TOOL_PROVIDER_FAILURE` and only sanitized `failure_code`; `rejection_code` and all forbidden material are absent. Verify in-progress and fenced rows are `409` with `TOOL_EXECUTION_IN_PROGRESS` and `TOOL_EXECUTION_FENCED`. Every result must carry the current sanitized proposal projection, including lifecycle, revision and audit. Denied/stale rows retain zero admission/write/effect. Capture independent matrix source/digest, recursive allowlists, projection/audit snapshots, counters and a zero-hit forbidden-field scan.

### M4-79-TC-04 — Duplicate-free execution race

Race direct/replayed execution using the same identity/fingerprint, then a conflicting fingerprint. Exactly one admission/effect may occur; same input replays and conflict is typed. Capture PostgreSQL admission, SQLite idempotency ledger and effect counters.

### M4-79-TC-05 — Reconciliation public envelopes after crashes

Use the required independently-authored reconciliation HTTP matrix; its fixtures and expected envelopes must not derive from production mappers, serializers, enums or types. Restart Knora and SQLite independently across both crash windows. Exercise success, all three terminal rejections, unavailable, timeout, malformed, not-found, in-progress and fenced outcomes. Terminal failures must be distinct `502/TOOL_PROVIDER_FAILURE` envelopes with sanitized `failure_code`; in-progress/fenced use exact `409` envelopes; ambiguous/not-found stays `202` non-terminal. Every outcome carries the current sanitized proposal projection. Capture independent matrix source/digest, SQLite snapshots, HTTP allowlist matrix, restart trace, projection/audit snapshots and a zero-hit forbidden-field scan.

### M4-79-TC-06 — PostgreSQL strict-expiry takeover

Race current, foreign, stale and generation-mismatched owners over the lock barrier. Exactly one post-lock strict-expiry takeover increments generation once; only current unexpired ownership may observe/finalize. Capture database time, durable lease rows and fencing evidence.

### M4-79-TC-07 — Audit reconstruction and sanitization

Reconstruct ordered audit across lookup, proposal, decision, admission, authority, crash, takeover, observation and terminal outcomes. Recursively scan public/audit/release evidence for every forbidden category listed in prerequisites. Capture timeline, independent SQLite comparison and zero-hit scan.

### M4-79-TC-08 — Root-CWD migration regression

At root CWD collect and run `backend/test/tools/test_reconciliation_postgres.py::test_reconciliation_migration_round_trips_persisted_takeover_audit`. Run upgrade `20260824_0040`, downgrade `20260824_0039`, re-upgrade and `current` via `-c backend/alembic.ini`. Each command exits zero at revision `20260824_0040`; no skip, xfail, deselection, assertion weakening or backend-CWD substitute is allowed.

### M4-79-TC-09 — Exact-subject regression

At `tested_subject_sha`, run the affected public contract tests, full pytest, Ruff and Compose. Every required node passes; only the three locked PDF baseline skips remain. Capture invocation, node inventory, clean status and release-evidence digest.

### M4-79-TC-10 — Scope and deferred review

Validate #75–#78 frontier identities, bind all changed paths to remediation scope, and verify `main` is unchanged. The worker must not create the final fixed-point review or execute it. Capture frontier evidence, scope/invalidation decision, `main` SHA and deferred-review boundary.

### M4-79-TC-11 — Guide lock and append-only Evaluation

Record guide/history digests before execution. Append a candidate Evaluation bound to the tested subject and technical evidence, then append separate explicit human approval only after owner review. Earlier history and guide bytes must not be rewritten.

This guide becomes immutable only after independent external approval and explicit repository-owner approval for its exact digest. Every execution appends a new Evaluation record; it never alters v2 or v3.
