# Semantic diff: issue-51-v11 → issue-51-v12

## Changed

- Moves authoritative closure and Binding V3/configuration snapshot to after exclusive seal
  acquisition; pre-seal corpus materialization is permitted but cannot authorize measurement.
- Defines seal as evaluation control-plane/orchestration ownership. No production-wide retrofit of
  evaluation-specific checks is required; topology, restricted actors/credentials, exclusive
  ownership or existing centralized guard may provide the no-mutation guarantee.
- TC-01 validates only supported mutation paths and actors present in the evaluation topology,
  while post-run drift verification remains mandatory defense-in-depth.

## Unchanged

- Pre-start auth lifecycle, Binding V3/triple provenance gate, canonical identity, metrics,
  citation, semantic scorer, latency boundaries, post-run invalidation and manual-acceptance state.
