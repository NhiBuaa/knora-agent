# Architecture Standard

These rules are normative for Knora unless superseded by an approved Standard or ADR.

## Ownership and boundaries

- Knora owns Workspaces, Documents, Chunks, embeddings, Question Traces and evaluations.
- KittaChat owns users, conversations and messages.
- Knora must not access KittaChat's database directly. Integration uses authenticated API or event
  contracts.
- Agent failure must not break KittaChat's ordinary message delivery.

## Authentication and workspace authorization

- `/health` is public and returns only minimal service status. It must not expose dependency
  details, secrets, model configuration or stack traces; debug endpoints are disabled by default.
- Every Workspace endpoint requires `X-API-Key` and must execute in this order:
  `authenticate key → create principal → authorize workspace → lookup resource`.
- Missing or invalid credentials return HTTP 401 with `UNAUTHENTICATED`. A valid principal used
  against another Workspace returns HTTP 403 with `WORKSPACE_ACCESS_DENIED`.
- Authorization failures must not reveal whether a requested resource exists.
- One API Credential belongs to exactly one Workspace; one Workspace may have multiple credentials
  for rotation and separate test environments.
- Runtime credential configuration stores only `key_id`, `key_hash`, `workspace_id` and `enabled`.
  Raw keys must not be persisted or logged, secret comparison is constant-time, and logs/traces
  use only `key_id` or a safe fingerprint.
- CLI may bypass HTTP credential parsing only. It must construct a Workspace Principal with
  explicit `workspace_id` and pass through the same application authorization policy.
- `trace_id` is only an opaque correlation handle and never grants data access.

## Evidence and tenant safety

- Every ingestion and retrieval operation must be scoped to exactly one Workspace.
- A Cited Answer may cite only Chunks present in the Evidence Set used for that answer.
- When evidence cannot support an answer, the system returns a Refusal and must not fabricate a
  citation.
- Documents, Chunks and evaluation data must not contain production secrets in version control.

## Provider and configuration boundaries

- Milestone 1 exposes exactly two provider contracts: `GenerationProvider` and
  `EmbeddingProvider`.
- Application and domain behavior depend on those contracts rather than a specific model vendor.
- Each contract has a deterministic local adapter for repeatable tests and an OpenAI-compatible
  adapter for demos and model-backed evaluation, selected through runtime environment variables.
- The deterministic local adapters may validate orchestration, schemas, citation/refusal flow and
  Question Trace persistence. Their output must not be used to claim semantic-quality metrics.
- Milestone 1 does not add provider fallback, multi-provider routing or a more general provider
  abstraction.
- Milestone 1 uses `text-embedding-3-small`, `1536` dimensions, PostgreSQL `vector(1536)` and
  cosine distance as one immutable Embedding Configuration.
- An Embedding Configuration contains `provider`, `model`, `dimensions` and `distance_metric`.
  Embedding Sets reference it by `embedding_configuration_id`.
- Immediately after an Embedding Provider response, the adapter must validate
  `len(embedding) == configured_dimension`. A mismatch returns
  `EMBEDDING_DIMENSION_MISMATCH` before any database write.
- Embeddings from different Embedding Configurations must never be mixed in ingestion or
  retrieval, even when their dimensions match.
- Changing the embedding model or dimensions creates a new embedding space, requires compatible
  migration/storage and a full re-ingestion of affected Chunks. Environment-only changes are not
  valid migrations.
- The deterministic local Embedding Provider must emit 1536-dimensional vectors so integration
  tests exercise the production database schema.
- Prompt, model, chunking and retrieval configurations must be versioned when they can affect an
  evaluation result.
- Provider credentials enter through runtime configuration and must never be committed.

## Ingestion and derivation identity

- Milestone 1 accepts only UTF-8 Markdown and plain text. Line endings are normalized before
  calculating the SHA-256 content checksum.
- `source_key` identifies a logical Document and is unique within a Workspace. Different source
  keys identify different Documents even when normalized content is identical.
- The derivation model is `Document Version → Chunk Set → Embedding Set`; re-chunking and
  re-embedding must not create a new Document Version.
- Document Version idempotency is `(document_id, normalized_content_checksum)`.
- Chunk Set idempotency is `(document_version_id, chunking_configuration_id)`.
- Embedding Set idempotency is `(chunk_set_id, embedding_configuration_id)`.
- A Chunking Configuration is immutable and includes `parser_version`, `chunker_version`,
  `tokenizer_name`, `tokenizer_version`, `target_tokens`, `overlap_tokens` and `max_tokens`.
