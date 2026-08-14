# M3 evaluation environment binding V1

`m3-corpus-v1` remains immutable. This artifact records a verified deployment-specific binding;
it never changes the corpus manifest or requires a production UUID to equal a manifest identity.

## Binding schema

```json
{
  "schema_version": 1,
  "dataset_manifest_identity": "m3-dataset-v1",
  "corpus_manifest_identity": "m3-corpus-v1",
  "chunk_set_provenance_id": "chunk-set-m3-v1",
  "production_chunk_set_id": "<persisted ChunkSet UUID>",
  "workspace_id": "evaluation-m3-v1",
  "retrieval_configuration_id": "retrieval-m3-rrf-v1"
}
```

The binding is valid only after bootstrap verifies the Workspace's active corpus and chunking
provenance against the immutable manifest, and records the exact persisted Chunk Set UUID. The
evaluation runner verifies the correlated trace contains that UUID before projecting candidates to
`(chunk_set_provenance_id, source_key, ordinal)`.

## Application seams

```text
EvaluationEnvironmentBootstrap.prepare(manifest, environment configuration)
  -> verified binding + runtime-only scoped credential

RetrievalConfigurationResolver.resolve(workspace/deployment configuration)
  -> immutable Retrieval Configuration
```

Bootstrap is control-plane only: it provisions/reuses an isolated Workspace, applies normal
credential invariants, loads/binds the corpus through supported ingestion/application behavior,
and writes the binding. It has no public acceptance-only HTTP endpoint and is outside measured Q&A.

The resolver runs in the production Q&A composition path. It accepts no evaluation request
override, persists the resolved configuration ID in the trace, and supports #52 by selecting
baseline and hybrid in separate configured runs.
