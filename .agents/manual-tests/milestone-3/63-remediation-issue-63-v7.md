# Manual Test Guide: M3 remediation R3 final paired-claim gate

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #67 / R3 — guide v7 and final integrated acceptance
- Authoritative specification: `docs/design/m3-remediation-v3.md`, R3
- Guide revision: `m3-remediation-issue-63-v7`
- Supersedes: `.agents/manual-tests/m3-remediation-issue-63-v6.md`
- Approved by: pending external guide review and authorized M3 remediation workflow
- Approved at: pending external review

## Prerequisites

- Native blockers #68 and #69 are closed; their accepted evidence and exact integrated commits
  are bound in the feature ledger.
- The final guide is reviewed against the exact integrated fixed point and current M3 manifests.
- Production evaluation uses `HttpEvaluationExecutor` and the public Q&A endpoint; raw traces and
  credentials remain in authorized persistence only.

## Locked Test Cases

### TC-01: Authority and policy projection provenance

- Purpose: prove the selected claim uses a concrete independent reviewer and the sole approved
  JSON policy projection.
- Steps: inspect the external-review artifact, source-author projection, reviewer/approver
  separation, policy blob/digest, seal and closure; run authority mutation negatives.
- Expected results: independent chain passes; generic/self-authored/self-approved/mutated chains
  fail closed before selection.
- Evidence: authority review/seal/closure records and validator matrix.

### TC-02: Exact immutable population and paired settings

- Purpose: prevent metric cherry-picking and configuration drift.
- Steps: inspect exact manifest paths/blobs/digests, dataset content and case-ID digest, corpus/
  Chunk Set provenance, and every equal paired field including generation/scorer model/prompt/
  policy/stochasticity. Run subset, replacement and wrong-digest negatives.
- Expected results: exact 50-case population and all equal fields match; only retrieval configuration
  fields differ; every mutation fails closed.
- Evidence: manifest capability, field-level comparison matrix and selector output.

### TC-03: Public seam and refusal applicability

- Purpose: preserve evaluation seam and correct scoring semantics.
- Steps: execute representative `ANSWER` and `REFUSAL` cases through public Q&A; correlate exact
  `(workspace_id, trace_id)`; inspect citations and semantic scorer inputs.
- Expected results: `ANSWER` has a semantic citation result from public answer/citations only;
  `REFUSAL` records semantic citation as inapplicable, not missing; insufficient-evidence-correct
  is non-failure refusal correctness.
- Evidence: public response/citation projection, scorer provenance and trace correlation record.

### TC-04: Selected artifact retention and improvement decision

- Purpose: prove the final selected record is auditable and pre-declared.
- Steps: inspect metric deltas, guardrails, vector/hybrid `m3-paired-latency-v1` values and
  explicit deltas, clock boundaries, and `remaining_regressions`; recompute projections.
- Expected results: values reconcile; no raw RRF threshold or post-run cherry-pick is used; every
  latency trade-off and remaining regression is retained.
- Evidence: selected-improvement record, pair projection and normalized report manifest.

### TC-05: No evaluation-only retrieval path

- Purpose: prove the accepted reports came from the production Q&A seam only.
- Steps: inspect executor route/request evidence and structural call-path proof; assert no direct
  evaluation retrieval function is invoked.
- Expected results: only public Q&A → `AnswerQuestion` → production `AnsweringStore.retrieve_candidates`
  path is used; trace is observation-only.
- Evidence: invocation digest, route/call-path assertion and redacted request metadata.

### TC-06: Final review, cadence and isolation gate

- Purpose: close M3 only from a fixed-point quality gate.
- Steps: run focused/full verification, fixed-point code review, cadence evidence validator and
  cross-Workspace isolation checks.
- Expected results: review `APPROVE` with zero Critical/Major findings; cadence `ready`; observation
  failures zero; isolation pass/fail contract passes; default branch and worktrees are clean.
- Evidence: fixed-point descriptor, review artifacts, cadence evidence digest and status snapshots.

Observations append to `.agents/manual-tests/milestone-3/63-remediation-issue-63-v7.evaluations.jsonl`.
This guide remains immutable after external review approval.
