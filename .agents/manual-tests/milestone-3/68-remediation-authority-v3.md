# Manual Test Guide: M3 remediation R1 authority chain v3

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #68 / R1 — independent authority chain and sole-source policy projection
- Authoritative specification: `docs/design/m3-remediation-v4.md`, R1
- Guide revision: `m3-remediation-68-v3`
- Supersedes: `m3-remediation-68-v2`
- Approved by: pending independent external guide review
- Approved at: pending external review

## Prerequisites

- Historical authority artifacts remain immutable.
- Identity record `.agents/review/identities/codex-agent-m3-final-package-review-v2.json`
  is committed and its Git blob/raw digest are available.
- Canonical serialization and identity/scope/response digest formulas are available from design v4.

## Locked Test Cases

### TC-01: Historical generic/self-attested chain fails closed

- Purpose: reject `independent-reviewer-id` and the self-authored/self-approved historical chain.
- Steps: validate the historical archive/closure in production mode and project the source author.
- Expected results: `AUTHORITY_VALIDATION_FAILURE`; no policy outcome.
- Evidence: result, source-author projection and historical digests.

### TC-02: Identity record and canonical digest verify

- Purpose: make reviewer identity independently reproducible.
- Steps: load the committed identity record; recompute its Git blob/raw SHA-256 and
  `sha256(canonical_json({reviewer_id,identity_kind,task_path,provider,source_authority}))`.
- Expected results: all values match the review artifact; generic IDs, missing source record or
  unknown identity kind fail.
- Evidence: identity record, blob/hash projection and recomputation output.

### TC-03: Independent review scope/response chain passes

- Purpose: prove exact subject and complete-scope review.
- Steps: load the approved closure `.agents/review/m3-remediation-v4-review-closure-v2.json`,
  recompute its Git blob/raw digest and the scope/response projection bytes it names, then verify
  the source commit/blob, seal and closure. Assert both response `subject_commit` and
  `reviewed_commit` equal the closure's exact package subject; a response that reviewed a
  descendant or parent is invalid even when its verdict is `APPROVE`. Caller-supplied or latest
  closure paths are invalid.
- Expected results: reviewer differs from source author and approver; status is `APPROVED_EFFECTIVE`.
- Evidence: review artifact, sealed response/closure, scope/hash recomputation and validator result.

### TC-04: Identity/projection mutations fail closed

- Purpose: reject assertion-only or mutated authority.
- Steps: mutate identity ID/kind/source/digest, subject/scope/response, reviewer/approver flags,
  policy fields and bound Git blob/digest.
- Expected results: every mutation returns `AUTHORITY_VALIDATION_FAILURE` before policy evaluation.
- Evidence: complete mutation matrix and reasons.

### TC-05: Caller override and fixture boundary

- Purpose: keep production authority sealed and focused fixtures explicit.
- Steps: pass caller authority/policy in production; invoke fixture only with `production=False`.
- Expected results: production overrides fail; explicit fixture path remains usable.
- Evidence: invocation/results and call-path record.

### TC-06: Artifact hygiene and verification

- Purpose: retain only normalized authority metadata.
- Steps: run focused tests, Ruff, diff checks and artifact inventory.
- Expected results: green verification; no raw traces, credentials or secrets committed.
- Evidence: test/lint/diff summary and clean worktree.

Observations append to `.agents/manual-tests/milestone-3/68-remediation-authority.evaluations.jsonl`.
Guide is immutable after approval.
