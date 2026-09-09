# Manual Test Guide: M4.5 final-review remediation v6

## Metadata

- Feature: GitHub Issue #74 — Milestone 4 tools and human approval
- Slice: GitHub Issue #79 — integrated release gate remediation
- Specification: `docs/design/milestone-4-tools-human-approval.md`
- Integrated fixed point: `C:/Developer/Projects/knora-agent/.git/feature-delivery/m4-tools-human-approval/final-review-fixed-point-v3.json`
- Fixed-point SHA-256: `84f5d90fdb52553e15990fdfefa5f229fda00d56d355a744c30b5c5a15a1852e`
- Spec-axis review: `C:/Developer/Projects/knora-agent/.git/feature-delivery/m4-tools-human-approval/final-review-spec-v3.json`
- Spec-axis review SHA-256: `6af0b4d7db8b5c628b9123119872d9c782782d780ed7749317f4ad54897d232f`
- Structured Test Cases: `.agents/review/m4-issue-79-test-cases-v6.json`
- Guide revision: `m4-79-integrated-release-gate-v6`
- Supersedes: `m4-79-integrated-release-gate-v5` after the integrated fixed-point review found four new Major specification findings.
- Approval status: pending independent external guide review and explicit repository-owner approval
- Evaluation history: `.agents/manual-tests/milestone-4/79-integrated-release-gate-v6.evaluations.jsonl`

## Remediation binding

The worker addresses only the four Major findings in the bound spec-axis review:

1. Persist the closed provider terminal outcomes and reconciled request rejection outcomes in PostgreSQL without constraint-triggered 500s; preserve their exact public mappings and durable evidence.
2. Capture one PostgreSQL `transaction_timestamp()` per transition transaction and use it consistently for lease expiry, fencing, CAS predicates and transition timestamps.
3. Add the sanitized durable execution projection to every `ToolProposalProjection` read and execution/reconciliation result without exposing provider IDs, routing handles, secrets or internal exceptions.
4. Preserve a validated safe `failure_code` for the closed terminal enum in append-only audit evidence and the sanitized execution projection while continuing to redact `rejection_code` and raw provider material.

No other production behavior is in scope. The worker must not accept, integrate, push, publish,
merge, deploy, close/reopen GitHub Issues, or invoke the final feature-level `code-review`.

## Inherited locked cases

All cases M4-79-TC-01 through M4-79-TC-13 from `m4-79-integrated-release-gate-v5` remain required
and are unchanged. Their expected results, independent fixtures, recursive forbidden-field scan,
root-CWD migration regression, append-only Evaluation history and final-review boundary remain
locked. The new cases below extend the same guide; they do not replace or weaken earlier cases.

## New locked Test Cases

### M4-79-TC-14 — PostgreSQL closed provider-outcome persistence

Execute provider request rejection, provider scope denial and reconciled request rejection through
both execution and reconciliation paths against PostgreSQL. Use independently authored fixtures and
expected envelopes; inspect the persisted observation, terminal state and append-only audit after
each transition.

Expected results:

- `provider_request_rejected` persists as a typed proven-no-write terminal observation and maps to `502 TOOL_PROVIDER_REQUEST_FAILED`.
- `provider_scope_denied` persists as a definitive authorization denial and maps to `403 TOOL_RESOURCE_ACCESS_DENIED`, never indeterminate `202`.
- `reconciled_request_rejected` remains durable and reconstructable without a persistence constraint error or untyped `500`.
- Migration constraints/guards accept only the specified closed values; arbitrary provider text remains rejected/redacted.
- Durable audit and public evidence contain the safe closed `failure_code` only, never `rejection_code` or raw provider material.

Capture migration revision, row state, HTTP envelope, audit snapshot, provider-call/write counters
and a recursive forbidden-field scan.

### M4-79-TC-15 — Fixed transaction-time lease and fencing decisions

Exercise acquire, authorize/admit, observe, finalize and stale-takeover transitions in PostgreSQL
under a single transaction while the database clock advances between statements. Race current,
foreign, stale and generation-mismatched owners over the lock barrier.

Expected results:

- Each transition captures one `transaction_timestamp()` value and all lease comparisons, CAS predicates and transition timestamps use that fixed value.
- A transition cannot change classification merely because a later statement sees a different wall-clock value.
- Exactly one valid owner or strict-expiry takeover wins; stale/foreign/generation-mismatched owners are fenced without duplicate effect.

Capture SQL/transaction identity, captured timestamp, lease/generation rows, CAS result and ordered
audit facts without credentials.

### M4-79-TC-16 — Sanitized execution projection on every proposal result

Create, read, execute and reconcile a proposal through in-memory and PostgreSQL-backed paths,
including success, terminal, indeterminate, in-progress, fenced and authority-denied outcomes.

Expected results:

- Every current `ToolProposalProjection` includes the durable sanitized execution lifecycle, generation, observations and terminal state where available.
- Execution and reconciliation HTTP results expose the same current nested proposal projection.
- Provider IDs, routing handles, secrets, raw provider payloads, internal exceptions and `rejection_code` are absent recursively.
- The projection remains stable across reload and recovery and is sufficient to reconstruct the public lifecycle without trusted-store internals.

Capture JSON responses, projection schema/allowlist, reload snapshots and recursive zero-hit scan.

### M4-79-TC-17 — Safe failure-code audit reconstruction

Run each closed terminal failure (`target_not_found`, `validation_rejected`, `policy_rejected` and
the approved provider request-rejection code) through execution and reconciliation, then rebuild
the ordered audit from both stores.

Expected results:

- Append-only audit and sanitized execution projection retain only the validated safe `failure_code`.
- Public payloads never contain `rejection_code`, arbitrary provider error strings, provider
  routing data, credentials or internal exception material at any nesting depth.
- The same safe failure code survives PostgreSQL persistence, reload and HTTP serialization.
- Unknown or unvalidated codes fail closed rather than being persisted or projected.

Capture audit rows, reload/HTTP projections, validation result and recursive forbidden-field scan.

## Execution and approval boundary

Run all inherited and new cases at the worker's exact tested subject. Every Evaluation is appended
to the v6 history; v5 and earlier guide/history bytes remain unchanged. A candidate `PASSED` still
requires explicit repository-owner approval before the guide can authorize acceptance. This guide
does not approve code, integration, issue closure or the final feature review.
