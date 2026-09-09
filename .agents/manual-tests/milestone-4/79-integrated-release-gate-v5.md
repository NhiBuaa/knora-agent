# Manual Test Guide: M4.5 final-review remediation v5

## Metadata

- Feature: GitHub Issue #74 — Milestone 4 tools and human approval
- Slice: GitHub Issue #79 — integrated release gate remediation
- Specification: `docs/design/milestone-4-tools-human-approval.md`
- Final-review fixed point: `C:/Developer/Projects/knora-agent/.git/feature-delivery/m4-tools-human-approval/final-review-fixed-point-v2.json`
- Final-review result: `C:/Developer/Projects/knora-agent/.git/feature-delivery/m4-tools-human-approval/final-review-result-v2.json`
- Final-review result SHA-256: `e4f10e48a82498300ce7454910558b44cb4c4d44bce9a45aacf99d9ac5b70446`
- Structured Test Cases: `.agents/review/m4-issue-79-test-cases-v5.json`
- Guide revision: `m4-79-integrated-release-gate-v5`
- Supersedes: `m4-79-integrated-release-gate-v4` after the feature-level review returned `REQUEST_CHANGES` with seven Major findings.
- Approval status: pending independent external guide review and explicit repository-owner approval
- Evaluation history: `.agents/manual-tests/milestone-4/79-integrated-release-gate-v5.evaluations.jsonl`

## Remediation binding

The worker addresses only the seven Major findings in the bound final-review result:

1. Validate and normalize malformed lookup/provider responses to the closed public contract.
2. Add the typed, proven-no-write `provider_request_rejected` outcome and map it to `502/TOOL_PROVIDER_REQUEST_FAILED`.
3. Authorize reconciliation against the stored exact resource/scope/claims before trusted routing.
4. Map definitive `provider_scope_denied` to `403/TOOL_RESOURCE_ACCESS_DENIED`, never to indeterminate `202`.
5. Prevent uncaught provider tuple/shape/type/exception failures from escaping the typed gateway boundary.
6. Recursively sanitize public projections and audit payloads so forbidden `rejection_code` and provider/internal material cannot leak.
7. Preserve the current sanitized `ToolProposalProjection` and all previously accepted M4 behavior.

No other production behavior is in scope. The worker must not accept, integrate, push, publish,
merge, deploy, close/reopen GitHub Issues, or invoke the final feature-level `code-review`.

## Prerequisites

- Execute only in the fresh Issue #79 remediation worktree and at its committed `tested_subject_sha`.
- Preserve an explicit `KNORA_DATABASE_URL` when supplied. Otherwise use the bounded local IPv4 fallback; record only sanitized host/database identity and never credentials.
- `main` remains `6312c4c4230032aa92ca5915803fcfaf564354fa`.
- Existing #75–#78 accepted/integrated frontier evidence is immutable and must be validated from the worker source base.
- Every execution, reconciliation and provider matrix must use independently authored fixtures and expected envelopes. It must not import, derive, mirror or read expected values from production mappers, serializers, enums or types.
- The recursive forbidden-field scan covers every public projection, error envelope, captured audit snapshot and release artifact. It must have zero hits for `rejection_code`, raw provider data, provider routing data, keys, credentials and internal exception material.

## Locked Test Cases

### M4-79-TC-01 — Authorization-before-lookup and malformed lookup contract

Execute authorized, denied, malformed typed-result and response-model failure rows. Denied rows must make zero provider calls. Malformed provider data must normalize to `502 TOOL_PROVIDER_CONTRACT_INVALID`, never an untyped 500.

### M4-79-TC-02 — Immutable proposal and human decision

Exercise create/read/approve/reject/not-found/expired/stale/validation rows and race human decision contenders. Model/system denial precedes mutation; exactly one human CAS decision wins; material and audit ordering remain immutable.

### M4-79-TC-03 — Execution public envelopes and current projection

Use an independently authored matrix for success, terminal failure, proven no-write provider rejection, provider scope denial, indeterminate, in-progress, fenced, authority-denial and stale outcomes. Verify `502/TOOL_PROVIDER_FAILURE` with sanitized `failure_code`, `502/TOOL_PROVIDER_REQUEST_FAILED`, `403/TOOL_RESOURCE_ACCESS_DENIED`, exact `409` in-progress/fenced envelopes, and a current sanitized proposal projection on every result. Denied/stale rows retain zero admission/write/effect. Recursively scan for all forbidden fields.

### M4-79-TC-04 — Duplicate-free execution race

Race direct/replayed execution using the same identity/fingerprint, then a conflicting fingerprint. Exactly one admission/effect may occur; same input replays and the conflict is typed.

### M4-79-TC-05 — Reconciliation public envelopes after crashes

Use an independently authored reconciliation matrix across both crash windows. Exercise success, all terminal rejections, proven no-write rejection, unavailable, timeout, malformed, not-found, in-progress, fenced, scope-denied and exact-resource-authorization rows. Exact current-resource authorization precedes trusted observation; scope denial is `403 TOOL_RESOURCE_ACCESS_DENIED`; ambiguity/not-found remains `202` non-terminal; every result carries the current sanitized proposal projection; forbidden-field scan is zero-hit.

### M4-79-TC-06 — PostgreSQL strict-expiry takeover

Race current, foreign, stale and generation-mismatched owners over the lock barrier. Exactly one post-lock strict-expiry takeover increments generation once; only current unexpired ownership may observe/finalize.

### M4-79-TC-07 — Audit reconstruction and sanitization

Reconstruct ordered audit across lookup, proposal, decision, admission, authority, crash, takeover, observation and terminal outcomes. Recursively scan public/audit/release evidence for every forbidden category.

### M4-79-TC-08 — Root-CWD migration regression

At root CWD collect and run `backend/test/tools/test_reconciliation_postgres.py::test_reconciliation_migration_round_trips_persisted_takeover_audit`. Run upgrade `20260824_0040`, downgrade `20260824_0039`, re-upgrade and `current` via `-c backend/alembic.ini`. No skip, xfail, deselection, assertion weakening or backend-CWD substitute is allowed.

### M4-79-TC-09 — Exact-subject regression

At `tested_subject_sha`, run affected public-contract tests, full pytest, Ruff and Compose. Every required node passes; only the three locked baseline skips remain.

### M4-79-TC-10 — Scope and deferred review

Validate #75–#78 frontier identities, bind all changed paths to this remediation scope, and verify `main` is unchanged. The worker must not create or execute the final fixed-point review.

### M4-79-TC-11 — Guide lock and append-only Evaluation

Record guide/history digests before execution. Append a candidate Evaluation bound to the tested subject and technical evidence, then append separate explicit human approval only after owner review. Earlier guide and history bytes must not change.

### M4-79-TC-12 — Provider boundary normalization

Inject malformed lookup, create-ticket and outcome-observation results covering absent fields, wrong types, wrong tuple arity, unexpected exceptions and unknown outcomes. Each maps to the specified typed contract-invalid or non-terminal observation result without an untyped 500 or fabricated terminal failure.

### M4-79-TC-13 — Current exact-resource observation authorization

Start an execution, revoke or change current exact resource/scope authority without expiring the write token, and reconcile from a valid Workspace principal. Observation must be denied before trusted/provider routing when the stored exact resource is no longer authorized; matching authority permits observation; provider scope denial is `403 TOOL_RESOURCE_ACCESS_DENIED`.

This guide becomes immutable only after independent external approval and explicit repository-owner
approval for its exact digest. Every execution appends a new Evaluation record; it never alters v4
or earlier history.
