# Manual Test Guide: OpenAI-Compatible Providers

## Metadata

- Status: Approved and locked
- Feature: Milestone 1 — Cited RAG
- Slice: GitHub issue #4 — Run ingestion and cited answers with OpenAI-compatible providers
- Authoritative specification: `docs/specs/milestone-1-cited-rag.md`
- Guide revision: `m1-openai-compatible-providers-r1`
- Approved by: NhiBuaa
- Approved at: 2026-07-31T20:20:28+07:00

## Prerequisites

- Environment: local checkout with Docker PostgreSQL/pgvector healthy, migrated schema and the
  FastAPI application configured once in deterministic-local mode and once in OpenAI-compatible
  mode. Restart the application between provider-mode changes so startup configuration is
  observable and immutable for each run.
- Compatible endpoint: a local controllable HTTP fake implementing the configured
  OpenAI-compatible embedding and generation operations. It must record sanitized requests and
  support controlled success, dimension mismatch, structured refusal, malformed output, HTTP
  error and timeout responses. A separately configured real compatible endpoint may be used for
  the final smoke case when the human supplies credentials at runtime.
- Data and state: dedicated Workspace `acceptance-openai-compatible`; reset its database rows
  before a new Evaluation run without rewriting prior Evaluation history. Use a small Markdown
  corpus with one answerable and one out-of-corpus question.
- Credentials and permissions: an enabled Knora test credential for the acceptance Workspace.
  Provider credentials exist only in process environment variables or an ignored local `.env`;
  use canary values rather than production secrets for fake-endpoint cases.
- Configuration: Milestone 1 Embedding Configuration uses model `text-embedding-3-small`, 1536
  dimensions and cosine distance. Pin the generation model, prompt version, provider endpoint and
  any pricing/configuration version used to derive cost metadata for the Evaluation run.
- Observability: capture complete HTTP/CLI results, sanitized compatible-endpoint request logs,
  application startup/errors, focused adapter contract results and persisted Question Trace
  projections. Never capture raw provider or Knora API keys.

## Locked Test Cases

### TC-01: Select one provider mode at startup without fallback or routing

- Purpose: prove runtime configuration selects exactly the deterministic-local pair or the
  OpenAI-compatible pair while preserving the two approved provider contracts.
- Steps:
  1. Start Knora in deterministic-local mode and run one ingestion plus one answerable Question
     Request.
  2. Restart Knora in OpenAI-compatible mode pointing at the controllable endpoint and repeat the
     same public flows.
  3. Start Knora with an unsupported provider mode and with incomplete OpenAI-compatible
     configuration.
- Expected results:
  - Both valid modes use the same `IngestDocument` and `AnswerQuestion` application interfaces and
    the same HTTP response contracts; only the injected provider adapters/configurations differ.
  - OpenAI-compatible mode sends embedding and generation requests to only the configured
    endpoint. Deterministic-local mode sends no remote provider request.
  - Unsupported or incomplete configuration fails clearly during startup before serving traffic;
    it does not silently select local mode or another endpoint.
  - Production structure still exposes exactly `EmbeddingProvider` and `GenerationProvider`; no
    generic provider super-interface, automatic fallback or multi-provider router is introduced.
- Evidence to capture:
  - Sanitized startup configuration/error output, public-flow responses, endpoint request counts
    and focused provider-wiring test output.

### TC-02: Ingest through the OpenAI-compatible Embedding Provider

- Purpose: verify the compatible embedding adapter implements the locked 1536-dimensional
  contract and remains behind the existing ingestion seam.
- Steps:
  1. Configure the fake endpoint to return one 1536-dimensional vector per requested input with
     the pinned provider/model identity.
  2. In OpenAI-compatible mode, ingest the acceptance document through authenticated HTTP.
  3. Ingest a second source through the CLI using the same selected provider mode and immutable
     Embedding Configuration.
- Expected results:
  - The adapter sends all prepared Chunk texts in the compatible request and returns vectors in
    input order with the expected provider/model identity.
  - HTTP and CLI both delegate to `IngestDocument`; neither adapter accesses persistence directly
    or implements a separate embedding path.
  - Successful ingestion persists an Embedding Set referencing the pinned OpenAI-compatible
    Embedding Configuration and returns the existing ingestion result contract.
  - Repeating an identical ingestion preserves existing idempotency and activation semantics.
- Evidence to capture:
  - HTTP and CLI results, sanitized embedding request/response summary, focused adapter contract
    output and persisted configuration identity.

### TC-03: Reject embedding shape or identity mismatch before persistence

- Purpose: prevent incompatible vectors or mislabeled embedding responses from entering an
  immutable Embedding Set.
- Steps:
  1. Configure the fake endpoint to return a 1535-dimensional vector for a new source and submit
     ingestion.
  2. Repeat with a wrong vector count and with provider/model identity inconsistent with the
     selected Embedding Configuration.
  3. Configure the same dimension mismatch for a Question Request and observe retrieval behavior.
