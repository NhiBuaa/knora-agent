# Manual Test Guide: M3 remediation R1 authority chain

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #68 / R1 — independent authority chain and sole-source policy projection
- Authoritative specification: `docs/design/m3-remediation-v2.md`, R1
- Guide revision: `m3-remediation-68-v1`
- Approved by: `NhiBuaa` under the authorized M3 remediation workflow
- Approved at: `2026-08-18T00:00:00Z`

## Prerequisites

- Environment: isolated R1 worktree at the pinned M3 remediation integration base.
- Data and state: historical authority artifacts from `2a1da89521b6c577800b4bbdb2688209086ac14e`; new authority revision generated append-only.
- Credentials and permissions: repository read access, Git object access, and no provider secret.
- Required external review: a concrete reviewer identity and sealed artifact covering the exact source commit, policy projection blob/digest, and complete claim-rule scope.

## Locked Test Cases

### TC-01: Current self-attested chain fails closed

- Purpose: prevent the historical `NhiBuaa` reviewer/approver and source-author chain from becoming effective without independent evidence.
- Steps:
  1. Run the production authority validator against the historical v2 approval/seal/closure.
  2. Record the structured result and reason.
- Expected results:
  - Status is `AUTHORITY_VALIDATION_FAILURE`.
  - The result identifies missing/unverifiable reviewer independence; it never returns an improvement policy outcome.
- Evidence to capture:
  - Validator JSON, historical artifact digests, and focused test ID.

### TC-02: Independently reviewed authority revision passes

- Purpose: prove the new authority can become effective only from a separately identified review artifact.
- Steps:
  1. Resolve the new sealed authority archive and closure.
  2. Validate its external-review artifact against the exact source commit, policy blob/digest, and full scope.
  3. Run `canonical_authority_validation` in production mode.
- Expected results:
  - Reviewer identity is concrete and differs from both source-commit author and approver.
  - All bound blobs, digests, seal and closure match.
  - Status is `APPROVED_EFFECTIVE`.
- Evidence to capture:
  - New authority artifact paths/digests, reviewer identity record, validator result, and source commit author projection.

### TC-03: Projection mutation and schema failures reject

- Purpose: keep the approved JSON projection as the sole normative source and fail closed on drift.
- Steps:
  1. Mutate one policy value, add an unknown key, remove a required key, and change the bound Git blob/digest in disposable copies.
  2. Validate each disposable authority bundle.
- Expected results:
  - Every mutation returns `AUTHORITY_VALIDATION_FAILURE`.
  - No duplicated Python policy map is consulted to accept a mutated projection.
- Evidence to capture:
  - Mutation matrix and structured failure reasons.

### TC-04: Reviewer/source-author/approver separation is enforced

- Purpose: prevent self-authored and self-approved authority from satisfying the independence precondition.
- Steps:
  1. Substitute the source-commit author as reviewer.
  2. Substitute the reviewer as approver.
  3. Set the legacy `reviewer_was_author` assertion to false without changing the actual source author.
- Expected results:
  - Each chain is rejected with an authority validation failure.
  - A payload assertion cannot override repository-derived author/identity evidence.
- Evidence to capture:
  - Identity mutation fixtures and validator results.

### TC-05: Caller authority/policy overrides remain forbidden

- Purpose: preserve the production boundary between the sealed authority and focused test fixtures.
- Steps:
  1. Pass a caller-supplied authority bundle in production mode.
  2. Pass a caller-supplied policy projection/claim rule.
  3. Invoke the explicit fixture seam with `production=False`.
- Expected results:
  - Production override attempts fail closed.
  - The fixture seam is usable only when explicitly non-production.
- Evidence to capture:
  - Override responses and fixture invocation result.

### TC-06: Artifact hygiene and regression verification

- Purpose: ensure authority remediation does not commit raw traces or secrets and remains compatible with existing claim tests.
- Steps:
  1. Run focused authority/remediation tests, Ruff, and diff checks.
  2. Inspect changed artifact inventory and Git status.
- Expected results:
  - Required tests pass.
  - Only normalized authority/review metadata is committed; no raw trace, credential, or provider secret is present.
- Evidence to capture:
  - Test summary, lint result, artifact manifest and worktree status.

This guide is immutable after approval. Observations are appended to
`.agents/manual-tests/milestone-3/68-remediation-authority.evaluations.jsonl`.
