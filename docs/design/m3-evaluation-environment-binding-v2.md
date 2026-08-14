# M3 evaluation environment binding V2

V1 remains immutable. V2 resolves its scalar persisted Chunk Set UUID into exact per-source
production provenance without changing the production model: a Chunk Set remains one derivation
of one Document Version.

## Binding schema

```json
{
  "schema_version": 2,
  "dataset_manifest_identity": "m3-dataset-v1",
  "corpus_manifest_identity": "m3-corpus-v1",
  "chunk_set_provenance_id": "chunk-set-m3-v1",
  "workspace_id": "evaluation-m3-v1",
  "retrieval_configuration_id": "retrieval-m3-rrf-v1",
  "source_bindings": [
    {
      "source_key": "support/refund-policy",
      "production_document_version_id": "<persisted DocumentVersion UUID>",
      "production_chunk_set_id": "<persisted ChunkSet UUID>"
    }
  ]
}
```

`source_bindings` contains exactly one entry for each `source_key` in `m3-corpus-v1`: it has no
missing, extra, or duplicate sources. The binding does not accept an unordered UUID set and does
not derive entries from current/latest/name lookup.

## Verification and projection

`EvaluationEnvironmentBootstrap` uses supported production/application seams to verify, for every
manifest source, its active manifest-matching Document Version and the persisted Chunk Set UUID
derived from that version before it publishes V2. The persisted UUIDs are redacted as necessary in
evidence but retained in the binding artifact.

When reading a correlated trace, the evaluator first uses the candidate `source_key` to select the
single binding entry. It then requires exact equality of the candidate persisted `chunk_set_id` and
the entry `production_chunk_set_id`; the candidate's persisted Document Version must also agree
with the entry when trace projection supplies it. Unknown source, wrong UUID/version, duplicate or
incomplete binding, and manifest-provenance mismatch are setup/observation failures. There is no
fallback, inference, or unordered-membership test.

Only after this gate passes does the evaluator project the candidate to the portable identity
`(chunk_set_provenance_id, source_key, ordinal)`. Persisted Document Version and Chunk Set UUIDs
remain environment provenance; they do not enter gold matching.

The bootstrap remains control-plane only, and `RetrievalConfigurationResolver` remains the
production Q&A composition seam. Neither changes the measured Q&A path.
