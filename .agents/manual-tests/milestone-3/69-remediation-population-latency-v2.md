# Manual Test Guide: M3 remediation R2 population binding and paired latency

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #69 / R2 — immutable population binding and paired latency retention
- Authoritative specification: `docs/design/m3-remediation-v3.md`, R2
- Guide revision: `m3-remediation-69-v2`
- Supersedes: `m3-remediation-69-v1`
- Approved by: `NhiBuaa` under the authorized M3 remediation workflow
- Approved at: `2026-08-18T00:00:00Z`

## Prerequisites

- Isolated R2 worktree from the pinned remediation integration base.
- Immutable manifest paths/blobs/digests and exact case-ID digest from the design are available.
- Paired reports were produced by `HttpEvaluationExecutor` against the public Q&A endpoint.

## Locked Test Cases

### TC-01: Exact immutable M3 capability resolves

- Purpose: bind production selection to the release, not mutable repository shape.
- Steps: resolve dataset/corpus manifests and verify path, Git blob/commit, file SHA-256,
  dataset content digest, version, exact 50 sorted IDs/digest, corpus version and Chunk Set provenance.
- Expected results: all exact values match design v3; no caller replacement is accepted.
- Evidence: verified capability and manifest digest projection.

### TC-02: Population/path/blob/digest mutations fail closed

- Purpose: reject subset, extra-case, replacement, wrong path/blob/digest and corpus/Chunk Set drift.
- Steps: mutate each manifest path/blob/digest, dataset content digest, case-ID digest and corpus
  provenance; remove/add/substitute cases; invoke canonical production selection.
- Expected results: every mutation is `NO_CLAIM`/provenance failure before metric selection.
- Evidence: complete mutation matrix and structured selector reasons.

### TC-03: Paired field-level invariants are enforced

- Purpose: ensure generation/scorer settings are fixed and only retrieval configuration differs.
- Steps: mutate each of generation configuration, scorer configuration/model/prompt/policy/
  stochasticity, embedding/chunking, evaluation commit and artifact schema in one report.
- Expected results: each mutation fails paired provenance; only the six listed retrieval fields may differ.
- Evidence: field mutation matrix and comparison result.

### TC-04: Non-production reduced fixture remains explicit

- Purpose: keep focused tests without a production vector-only evaluation path.
- Steps: use reduced `expected_case_ids` only through `compare_paired_reports` with explicit
  non-production fixture authority; route the same fixture through `select_production_improvement`.
- Expected results: fixture seam works; canonical production selector rejects it.
- Evidence: both results and call-path proof.

### TC-05: Public Q&A executor is the sole evaluation seam

- Purpose: prove no evaluation-only retrieval path and exact trace correlation.
- Steps: run paired requests through `HttpEvaluationExecutor`; capture route/request evidence,
  production call-path/structural assertion and exact `(workspace_id, trace_id)` correlation.
- Expected results: endpoint response supplies trace ID; no direct evaluation retrieval seam is
  invoked; missing/mismatched trace is an observation failure, never zero quality.
- Evidence: executor invocation digest, route record, structural call-path assertion and trace
  provenance (without raw traces).

### TC-06: Selected artifact retains independent latency and regressions

- Purpose: make vector-versus-hybrid trade-offs auditable.
- Steps: run a qualifying pair; inspect `m3-paired-latency-v1`; recompute per-case deltas.
- Expected results: vector/hybrid retrieval and end-to-end latency values remain independent,
  deltas reconcile, clock boundaries are explicit, and selected record retains both sides,
  guardrails, metric deltas and `remaining_regressions`; no hard threshold is applied.
- Evidence: selected record, latency projection and recomputation output.

### TC-07: Artifact hygiene and regression verification

- Purpose: preserve reproducibility and safe publication boundaries.
- Steps: run focused tests, Ruff, diff checks and committed artifact inventory.
- Expected results: tests pass; manifests/reports/annotations/selected records are committed;
  raw traces and secrets are absent.
- Evidence: test summary, lint/diff result, manifest and clean worktree.

Observations append to `.agents/manual-tests/milestone-3/69-remediation-population-latency.evaluations.jsonl`.
This guide is immutable after approval.
