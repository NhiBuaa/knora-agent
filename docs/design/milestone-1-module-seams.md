# Milestone 1 Module Seams

Status: Approved  
Source: [Milestone 1 specification](../specs/done/milestone-1-cited-rag.md)

This design places complex orchestration behind two deep application interfaces. HTTP, CLI,
evaluation and tests cross the same seams; ORM, provider payloads and transaction mechanics remain
implementation details.

## External application seams

### Ingest Document module

Interface:

```text
IngestDocument.execute(command, principal) -> IngestionResult
```

The command carries Workspace identity, `source_key`, display name, media type, raw bytes and the
selected immutable configurations. The result carries outcome, activation change, resource IDs,
configuration IDs and chunk count.

The implementation hides authentication-independent Workspace authorization, normalization,
checksum identity, parsing, chunking, synchronous limits, Embedding Provider calls, vector
validation, idempotency re-check, atomic derivation persistence and revision compare-and-swap.

Errors are domain-visible codes including `WORKSPACE_ACCESS_DENIED`,
`DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION`, `EMBEDDING_DIMENSION_MISMATCH` and
`DOCUMENT_CONCURRENTLY_UPDATED`.

HTTP and CLI are adapters at this seam. Neither may access ORM models or repositories directly.

### Answer Question module

Interface:

```text
AnswerQuestion.execute(command, principal) -> QuestionResult
```

The command carries Workspace identity and question text. The result carries decision, validated
answer/refusal, ordered Citation Projections and opaque trace ID.

The implementation hides query embedding, exact active-set retrieval, deterministic candidate
ordering, overlap/token-budget selection, Evidence Alias assignment, Generation Provider calls,
structured-output validation, citation projection and Question Trace persistence.

`GENERATION_OUTPUT_INVALID` is an error result, not a Refusal. The module returns only after trace
persistence succeeds.

## Provider seams

These are real seams because each has deterministic-local and OpenAI-compatible adapters.

```text
EmbeddingProvider.embed(texts, configuration) -> EmbeddingBatch
GenerationProvider.generate(question, aliased_evidence, configuration) -> StructuredGenerationResult
```

Adapters own remote payload formats, request IDs, finish reasons and usage extraction. The
application owns dimension validation, Evidence Alias membership, marker consistency and user
response semantics.

There is no generic provider super-interface, fallback or routing interface in Milestone 1.

## Persistence seams

Persistence interfaces are transaction-shaped rather than one shallow repository per table.

### Ingestion store

```text
read_document_head(workspace_id, source_key) -> DocumentHead
commit_derivation(prepared_derivation, expected_revision) -> IngestionResult
```

`commit_derivation` hides unique-constraint reconciliation, the short transaction, complete
derivation persistence, active-pointer validation and compare-and-swap. Provider calls never occur
inside this interface.

### Retrieval store

```text
retrieve_candidates(workspace_id, query_vector, embedding_configuration, retrieval_configuration)
  -> RetrievalCandidates
```

The Postgres adapter owns the exact pgvector query and applies Workspace, Active Embedding Set and
Embedding Configuration predicates inside SQL. Application code owns evidence selection and
candidate outcomes.

### Question trace store

```text
persist(trace) -> trace_id
```

The store persists one complete, validated trace. `trace_id` generation and storage remain behind
the interface; no read interface is introduced in Milestone 1.

## Access seam

HTTP credential parsing is an adapter concern. It produces a `WorkspacePrincipal` through a
constant-time API-key authenticator. A single application authorization policy validates principal
Workspace before either deep application interface performs resource lookup. CLI constructs an
explicit principal but uses the same policy.

The policy remains an in-process module rather than a hypothetical adapter seam because Milestone
1 has one authorization implementation.

## Internal modules

Normalization, Markdown/text parsing, tokenization, chunking, overlap detection, generation marker
parsing and Citation Projection are internal modules. They may have internal test seams but do not
expand the two external application interfaces.

## Verification surfaces

- HTTP adapters: health, authenticated ingestion and question responses.
- CLI adapter: Workspace-isolated ingestion through `IngestDocument`.
- Application interfaces: ingestion outcomes/errors and question decisions/errors.
- Postgres adapters: atomic derivation/CAS behavior and tenant-filtered exact retrieval.
- Provider adapters: contract conformance for local and OpenAI-compatible modes.
- Evaluation runner: structural gates, retrieval metrics, semantic metrics and system metrics.

Tests assert observable outcomes through these interfaces and avoid testing ORM rows as a proxy
for application behavior except in focused persistence-adapter integration tests.

## Target directory ownership

Milestone 1 evolves toward this capability-first structure. Directories are created only when a
ticket needs them; empty placeholders are not required.

```text
backend/
├── migrations/
├── src/knora/
│   ├── main.py
│   ├── bootstrap.py
│   ├── config.py
│   ├── domain/
│   │   ├── access.py
│   │   ├── documents.py
│   │   ├── retrieval.py
│   │   ├── answering.py
│   │   └── errors.py
│   ├── access/
│   │   ├── api_keys.py
│   │   └── policy.py
│   ├── ingestion/
│   │   ├── interface.py
│   │   ├── module.py
│   │   ├── processing.py
│   │   └── store.py
│   ├── answering/
│   │   ├── interface.py
│   │   ├── module.py
│   │   ├── evidence.py
│   │   ├── generation_validation.py
│   │   └── stores.py
│   ├── providers/
│   │   ├── embedding.py
│   │   ├── generation.py
│   │   ├── deterministic/
│   │   └── openai_compatible/
│   └── adapters/
│       ├── http/
│       ├── cli/
│       └── postgres/
└── test/
    ├── access/
    ├── ingestion/
    ├── answering/
    ├── providers/
    ├── adapters/http/
    ├── adapters/postgres/
    └── fixtures/

evals/
├── corpora/milestone_1/
├── datasets/
├── runners/
├── scorers/
├── reports/
└── test/
```

`domain` contains pure canonical types and invariants and imports no FastAPI, SQLAlchemy or model
SDK. `ingestion` and `answering` own their application interfaces and implementations.
`adapters` contains transport and persistence implementations without application rules.

Avoid generic `services`, `repositories`, `utils`, `helpers` and `common` directories. Persistence
interfaces stay beside the application module that consumes them; PostgreSQL adapters stay under
`adapters/postgres`. Tests remain outside production source and mirror the owning module.
