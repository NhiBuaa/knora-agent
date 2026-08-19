# Manual Test Guide: M3 remediation R3 final paired-claim gate v9

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #67 / R3 — guide v9 and final integrated acceptance
- Authoritative specification: `docs/design/m3-remediation-v4.md`, canonical executor seam
- Guide revision: `m3-remediation-issue-63-v9`
- Supersedes: `m3-remediation-issue-63-v8`
- Approved by: pending independent external guide review after #68/#69 integration
- Approved at: pending external review

## Locked Test Cases

### TC-01: Canonical executor and exact trace correlation

- Purpose: require the production `HttpEvaluationExecutor` seam.
- Steps: use `evals.runners.milestone_3.HttpEvaluationExecutor`; assert compatibility alias;
  inject response trace-ID and Workspace mismatches; capture response-completion clock before trace work.
- Expected results: only public Q&A path runs; mismatches are observation failures; end-to-end excludes
  trace loading/scoring and uses the response-completion boundary.
- Evidence: symbol/call-path assertion, fault matrix and clock observation.

### TC-02: Authority and exact policy provenance

- Purpose: prove independent identity/scope/response digests and sole JSON projection.
- Steps: verify the stable identity projection
  `.agents/review/identities/codex-agent-m3-final-package-review-v4-projection.json` raw
  digest `sha256:b6af13241badf537647b9c0301043fa721ea6fb42a1ab6a344ff28065076bfda`; load the
  approved closure `.agents/review/m3-remediation-v4-review-closure-v5.json`, recompute its Git
  blob/raw digest plus the scope and response projection bytes it names, and assert both response
  `subject_commit` and `reviewed_commit` equal the closure's exact package subject. Caller-supplied
  or latest/path-substituted closure data is invalid.
- Expected results: valid closure passes; generic/assertion-only/self-authored/self-approved,
  subject mismatch, mutated projection or mutated closure chains fail.
- Evidence: authority matrix and recomputation output.

### TC-03: Exact population and paired settings

- Purpose: prevent dataset/configuration cherry-picking.
- Steps: verify canonical 50-case digest and manifest bindings; compare every equal field including
  generation/scorer model/prompt/policy/stochasticity; run mutations.
- Expected results: exact values match and only retrieval configuration fields differ.
- Evidence: capability/serialization output and field matrix.

- Additional taxonomy assertion: inspect branch observations before fusion. Vector statuses are
  `ELIGIBLE`, `BELOW_THRESHOLD` or no contribution; FTS statuses are `ELIGIBLE`, `INELIGIBLE` or
  no contribution. Only fused candidates may carry `SELECTED`, `REDUNDANT_OVERLAP`,
  `BUDGET_EXCEEDED` or `ELIGIBLE_NOT_SELECTED` with `final_rank`/`fusion_score`.

### TC-04: Public citation and refusal semantics

- Purpose: score final public output only.
- Steps: execute ANSWER and REFUSAL; validate exact public answer, citation marker membership/order,
  alias mapping and same-request binding; inspect semantic scorer input.
- Expected results: semantic scorer sees only public answer/citation excerpts/source locators, never hidden
  trace chunks; ANSWER has result, REFUSAL is inapplicable; missing trace/Workspace/provenance is failure,
  not zero; insufficient-evidence-correct is non-failure refusal correctness.
- Evidence: redacted public response/citation projection and scorer-input digest.

### TC-05: Selected artifact and latency retention

- Purpose: retain metric deltas, guardrails, both latency sides/deltas, boundary version and regressions.
- Steps: inspect and recompute selected record.
- Expected results: no raw RRF threshold/cherry-pick; all evidence reconciles.
- Evidence: selected record and normalized manifest.

### TC-06: Final review/cadence/isolation

- Purpose: close only from fixed-point gate.
- Steps: run verification, fixed-point review, cadence gate and cross-Workspace isolation.
- Expected results: APPROVE zero Critical/Major, cadence ready, zero observation failures, isolation pass,
  clean main/worktrees.
- Evidence: fixed-point/review/cadence/isolation artifacts.

Observations append to `.agents/manual-tests/milestone-3/63-remediation-issue-63-v9.evaluations.jsonl`.
Guide is immutable after external approval.
