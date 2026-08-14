# Semantic diff: issue-51-v8 → issue-51-v9

## Changed

- Adds corpus-closure preflight before measured Q&A: the complete retrieval-eligible active corpus
  must have exactly the `m3-corpus-v1` source-key set, with exactly one active manifest-matching
  Document Version and corresponding Chunk Set per source.
- Makes `production_document_version_id` a mandatory provenance gate. The reader projects it and
  the evaluator validates exact `(source_key, document_version_id, chunk_set_id)` equality against
  one per-source binding entry. An equivalent mandatory reader-side relation is allowed only when
  direct trace projection is unavailable; skipping version validation is prohibited.
- Adds setup/observation failures for extra active corpus source/document, missing source,
  duplicate/multiple active source/version, and missing/wrong version provenance before scoring.

## Unchanged

- Per-source Binding V2 direction, production data model, canonical
  `(chunk_set_provenance_id, source_key, ordinal)`, retrieval metrics/denominator, citation,
  semantic and latency semantics, bootstrap/resolver boundaries, and no manual acceptance run.
