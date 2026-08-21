# Manual Test Guide: M3 remediation R3 final paired-claim gate v9

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #67 / R3 — guide v9 and final integrated acceptance
- Authoritative specification: `docs/design/m3-remediation-v4.md`, canonical executor seam
- Guide revision: `m3-remediation-issue-63-v9`
- Supersedes: `m3-remediation-issue-63-v8`
- Approved by: NhiBuaa (explicit repository-owner authorization in the active M3 completion task)
- Approved at: 2026-08-20; immutable after external review and this approval

## Locked Test Cases

### TC-01: Canonical executor and exact trace correlation

- Purpose: require the production `HttpEvaluationExecutor` seam.
- Steps: use `evals.runners.milestone_3.HttpEvaluationExecutor`; assert compatibility alias;
  record the HTTP method, public Q&A route, request Workspace and response trace ID; prove the
  executor sends the request to the public Q&A endpoint and reads the exact `(workspace_id,
  trace_id)` trace. Inject response trace-ID and Workspace mismatches; capture response-completion
  clock before trace work; inspect the call path to prove no evaluation-only retrieval function is
  invoked.
- Expected results: route/request evidence identifies the public Q&A seam; only that path runs;
  mismatches are observation failures; end-to-end excludes trace loading/scoring and uses the
  response-completion boundary.
- Evidence: route/request projection or digest, symbol/call-path assertion, no-evaluation-only
  retrieval proof, fault matrix and clock observation.

### TC-02: Authority and exact policy provenance

- Purpose: prove independent identity/scope/response digests and sole JSON projection.
- Steps: verify the stable identity projection
  `.agents/review/identities/codex-agent-m3-final-package-review-v4-projection.json` raw
  digest `sha256:b6af13241badf537647b9c0301043fa721ea6fb42a1ab6a344ff28065076bfda`; load the
  approved closure `.agents/review/m3-remediation-v4-review-closure-final.json`, recompute its Git
  blob/raw digest plus the scope and response projection bytes it names, and assert both response
  `subject_commit` and `reviewed_commit` equal the closure's exact package subject. Caller-supplied
  or latest/path-substituted closure data is invalid. Load the exact approved policy projection
  `docs/design/m3-improvement-claim-rule-v1.policy.json`, recompute its bound Git blob/raw digest,
  and inspect `evals/runners/m3_claim_authority.py` to prove production reads that projection
  rather than a duplicated full value-level policy map; compatibility fixture exports are not
  production authority.
- Expected results: valid closure passes; generic/assertion-only/self-authored/self-approved,
  subject mismatch, mutated projection or mutated closure chains fail.
- Evidence: authority matrix and recomputation output.

### TC-03: Exact population and paired settings

- Purpose: prevent dataset/configuration cherry-picking.
- Steps: verify canonical 50-case digest and manifest bindings; compare every equal field including
  generation/scorer model/prompt/policy/stochasticity. The only permitted differences are exactly
  `retrieval_configuration_id`, `strategy`, `fusion_policy_id`, `fusion_policy_version`,
  `lexical_policy_id` and `fts_candidate_k`; record a field matrix for both reports. Run one
  mutation for each equal field and verify the comparator fails closed.
- Expected results: exact values match and only those six retrieval configuration fields differ;
  every equal-field mutation fails closed.
- Evidence: capability/serialization output and field matrix.

- Additional taxonomy assertion: inspect branch observations before fusion. Vector statuses are
  `ELIGIBLE`, `BELOW_THRESHOLD` or no contribution; FTS statuses are `ELIGIBLE`, `INELIGIBLE` or
  no contribution. Only fused candidates may carry `SELECTED`, `REDUNDANT_OVERLAP`,
  `BUDGET_EXCEEDED` or `ELIGIBLE_NOT_SELECTED` with `final_rank`/`fusion_score`; a fused
  `BUDGET_EXCEEDED` candidate must distinguish `decision_reason=TOKEN_BUDGET` from
  `decision_reason=CHUNK_COUNT_LIMIT` using persisted typed budget evidence (configured chunk/token
  limits, selected counts/tokens, candidate token count and total). The reader must bind candidate
  token count to the persisted chunk and reject a reason that does not match the actual condition.
  Negative cases swap both budget reasons, mutate a pre-fusion status into a fused decision, assign
  `final_rank`/`fusion_score` to a branch loss, or swap the two budget reasons; each must fail
  closed. Pre-fusion statuses never receive fused rank/score.

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
- Steps: inspect `selected_improvement.latency_tradeoffs`, `guardrails` and
  `remaining_regressions`. For each case and both metrics, recompute
  `hybrid_minus_vector[metric][case_id] = hybrid[metric][case_id] - vector[metric][case_id]`;
  verify `version=m3-paired-latency-v1`, `clock_boundary_version=m3-latency-boundary-v1`,
  `streaming=false`, and that both vector and hybrid observations are retained.
- Expected results: no raw RRF threshold/cherry-pick; both latency sides, explicit deltas,
  guardrails and all remaining regressions reconcile exactly.
- Evidence: selected record and normalized manifest.

### TC-06: Final review/cadence/isolation

- Purpose: close only from fixed-point gate.
- Steps: run verification, fixed-point review, cadence gate and cross-Workspace isolation.
- Expected results: APPROVE zero Critical/Major, cadence ready, zero observation failures, isolation pass,
  clean main/worktrees.
- Evidence: fixed-point/review/cadence/isolation artifacts.

Observations append to `.agents/manual-tests/milestone-3/63-remediation-issue-63-v9.evaluations.jsonl`.
Guide is immutable after external approval.
