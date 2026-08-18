# Manual Test Guide: M3 remediation R2 population and executor latency v4

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #69 / R2 — immutable population binding, exact executor seam and paired latency
- Authoritative specification: `docs/design/m3-remediation-v4.md`, R2 canonical executor seam
- Guide revision: `m3-remediation-69-v4`
- Supersedes: `m3-remediation-69-v3`
- Approved by: pending independent external review
- Approved at: pending external review

## Locked Test Cases

### TC-01: Exact manifest and case-ID canonicalization

- Purpose: bind production selection to immutable M3 data.
- Steps: verify exact paths/Git blobs/raw/content hashes/version/50 IDs/corpus values and recompute
  `sha256(UTF-8(json.dumps(sorted(case_ids), ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'))`.
- Expected results: all values match; repository-state substitutes fail.
- Evidence: capability, serialization formula/version and digest.

### TC-02: Population and paired-field mutation failures

- Purpose: reject subset/extra/replacement/wrong binding and generation/scorer drift.
- Steps: mutate each manifest/path/blob/digest/case-ID and every equal paired field; invoke canonical selector.
- Expected results: every mutation fails closed; only six retrieval fields may differ.
- Evidence: mutation matrix and reasons.

### TC-03: Canonical M3 executor identity and compatibility alias

- Purpose: prevent a second evaluation seam.
- Steps: instantiate `evals.runners.milestone_3.HttpEvaluationExecutor`; assert
  `ProductionM3Executor is HttpEvaluationExecutor`; inspect generic runner executor contract.
- Expected results: both names resolve to the same production-Q&A behavior; no direct evaluation retrieval.
- Evidence: symbol/call-path assertion and invocation digest.

### TC-04: Exact trace correlation and response-completion clock

- Purpose: enforce `(workspace_id, trace_id)` and independent latency semantics.
- Steps: inject response trace-ID mismatch and trace Workspace mismatch; record the monotonic clock
  immediately after complete HTTP response body and before trace loading/citation processing.
- Expected results: each mismatch is an observation failure; end-to-end latency uses the captured
  response-completion timestamp and excludes trace loading/scoring.
- Evidence: fault matrix, clock-boundary observation and structured failure reasons.

### TC-05: Public seam and no evaluation-only retrieval

- Purpose: prove only public Q&A is measured.
- Steps: execute through canonical executor; inspect route and structural call-path proof.
- Expected results: endpoint response supplies trace ID; no evaluation-only retrieval function is called;
  missing trace/provenance is observation failure, not score zero.
- Evidence: route/request digest and call-path assertion.

### TC-06: Pair latency projection

- Purpose: retain auditable vector/hybrid trade-offs.
- Steps: verify `m3-paired-latency-v1` and `m3-latency-boundary-v1`; recompute both deltas.
- Expected results: both independent metrics and explicit deltas reconcile; streaming=false; no hard cutoff.
- Evidence: per-case projection and recomputation.

### TC-07: Artifact hygiene and verification

- Purpose: preserve safe reproducibility.
- Steps: run focused tests, Ruff, diff checks and inventory.
- Expected results: green; raw traces/secrets absent.
- Evidence: summaries and clean worktree.

Observations append to `.agents/manual-tests/milestone-3/69-remediation-population-latency.evaluations.jsonl`.
Guide is immutable after approval.
