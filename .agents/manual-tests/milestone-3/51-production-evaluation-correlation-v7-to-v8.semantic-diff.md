# Semantic diff: issue-51-v7 → issue-51-v8

## Changed

- Replaces the scalar binding field `production_chunk_set_id` with `source_bindings`, an exact
  per-`source_key` mapping of persisted Document Version and Chunk Set UUIDs.
- Requires binding coverage to equal the `m3-corpus-v1` source-key set exactly; missing, extra or
  duplicate source entries are setup/observation failures.
- TC-01 and TC-02 select a binding entry by candidate `source_key`, then require the candidate
  persisted Chunk Set UUID (and, where projected, Document Version UUID) to match that entry.
- Adds explicit negative cases for unknown source, wrong per-source UUID/version, and malformed
  mapping coverage; rejects unordered UUID-set membership and current/latest fallback.

## Unchanged

- The production model: one `ChunkSet.id` persisted instance per Document Version derivation.
- `chunk_set_provenance_id = chunk-set-m3-v1` as the stable corpus/evaluation scope.
- Canonical gold/candidate identity `(chunk_set_provenance_id, source_key, ordinal)`.
- Recall@8, uncut MRR, macro averaging, denominator, citation, semantic-scoring and latency
  semantics; bootstrap and resolver boundaries; no manual acceptance execution.
