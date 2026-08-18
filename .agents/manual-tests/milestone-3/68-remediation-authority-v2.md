# Manual Test Guide: M3 remediation R1 authority chain

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #68 / R1 — independent authority chain and sole-source policy projection
- Authoritative specification: `docs/design/m3-remediation-v3.md`, R1
- Guide revision: `m3-remediation-68-v2`
- Supersedes: `m3-remediation-68-v1`
- Approved by: `NhiBuaa` under the authorized M3 remediation workflow
- Approved at: `2026-08-18T00:00:00Z`

## Prerequisites

- Isolated R1 worktree from the pinned remediation integration base.
- Historical authority artifacts remain immutable. New authority artifacts are append-only.
- A reviewer artifact with a concrete task identity, source record, identity digest, subject
  commit/blob, complete-scope digest, seal and closure is available.

## Locked Test Cases

### TC-01: Historical generic/self-attested chain fails closed

- Purpose: reject the old `independent-reviewer-id`/`NhiBuaa` self-attested chain.
- Steps: validate the historical authority archive and closure in production mode.
- Expected results: `AUTHORITY_VALIDATION_FAILURE`; no policy outcome or quality score.
- Evidence: validator JSON, source-author projection, and historical artifact digests.

### TC-02: Concrete independent reviewer chain passes

- Purpose: prove the new authority binds independently verifiable reviewer provenance.
- Steps: validate reviewer `reviewer_id`, `identity_kind`, `source_record`, `identity_digest`,
  subject commit/blob, complete-scope digest, response digest, seal and closure.
- Expected results: reviewer differs from source-commit author and approver; all bindings match;
  production validation returns `APPROVED_EFFECTIVE`.
- Evidence: review artifact, sealed response/closure, Git author projection and validator result.

### TC-03: Identity provenance mutations fail closed

- Purpose: prevent payload-only independence assertions or generic identities.
- Steps: mutate reviewer ID, identity kind, source record, identity digest, subject commit/blob,
  scope digest, reviewer/approver separation flags, response digest and closure values one at a time.
- Expected results: every mutation returns `AUTHORITY_VALIDATION_FAILURE` before policy evaluation.
- Evidence: complete mutation matrix and structured reasons.

### TC-04: Policy projection is sole normative source

- Purpose: reject projection mutation, unknown/missing fields and duplicated value fallback.
- Steps: mutate/add/remove projection fields and bind wrong Git blob/digest; inspect production source
  and run validator.
- Expected results: all mutations fail closed; no duplicated full policy value map is used.
- Evidence: mutation matrix, source inspection and validator results.

### TC-05: Caller overrides and fixture boundary

- Purpose: keep authority/policy overrides outside production.
- Steps: pass caller authority/policy in production; invoke explicit fixture with `production=False`.
- Expected results: production overrides fail; fixture succeeds only in explicit non-production mode.
- Evidence: override results and fixture result.

### TC-06: Artifact hygiene and regression verification

- Purpose: preserve historical evidence and prevent secret/raw-trace publication.
- Steps: run focused authority/remediation tests, Ruff, diff checks and artifact inventory.
- Expected results: tests pass; only normalized authority/review metadata is committed.
- Evidence: test summary, lint/diff result, artifact manifest and clean worktree.

Observations append to `.agents/manual-tests/milestone-3/68-remediation-authority.evaluations.jsonl`.
This guide is immutable after approval.
