# Manual Test Guide: M3 remediation R3 final paired-claim gate v8

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #67 / R3 — guide v8 and final integrated acceptance
- Authoritative specification: `docs/design/m3-remediation-v4.md`, R3
- Guide revision: `m3-remediation-issue-63-v8`
- Supersedes: `m3-remediation-issue-63-v7`
- Approved by: pending independent external guide review after #68/#69 integration
- Approved at: pending external review

## Prerequisites

- Native blockers #68 and #69 are closed with accepted evidence and integrated commits.
- Current fixed point and design v4 are bound; v6/v7 guides and histories remain immutable.
- Evaluation uses `HttpEvaluationExecutor` against the public Q&A endpoint only.

## Locked Test Cases

### TC-01: Authority and exact policy provenance

- Purpose: prove independent identity and sole-source policy projection.
- Steps: verify identity record/blob/raw digest, identity/scope/response canonical digests, source
  author/approver separation, policy blob/digest, seal and closure; run mutation negatives.
- Expected results: valid chain passes; generic/self-authored/self-approved/mutated chains fail closed.
- Evidence: authority artifacts and recomputation matrix.

### TC-02: Exact immutable population and paired settings

- Purpose: prevent metric cherry-picking and configuration drift.
- Steps: verify exact manifest paths/blobs/raw/content digests, canonical 50-case digest, corpus/Chunk Set
  values; compare every equal field including generation/scorer model/prompt/policy/stochasticity; run
  subset/replacement/wrong-digest/field mutations.
- Expected results: exact population and equal fields match; only retrieval configuration fields differ;
  mutations fail closed.
- Evidence: capability, serialization command, field matrix and selector result.

### TC-03: Public answer/citation and refusal semantics

- Purpose: evaluate final public output, not hidden trace evidence.
- Steps: execute representative `ANSWER` and insufficient-evidence `REFUSAL` requests through the public
  endpoint. For the same response, validate exact public `answer` text, citation marker membership/order,
  citation alias mapping and source locator/excerpt against the correlated public citations. Confirm the
  trace ID comes directly from that response and workspace matches exactly.
- Expected results: deterministic citation correctness uses only that request's public answer/citations;
  semantic scorer receives only public answer plus public citation excerpts/source locators and never
  hidden retrieved chunks. `ANSWER` has semantic citation result; `REFUSAL` is explicitly inapplicable;
  `INSUFFICIENT_EVIDENCE_CORRECT` is non-failure refusal correctness. Missing trace, Workspace mismatch
  or incomplete provenance is observation/execution failure, not score zero.
- Evidence: redacted public response/citation projection, scorer input digest and correlation/provenance
  failure probes.

### TC-04: Selected artifact retention and improvement decision

- Purpose: prove pre-declared, auditable improvement.
- Steps: inspect metric deltas, guardrails, vector/hybrid `m3-paired-latency-v1` values/deltas, boundary
  version and `remaining_regressions`; recompute all projections.
- Expected results: values reconcile; no raw RRF threshold or post-run cherry-pick; every trade-off and
  regression is retained.
- Evidence: selected record, pair projection and normalized manifest.

### TC-05: Sole production evaluation seam

- Purpose: prove no evaluation-only retrieval path.
- Steps: inspect executor route/request digest and structural call-path proof from public Q&A to
  `AnswerQuestion` to production `AnsweringStore.retrieve_candidates`; assert no direct eval retrieval.
- Expected results: only the production seam is used; trace is observation-only.
- Evidence: invocation digest, route/call-path assertion and redacted request metadata.

### TC-06: Final review, cadence and isolation gate

- Purpose: close M3 only at a fixed-point gate.
- Steps: run verification, fixed-point review, cadence evidence validator and cross-Workspace isolation.
- Expected results: review `APPROVE` with zero Critical/Major; cadence `ready`; observation failures zero;
  isolation pass; default branch/worktrees clean.
- Evidence: fixed-point descriptor, review artifacts, cadence digest and status snapshots.

Observations append to `.agents/manual-tests/milestone-3/63-remediation-issue-63-v8.evaluations.jsonl`.
Guide is immutable after external approval.
