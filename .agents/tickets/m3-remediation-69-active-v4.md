## Objective

Make production improvement selection bind the immutable M3 population and retain an auditable
vector-versus-hybrid latency trade-off.

Authoritative design: `docs/design/m3-remediation-v4.md`.
Locked guide: `.agents/manual-tests/milestone-3/69-remediation-population-latency-v3.md`.

## Acceptance

- Exact manifest paths, Git blobs, raw/content SHA-256 values, `m3-dataset-v1`, 50 sorted IDs and
  canonical case-ID digest, corpus `m3-corpus-v1`, Workspace and Chunk Set provenance are verified.
- Subset/extra/replacement/wrong path/blob/digest and corpus/Chunk Set mutations fail closed;
  caller expected IDs cannot authorize production selection.
- Every paired equal field, including generation/scorer model/prompt/policy/stochasticity,
  matches; only six retrieval-configuration fields differ.
- `m3-paired-latency-v1` uses executable `m3-latency-boundary-v1` retrieval and executor clock
  boundaries, stores both vector/hybrid values and explicit deltas, and never applies a hard cutoff.
- Public `HttpEvaluationExecutor` evidence proves exact trace correlation and no evaluation-only
  retrieval path. Tests/lint/diff/hygiene pass.

## Dependency

Child of #48. Independent frontier ticket; #67 is natively blocked by #69.