- The Milestone 1 baseline is heading/paragraph-aware chunking with `target_tokens = 500`,
  `overlap_tokens = 75` and `max_tokens = 650`. Content exceeding `max_tokens` must be split even
  when it belongs to one heading or paragraph.
- Every Chunk records at least `ordinal`, `heading_path`, `start_line`, `end_line`,
  `content_checksum` and `token_count`.
- Chunk ordering is unique within a Chunk Set through `unique(chunk_set_id, ordinal)`. Chunk
  identity is not stable across different Chunk Sets.

## Synchronous ingestion execution

- HTTP and CLI must call the same `IngestDocument` application use case and validation path. The
  CLI must not access repositories or ORM models directly.
- Raw input is limited to 1 MiB. Normalized content is limited to 50,000 tokens and a resulting
  Chunk Set is limited to 100 Chunks.
- A size-limit violation returns `DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION` before calling the
  Embedding Provider.
- Parse, normalize, chunk, embed and validate all vectors before opening a database transaction.
- Persistence uses one short transaction that re-checks idempotency and atomically writes the
  requested `Document Version → Chunk Set → Embedding Set` derivation. Failure must not leave a
  partial Chunk Set or Embedding Set.
- Unique constraints are the Milestone 1 concurrency control for duplicate persistence.
  Concurrent requests may perform duplicate embedding calls; preventing that with a lease or
  distributed lock is explicitly deferred.
- A request reuses the chain only when `source_key`, normalized content checksum, Chunking
  Configuration and Embedding Configuration all resolve to existing resources.

## Active retrieval state and concurrency

- `Document.active_embedding_set_id` is nullable. Retrieval ignores Documents without an active
  set.
- The active pointer may reference only a completed Embedding Set belonging to the same Document
  and Workspace and using the required Embedding Configuration.
- The active pointer foreign key uses `ON DELETE RESTRICT`; an active Embedding Set must not be
  deleted.
- Every Document has a monotonic `revision`. `IngestDocument` reads the expected revision before
  calling the Embedding Provider.
- The final transaction persists or reuses the derivation chain, then updates the active pointer
  with compare-and-swap `WHERE revision = expected_revision` and increments revision.
- If compare-and-swap affects no row, the transaction rolls back completely and returns
  `DOCUMENT_CONCURRENTLY_UPDATED`. A provider call that completes late cannot replace a newer
  activation.
- Re-ingesting historical content may reuse an existing chain and activate it after the same
  concurrency check. The HTTP outcome remains `reused`, while `activation_changed` reports the
  pointer change.
- Retrieval resolves active sets consistently for one Question Request. Its Question Trace stores
  at least `embedding_set_id`, `chunk_set_id`, `embedding_configuration_id` and
  `retrieved_chunk_ids`.
- Historical Document Versions, Chunk Sets and Embedding Sets remain immutable for traceability
  but are excluded from search unless activated.

## Retrieval and evidence selection

- Milestone 1 uses exact pgvector cosine search. HNSW, IVFFlat, hybrid search and reranking are out
  of scope so the Recall@k baseline remains stable and inspectable.
- Score semantics are `similarity = 1 - cosine_distance`; the threshold applies to similarity.
  Question Trace records both raw cosine distance and derived similarity.
- The versioned Retrieval Configuration baseline is `candidate_k = 8`,
  `max_evidence_chunks = 5`, `max_evidence_tokens = 3000` and `min_similarity = 0.65`.
  The threshold is an initial value to calibrate with evaluation data, not a demonstrated quality
  claim.
- Workspace, Active Embedding Set and Embedding Configuration predicates must be applied inside
  the retrieval query. Global retrieval followed by application filtering is forbidden.
- Candidate order is `similarity DESC → document_id ASC → chunk_ordinal ASC → chunk_id ASC`.
- Evidence selection scans that order after thresholding and removes strongly overlapping adjacent
  Chunks from the same Chunk Set. It does not merge Chunks.
- Each candidate is traced with exactly one outcome: `SELECTED`, `BELOW_THRESHOLD`,
  `REDUNDANT_OVERLAP` or `TOKEN_BUDGET_EXCEEDED`.
- An Evidence Set is bounded by both `max_evidence_chunks` and `max_evidence_tokens`.
- When no candidate qualifies, Knora returns the deterministic Refusal without calling the
  Generation Provider. When evidence exists, the Generation Provider may still return a
  structured Refusal because relevant evidence may be insufficient to conclude.

## Generation and citation validation

- The application assigns request-scoped Evidence Aliases (`E1`, `E2`, ...) and retains the
  `evidence_id → chunk_id` mapping. Generation Providers must not receive database Chunk IDs.
