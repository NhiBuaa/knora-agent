# Manual Test Guide: M3 remediation R2 population binding and paired latency

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #69 / R2 — immutable population binding and paired latency retention
- Authoritative specification: `docs/design/m3-remediation-v2.md`, R2
- Guide revision: `m3-remediation-69-v1`
- Approved by: `NhiBuaa` under the authorized M3 remediation workflow
- Approved at: `2026-08-18T00:00:00Z`

## Prerequisites

- Environment: isolated R2 worktree at the pinned M3 remediation integration base.
- Data and state: committed `m3-dataset-v1` and matching M3 corpus/Chunk Set manifests; paired vector-only and hybrid reports from the production Q&A seam.
- Credentials and permissions: repository read access and report fixtures; no raw trace or provider secret in the repository.
- The production path uses `HttpEvaluationExecutor` and the exact `(workspace_id, trace_id)` correlation contract.

## Locked Test Cases

### TC-01: Full immutable M3 population resolves

- Purpose: prevent favorable subset selection by binding the canonical selector to the released dataset/corpus population.
- Steps:
  1. Resolve the production selection manifest from repository-root manifests.
  2. Compare its version, digest, exact sorted case IDs, corpus manifest digest and Chunk Set provenance with both reports.
  3. Call `select_production_improvement` without caller-supplied expected IDs.
- Expected results:
  - The capability identifies `m3-dataset-v1` and exactly its 50-case population.
  - Both reports bind the same immutable corpus/Chunk Set provenance and only differ in Retrieval Configuration.
  - A qualifying pair may proceed to policy evaluation.
- Evidence to capture:
  - Verified manifest capability, exact case-ID digest, report provenance and selector output.

### TC-02: Population and digest mutations fail closed

- Purpose: reject subset, extra-case, same-shaped wrong-digest and corpus/chunk-set mismatch inputs at the canonical production seam.
- Steps:
  1. Remove one case, add one case, replace one case with a same-shaped ID, and substitute a wrong dataset digest.
  2. Mutate corpus manifest or Chunk Set provenance in one report.
  3. Invoke production selection for each disposable mutation.
- Expected results:
  - Every mutation returns `NO_CLAIM`/provenance failure before metric selection.
  - Caller-provided expected case IDs cannot authorize the mutation.
- Evidence to capture:
  - Mutation matrix and structured selector reasons.

### TC-03: Non-production reduced fixture remains explicit

- Purpose: preserve focused contract tests without creating a production evaluation path.
- Steps:
  1. Use `compare_paired_reports(..., expected_case_ids=...)` with a disposable reduced fixture and `production=False` authority fixture.
  2. Attempt to route the same reduced fixture through `select_production_improvement`.
- Expected results:
  - The explicit non-production fixture seam remains usable.
  - The canonical production selector rejects the reduced population.
- Evidence to capture:
  - Fixture result and production rejection result.

### TC-04: Selected artifact retains pair-level latency evidence

- Purpose: make the vector-versus-hybrid performance trade-off auditable without inferring one latency metric from the other.
- Steps:
  1. Run a qualifying paired comparison.
  2. Inspect the selected-improvement record and its versioned latency projection.
  3. Recompute each `hybrid_minus_vector` delta from the stored values.
- Expected results:
  - For every case, vector and hybrid `retrieval_latency_ms` and `end_to_end_latency_ms` are present with independent clock-boundary metadata.
  - Explicit pair deltas reconcile exactly; no aggregate hard cutoff is introduced.
  - The selected artifact retains both sides, metric deltas, guardrails and `remaining_regressions`.
- Evidence to capture:
  - Selected record, latency projection and recomputation output.

### TC-05: Public-Q&A and trace semantics remain unchanged

- Purpose: preserve the sole production evaluation seam and exact trace correlation while adding report provenance.
- Steps:
  1. Execute paired cases through `HttpEvaluationExecutor` against the public Q&A endpoint.
  2. Correlate each response trace by exact `(workspace_id, trace_id)`.
  3. Inspect the report's retrieval configuration and latency provenance.
- Expected results:
  - No evaluation-only retrieval path is called.
  - Missing/mismatched trace is an observation failure, never a zero score.
  - `retrieval_latency_ms` and client-observed `end_to_end_latency_ms` remain independent.
- Evidence to capture:
  - Executor request/response IDs, trace provenance and report observation records (without raw traces).

### TC-06: Artifact hygiene and regression verification

- Purpose: ensure normalized reports remain reproducible and safe to commit.
- Steps:
  1. Run focused comparison/remediation tests, Ruff, and diff checks.
  2. Inspect committed artifact inventory and worktree status.
- Expected results:
  - Required tests pass.
  - Manifests, normalized reports, annotations and selected records are committed; raw traces and secrets are absent.
- Evidence to capture:
  - Test summary, lint result, artifact manifest and worktree status.

This guide is immutable after approval. Observations are appended to
`.agents/manual-tests/milestone-3/69-remediation-population-latency.evaluations.jsonl`.