- Expected results:
  - Vector dimension or count mismatch returns `EMBEDDING_DIMENSION_MISMATCH`; configuration
    identity mismatch returns the repository's explicit configuration-mismatch error.
  - Failed ingestion performs no derivation persistence and does not change a Document's active
    pointer.
  - A mismatched question embedding fails before retrieval and generation.
  - No scenario falls back to deterministic-local embeddings or retries against another provider.
- Evidence to capture:
  - Error responses, endpoint request counts, before/after persistence projections and proof that
    retrieval/generation were not invoked.

### TC-04: Generate a validated cited answer through the OpenAI-compatible provider

- Purpose: prove model-backed generation returns the locked Structured Generation Result and uses
  the existing answer/citation validation pipeline.
- Steps:
  1. Ingest the acceptance corpus in OpenAI-compatible mode and configure the fake generation
     response as a valid answer citing selected aliases in a controlled order.
  2. Submit the answerable Question Request through authenticated HTTP.
  3. Compare the provider request, HTTP response and persisted Question Trace with the selected
     Evidence Set.
- Expected results:
  - The compatible request contains the question, opaque Evidence Aliases and evidence content,
    but no database Chunk IDs or provider-supplied citation metadata.
  - HTTP 200 returns the existing `ANSWER` contract with validated inline markers, ordered
    server-resolved Citation Projections and an opaque `trace_id`.
  - The same `AnswerQuestion` orchestration performs retrieval, generation validation, citation
    projection and trace persistence before responding; no partial output is exposed.
  - The persisted trace safely records provider, model, prompt version, provider request ID,
    finish reason, token usage and cost metadata with its pricing/configuration provenance.
- Evidence to capture:
  - Complete HTTP response, sanitized compatible request/response summary and Question Trace
    provider-metadata projection.

### TC-05: Preserve refusal and invalid-generation error semantics

- Purpose: ensure the remote adapter cannot weaken the application's structured refusal and
  generation-validation invariants.
- Steps:
  1. With qualified evidence, return a valid structured `INSUFFICIENT_EVIDENCE` refusal from the
     fake generation endpoint.
  2. Run controlled malformed outputs covering invalid JSON/schema, unknown alias and marker/list
     mismatch.
  3. Run one provider HTTP error and one timeout.
- Expected results:
  - A valid structured refusal returns HTTP 200 with the application-owned refusal message, empty
    citations and `refusal_reason=INSUFFICIENT_EVIDENCE`.
  - Every malformed structured output returns HTTP 502 `GENERATION_OUTPUT_INVALID`; none becomes
    a Refusal or exposes a partial answer/citation.
  - Provider transport failures use explicit sanitized errors and do not expose raw response
    bodies, credentials or stack traces to clients.
  - Each scenario makes only the expected configured-provider request: there is no repair retry,
    deterministic fallback or alternate-provider request.
- Evidence to capture:
  - HTTP results, endpoint request counts and sanitized trace/error observations.

### TC-06: Keep credentials runtime-only and redact sensitive provider data

- Purpose: prove provider authentication and observability do not persist or disclose secrets.
- Steps:
  1. Start OpenAI-compatible mode with a unique canary provider key supplied only through runtime
     configuration and execute successful embedding and generation calls.
  2. Trigger a provider HTTP error whose body and headers contain distinct secret-like canaries.
  3. Search application logs, HTTP responses, Question Traces, generated artifacts and tracked
     repository files for every canary.
- Expected results:
  - Authorization reaches only the configured provider endpoint using its required auth scheme;
    raw credentials are absent from request summaries and application-visible metadata.
  - No canary appears in client responses, logs, traces, Evaluation artifacts or tracked files.
  - Provider request IDs and safe operational metadata remain available for correlation without
    retaining request authorization headers or raw provider payloads.
- Evidence to capture:
  - Redacted endpoint auth observation, negative canary-search output and sanitized trace/error
    samples.

### TC-07: Pass adapter contracts against a controlled and a configured compatible endpoint

- Purpose: show adapter behavior is repeatable under deterministic fakes and interoperable with a
  human-configured OpenAI-compatible service without making a semantic-quality claim.
- Steps:
  1. Run the focused embedding and generation adapter contract suites against the controllable
     fake endpoint, including success and failure cases from TC-02 through TC-06.
  2. When the human supplies a non-production compatible endpoint and runtime credential, run one
     1536-dimensional embedding call and one structured-generation smoke call.
  3. Run the repository verification commands from the repository root.
- Expected results:
  - The deterministic fake contract suite passes without network credentials and records no
    semantic-quality metric.
  - When configured, the live smoke calls satisfy the same adapter result contracts and record
    provider/model/configuration provenance; absence of optional live credentials is reported as
    a blocked smoke case rather than silently replaced by local mode.
  - The full pytest suite, Ruff and Docker Compose configuration checks pass.
- Evidence to capture:
  - Focused contract-test output, optional sanitized live smoke result and complete repository
    verification output.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL
Evaluation records.
