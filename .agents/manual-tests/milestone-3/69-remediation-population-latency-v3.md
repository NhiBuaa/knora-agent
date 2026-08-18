# Manual Test Guide: M3 remediation R2 population binding and paired latency v3

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #69 / R2 — immutable population binding and paired latency retention
- Authoritative specification: `docs/design/m3-remediation-v4.md`, R2
- Guide revision: `m3-remediation-69-v3`
- Supersedes: `m3-remediation-69-v2`
- Approved by: pending independent external guide review
- Approved at: pending external review

## Locked Test Cases

### TC-01: Exact manifest and case-ID canonicalization

- Purpose: bind production to immutable M3 files and make the case digest independently reproducible.
- Steps: verify exact paths/Git blobs/raw SHA-256/content SHA-256/version/50 IDs/corpus values; recompute
  `sha256(canonical_json(sorted(case_ids)))` using UTF-8 compact JSON plus one newline.
- Expected results: all values match design v4; no repository-state substitute is accepted.
- Evidence: capability projection, command/serialization version and recomputed digest.

### TC-02: Manifest/population mutations fail closed

- Purpose: reject subset, extra, replacement, wrong path/blob/digest and corpus/Chunk Set drift.
- Steps: mutate each binding and invoke canonical production selection.
- Expected results: every mutation is `NO_CLAIM`/provenance failure before metrics.
- Evidence: mutation matrix and selector reasons.

### TC-03: Field-level paired equality

- Purpose: prevent generation/scorer/configuration cherry-picking.
- Steps: mutate generation configuration, scorer configuration/model/prompt/policy/stochasticity,
  embedding/chunking, evaluation commit or report schema one at a time.
- Expected results: each mutation fails; only the six retrieval configuration fields are allowed to differ.
- Evidence: field matrix and comparison output.

### TC-04: Explicit non-production fixture seam

- Purpose: preserve focused reduced tests without a production evaluation path.
- Steps: use reduced IDs only in `compare_paired_reports` with `production=False`; attempt canonical
  production selection with the same fixture.
- Expected results: fixture succeeds; production rejects.
- Evidence: both results and call-path proof.

### TC-05: Public Q&A and no evaluation-only retrieval path

- Purpose: prove the production seam and exact trace contract.
- Steps: run paired requests through `HttpEvaluationExecutor`; capture route/request invocation,
  structural call-path assertion and exact `(workspace_id, trace_id)` correlation.
- Expected results: no direct evaluation retrieval function is invoked; missing trace, Workspace
  mismatch or incomplete provenance is an observation failure, never zero quality.
- Evidence: executor invocation digest, route/call-path assertion and redacted provenance.

### TC-06: Executable independent latency boundaries

- Purpose: make latency reproducible and preserve metric independence.
- Steps: verify `m3-latency-boundary-v1`: retrieval starts after auth validation before
  `AnsweringStore.retrieve_candidates` and ends after Evidence Selection before generation; end-to-end
  starts at executor `perf_counter` immediately before HTTP send and ends after complete non-streaming
  response body. Recompute pair deltas.
- Expected results: vector/hybrid values and explicit deltas reconcile; `streaming=false`; no metric is
  inferred from the other and no hard threshold is applied.
- Evidence: boundary version, per-case projection and recomputation output.

### TC-07: Artifact hygiene and verification

- Purpose: preserve reproducibility and safe publication.
- Steps: run focused tests, Ruff, diff checks and inventory.
- Expected results: green verification; raw traces/secrets absent.
- Evidence: test/lint/diff summary, manifest and clean worktree.

Observations append to `.agents/manual-tests/milestone-3/69-remediation-population-latency.evaluations.jsonl`.
Guide is immutable after approval.
