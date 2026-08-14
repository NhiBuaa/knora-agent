# M3 evaluation environment binding V3

V1 and V2 remain immutable. V3 retains V2's per-source binding and makes corpus closure and
Document Version provenance mandatory preconditions of measured Q&A.

## Binding schema

```json
{
  "schema_version": 3,
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

`source_bindings` is a map encoded as a list: it contains exactly one entry for each source key in
`m3-corpus-v1`, with no missing, extra or duplicate `source_key`. Each entry is the exact
environment-provenance triple `(source_key, production_document_version_id,
production_chunk_set_id)`.

## Corpus-closure preflight

Before a measured Q&A request, `EvaluationEnvironmentBootstrap` uses supported production and
application seams to enumerate the complete retrieval-eligible active corpus of the evaluation
Workspace. Its source-key set must equal `m3-corpus-v1` exactly. For each manifest source there
must be exactly one active manifest-matching Document Version and exactly one corresponding
persisted Chunk Set. An active extra source/document, missing source, duplicate binding source, or
multiple active source/version is a setup/provenance failure and prevents Q&A execution. The
bootstrap does not infer any result from current/latest/name lookup.

## Trace gate and canonical projection

The trace/evaluation reader projects candidate `source_key`, `document_version_id`, `chunk_set_id`
and ordinal. For every correlated candidate the evaluator selects one entry by source key and
requires the exact triple equality before canonical projection. `document_version_id` is mandatory:
if the trace itself lacks it, the reader must establish an equivalent mandatory verified
source → Document Version → Chunk Set relation before returning the candidate. A consumer may not
omit the version comparison.

Unknown source, wrong Document Version/Chunk Set UUID, incomplete or duplicate binding, or any
provenance mismatch is an observation failure. Only after passing the gate may the candidate be
projected to `(chunk_set_provenance_id, source_key, ordinal)`. The UUIDs remain environment gates,
not portable gold identity.