- A Structured Generation Result contains `decision: ANSWER | REFUSAL`, nullable `answer`, ordered
  `cited_evidence_ids`, and nullable `refusal_reason` limited to `INSUFFICIENT_EVIDENCE`.
- Answer text cites evidence through inline markers such as `[[E2]]`.
- An `ANSWER` is valid only when answer text is non-empty, contains at least one marker, every
  marker belongs to the Evidence Set, IDs are unique, and `cited_evidence_ids` exactly equals the
  marker IDs in first-appearance order.
- A `REFUSAL` is valid only when `answer` is null, no marker or citation exists,
  `cited_evidence_ids` is empty, and `refusal_reason` is `INSUFFICIENT_EVIDENCE`. Application code
  supplies the standardized user-facing refusal message.
- Schema, Evidence Set membership or marker-consistency failure returns
  `GENERATION_OUTPUT_INVALID`. It must not be converted to a Refusal, and Milestone 1 performs no
  repair retry.
- Citation metadata such as Document, heading and line range is resolved by the server from
  persisted data. Provider-supplied source metadata is never trusted.
- A Citation Projection pins `document_id`, `document_version_id`, `source_key`, display-only
  `source_name`, heading path, line range, content checksum and a server-resolved excerpt of at
  most 500 characters. `source_key` must not contain internal filesystem paths.
- Each Evidence Alias appears exactly once in the response citations, in first-appearance order;
  every inline marker has a corresponding item.
- The response includes explicit `decision: ANSWER | REFUSAL`. Refusal responses include
  `refusal_reason: INSUFFICIENT_EVIDENCE`; clients must not infer refusal from message text.
- `trace_id` is opaque and workspace-authorized; it does not grant access to traces or documents.
- A `GENERATION_OUTPUT_INVALID` response is HTTP 502 with the explicit error code and is never
  converted to a Refusal.
- Runtime validation proves only schema, Evidence Set membership and marker consistency.
  Semantic citation correctness and faithfulness are evaluation concerns.
- Question Trace stores generation status, the Evidence Alias mapping, parsed markers, validation
  outcome, provider/model, prompt version, token usage, latency, finish reason and provider request
  ID when present. Chain-of-thought must neither be requested nor persisted.

## Response delivery

- Milestone 1 uses ordinary request/response HTTP. The server must complete retrieval, generation,
  structured-output validation, citation projection and trace persistence before responding.
- Token events, partial answers and unvalidated citations must never be exposed to clients.
- End-to-end latency is recorded in Question Trace.
- Later progress events (`retrieving`, `generating`, `validating`) or token streaming require a
  separate contract and failure semantics; they are not implied by `trace_id` and are not assigned
  automatically to Milestone 2. UI/observability work is the current candidate milestone for that
  capability unless evaluation demonstrates an earlier need.

## Evaluation governance

- Milestone 1 uses 20–25 curated Evaluation Cases to prove the evaluation pipeline end to end.
  Cases include answerable, unanswerable, ambiguous and adversarial/near-miss behavior.
- Each case records `expected_behavior`, `expected_source_documents`,
  `acceptable_relevant_chunks` and required facts/reference answer when applicable. Evaluation
  must not require one unique correct Chunk when several relevant Chunks are acceptable.
- Retrieval metrics are independent of Generation Provider: Recall@8, MRR, hit rate and retrieval
  latency.
- Generation semantic metrics require a model-backed provider: citation entailment, faithfulness,
  answer relevance and refusal correctness.
- System metrics include latency, tokens, cost and provider errors; they are not semantic metrics.
- Citation correctness is split into deterministic validity checks (structural invariants must be
  100%) and semantic support/entailment scored by a human or versioned scorer.
- Milestone 1 hard gates are: structural pipeline checks at 100%, no cross-Workspace retrieval,
  no citation outside Evidence Set, persisted Question Trace, repeatable runner and complete
  provenance for dataset, corpus, chunking, embedding, retrieval, generation and scorer versions.
- Milestone 1 semantic metrics are baseline observations; no arbitrary quality threshold is set
  before the first run.
- A semantic metric may be claimed in portfolio material only after the dataset reaches at least
  50 cases and the report states dataset size and measurement method.

## Tool actions

- Tools are classified as read-only or write/destructive.
- Write or destructive actions require explicit human approval by default.
- Tool input must be schema-validated; side effects require an idempotency key and audit trail.
- An agent cannot infer access rights that were not supplied by the authenticated caller.

## Verification

- Public behavior is tested through approved HTTP, application and evaluation seams.
- Metrics claimed in portfolio material must name the dataset size and measurement method.
- Multi-agent orchestration requires evaluation evidence that its quality or maintainability gain
  justifies added latency and cost.
