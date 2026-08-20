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
- Steps: verify immutable source commit
  `2a6061ad38b3b3c4f06811c7ceb8bc26af39892` contains the expected manifest Git blobs, then verify
  exact paths/Git blobs/raw/content hashes/version/50 IDs/corpus values. Assert every production
  report carries this exact value as `provenance.source_commit`, and read
  `.agents/review/m3-dataset-v1-case-ids.json` as the immutable case-ID projection. Assert the
  exact production values `workspace=evaluation-m3-v1` and
  `chunk_set_provenance_id=chunk-set-m3-v1` in both report provenance and Binding V3 data.
- Expected results: the source-commit manifest binding and projection raw UTF-8 SHA-256 are
  `sha256:d2295109d810984767b1f8157e323a2993c6773c2ccfd27e5dc61c35e5362253`; no alternate
  serialization or repository-state substitute is accepted.
- Evidence: capability, projection bytes and digest.

### TC-02: Population and paired-field mutation failures

- Purpose: reject subset/extra/replacement/wrong binding and generation/scorer drift.
- Steps: mutate each manifest/path/blob/content digest, case-ID projection, dataset/corpus/chunk-set
  provenance, `manifest_source_commit`, and every equal paired field; invoke canonical selector.
  Include a caller-supplied expected-ID override and a corpus/Chunk Set drift mutation. Record the
  six and only six permitted retrieval differences explicitly:
  `retrieval_configuration_id`, `strategy`, `fusion_policy_id`, `fusion_policy_version`,
  `lexical_policy_id`, `fts_candidate_k`.
- Expected results: every mutation fails closed; specifically, substituting a different
  `manifest_source_commit` whose manifest blob happens to be same-shaped, caller expected IDs,
  corpus drift and Chunk Set drift are rejected before selection.
- Evidence: named mutation matrix and reasons.

### TC-03: Canonical M3 executor identity and compatibility alias

- Purpose: prevent a second evaluation seam.
- Steps: instantiate `evals.runners.milestone_3.HttpEvaluationExecutor`; assert
  `ProductionM3Executor is HttpEvaluationExecutor`; inspect generic runner executor contract.
- Expected results: both names resolve to the same production-Q&A behavior; no direct evaluation retrieval.
- Evidence: symbol/call-path assertion and invocation digest.

### TC-04: Exact trace correlation and response-completion clock

- Purpose: enforce `(workspace_id, trace_id)` and independent latency semantics.
- Steps: inject response trace-ID mismatch and trace Workspace mismatch; record the monotonic clock
  immediately after complete HTTP response body and before trace loading/citation processing using
  deterministic clock injection for both canonical and generic compatibility executors.
- Expected results: each mismatch is an observation failure; end-to-end latency uses the captured
  response-completion timestamp and excludes trace loading/scoring; the observed tick order is
  request start, response completion, trace loading.
- Evidence: fault matrix, clock-boundary observation and structured failure reasons.

### TC-05: Public seam and no evaluation-only retrieval

- Purpose: prove only public Q&A is measured.
- Steps: execute through canonical executor; inspect route and structural call-path proof.
- Expected results: endpoint response supplies trace ID; no evaluation-only retrieval function is called;
  missing trace/provenance is observation failure, not score zero.
- Evidence: route/request digest and call-path assertion.

### TC-06: Pair latency projection

- Purpose: retain auditable vector/hybrid trade-offs.
- Steps: verify `m3-paired-latency-v1` and `m3-latency-boundary-v1`; inspect server phase evidence
  proving `retrieval_start` occurs after authenticated request validation and immediately before
  `AnsweringStore.retrieve_candidates`, while `retrieval_end` occurs after Evidence Selection and
  before generation. Recompute both vector/hybrid deltas and separately inspect the executor's
  response-completion boundary.
- Expected results: server retrieval latency includes exactly candidate retrieval plus Evidence
  Selection and excludes generation; end-to-end ends after the complete non-streaming response
  body; both independent metrics and explicit deltas reconcile; `streaming=false`; no hard cutoff.
- Evidence: server phase markers/call-path projection, per-case pair projection and recomputation,
  and executor clock-boundary observation.

### TC-07: Artifact hygiene and verification

- Purpose: preserve safe reproducibility.
- Steps: run focused tests, Ruff, diff checks and inventory.
- Expected results: green; raw traces/secrets absent.
- Evidence: summaries and clean worktree.

Observations append to `.agents/manual-tests/milestone-3/69-remediation-population-latency.evaluations.jsonl`.
Guide is immutable after approval.
