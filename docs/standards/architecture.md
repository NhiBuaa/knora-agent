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
- Milestone 1 uses `1536` dimensions, PostgreSQL `vector(1536)` and cosine distance. Approved
  immutable Embedding Configurations are `embedding-local-m1-v2` for deterministic-local
  structural tests (`text-embedding-3-small` as a model label), `embedding-openai-m1-v1` for
  OpenAI-compatible `text-embedding-3-small`, and the separately versioned
  `embedding-gemini-m1-v1` for OpenAI-compatible Gemini `gemini-embedding-001` semantic-baseline
  runs.
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
- `embedding-gemini-m1-v1` is a distinct migration/storage identity. Its corpus must be re-embedded
  and activated as a new Embedding Set before retrieval; it must never reuse or mix vectors from
  another Embedding Configuration, even when dimensions match.
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
- The Milestone 1 text identities above remain unchanged. For Milestone 2 PDF, Document Version
  idempotency is `(document_id, raw_sha256)` and the immutable Original Source Object belongs to
  that version. Parser, normalizer, chunking and embedding version changes do not create another
  PDF Document Version; they create a distinct derivation target whose Chunk Set identity includes
  immutable parser, normalizer and chunking configuration version IDs.
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

## Asynchronous PDF ingestion

- Milestone 2 accepts one text-based, non-encrypted PDF through the authenticated document-upload
  seam and acknowledges durable accepted work with HTTP `202` and an Ingestion Job ID. Existing
  synchronous Markdown/plain-text behavior remains compatible.
- Job status lookup must authenticate and authorize the Workspace before looking up the job. Job
  records and all job-store predicates are Workspace-scoped; an authorized unknown job returns a
  safe not-found code and never reveals another Workspace's resource.
- PostgreSQL is the durable Ingestion Job store for Milestone 2. A worker claims an eligible job
  atomically (including `FOR UPDATE SKIP LOCKED` where appropriate), writes an expiring lease and
  increments a fencing/lease version. A worker whose lease is expired or fenced out must not
  publish a result. Another worker may reclaim an expired job.
- The claim transaction ends before PDF parsing, normalization, chunking or Embedding Provider
  calls begin. Provider and parsing latency must never hold the job-claim or derivation
  transaction open.
- Delivery is at-least-once. Processing must be idempotent; job, Document Version, Chunk Set and
  Embedding Set database constraints remain the final deduplication and version-integrity guards,
  independent of queue behavior.
- Each job records attempt count, bounded retry policy, exponential backoff, `next_attempt_at`,
  lease metadata and a stable terminal failure code. Only classified transient storage, database
  or provider failures are retried; invalid input, configuration/vector mismatches and stale
  activation compare-and-swap failures are terminal unless a later approved policy changes this.
- Milestone 2 uses four attempts total (one initial plus three retries). Backoff is a versioned
  full-jitter policy with windows of 5 seconds, 30 seconds and 2 minutes, capped at 5 minutes;
  the windows are not described as exponential without an explicit formula. Lease duration is 2
  minutes, heartbeat is every 30 seconds and extends to `now + 2 minutes`, and maximum attempt
  runtime is separately bounded at 15 minutes. Every heartbeat and commit checks `worker_id` and
  `lease_version`.
- Retryable failures are provider timeout/429/5xx, transient database deadlock/serialization/
  connectivity, worker crash, extractor eviction and other explicitly transient infrastructure
  failures. Invalid/encrypted/unsupported input, resource limits, deterministic parser failure,
  invalid pinned configuration and embedding/vector mismatch are non-retryable for the job.
- A stale activation CAS is not a terminal failure and does not consume retry budget. The job
  becomes `superseded`, cleans staging output, and a manual reprocess creates a new job generation.
  Exhausted attempts remain public state `failed` with safe `failure_reason = retry_exhausted`; a
  new manual reprocess never mutates the old attempt counter.
- `Document.current_document_version_id` is an explicit source pointer and is never inferred from
  timestamps, UUIDs or `MAX(id)`. After Original Source Object durability and checksum confirmation,
  the version record and current pointer are committed atomically before chunking/embedding; the
  pointer does not wait for activation. `Document.version_number` is allocated sequentially while
  concurrent source uploads serialize on the Document row/CAS.
- `current_document_version_id` and `active_embedding_set_id` may temporarily refer to different
  source versions. Retrieval reads only the active Embedding Set, so a failed or in-progress newer
  source version does not interrupt answers from the older served derivation. Activation requires
  a valid worker lease/fencing token, target equality with the current pointer, a complete set and
  same Document/Workspace ownership. A newer source version causes an older job to finish
  `superseded`.
- Foreign keys and ownership constraints must prevent current or active pointers from referencing
  another Document or Workspace, and hard deletion is forbidden while either pointer references a
  version/set. Reprocess accepts only the current version; historical versions return
  `409 DOCUMENT_VERSION_NOT_CURRENT`.
- PDF request idempotency is scoped by `(workspace_id, operation, idempotency_key)` with a baseline
  24-hour retention. The same key with the same immutable request fingerprint returns the same job
  response; the same key with a different fingerprint returns `IDEMPOTENCY_KEY_CONFLICT`. Atomic
  insert or a unique database constraint protects concurrent requests.
- The content fingerprint is exactly `(workspace_id, canonical_source_key, raw_sha256,
  parser_config_version_id, normalizer_config_version_id, chunking_config_version_id,
  embedding_config_version_id)`. Filename, upload timestamp and object key are excluded. Immutable
  configuration version IDs are mandatory; mutable configuration blobs and model names alone are
  not valid identities.
- Document Version deduplication is distinct from request idempotency and processing generation:
  equal `source_key + raw_sha256` reuses the Document Version target; changed raw checksum creates
  a new Document Version. A retry-exhausted job can be explicitly reprocessed as a new generation
  linked by `reprocess_of`, with a fresh attempt budget and no mutation of the old job. Reprocessing
  an older version is explicit and must not automatically replace a newer current version.
- Manual reprocess targets a current `Document Version` through
  `POST /v1/workspaces/{workspace_id}/document-versions/{document_version_id}/reprocess`. It
  requires Workspace reprocess authorization, a new `Idempotency-Key`, an audit record and
  `config_mode` of `same_as_job` or `current`. The handler checks Original Source Object
  availability, snapshots immutable config version IDs and enqueues; it never reads or parses the
  object. The worker reads the object and never resolves mutable/current configuration.
- Reprocess creates a new job generation with `reprocess_of_job_id` and a reset attempt budget;
  the old job is immutable. Equal Document Version plus equal config versions already processing
  or succeeded is deduplicated/reused. A non-current target returns `409 DOCUMENT_VERSION_NOT_CURRENT`.
  If the target becomes stale during processing, activation CAS ends the generation as
  `superseded`. Historical-version reprocessing is out of scope for Milestone 2.
- A job is terminally successful only after the complete derivation chain and active-pointer
  compare-and-swap commit. A failed job must not change the previously Active Embedding Set or
  leave a partial Chunk Set or Embedding Set.
- Accepted raw PDFs are staged in Workspace-isolated object storage under server-generated opaque
  keys. The staging object must be durable before `202`; database records must not store raw PDF
  contents or credentials. Once a Document Version is committed, its immutable original PDF object
  belongs to that Document Version and is not deleted at job terminal state. Superseded originals
  follow retention required by citations, traces and evaluations; failed uploads follow bounded
  diagnostic retention. Staging, temporary and partial derivation artifacts are cleaned
  asynchronously after terminal state.
- The minimum `ObjectStore` interface is streaming `put_stream`, streaming `open_read`, `head`,
  and idempotent `delete`. Objects carry Workspace identity, a server-generated opaque key,
  SHA-256 content hash, byte size and media type. ETag is not a content hash, and callers must not
  create storage paths or call a whole-object `read()` API.
- Database and object storage do not share an atomic transaction. An orphan sweeper/reconciler
  must find and clean unreferenced staging/temporary objects, retry cleanup failures, expose
  cleanup/orphan metrics and alert without reversing a committed ingestion success. Contract tests
  must run against MinIO and the configured production S3-compatible provider.
- The PDF upload response is `202 Accepted` when a created or reused job is non-terminal and
  `200 OK` for a terminal idempotency replay or fingerprint deduplication. Every response includes
  `ingestion_job_id`, `submission_outcome` (`created`, `idempotency_replay` or `deduplicated`) and
  `status`.
- Public states are `queued`, `processing`, `retry_scheduled`, `succeeded`, `superseded` and
  `failed`. `attempt_count` counts attempts started, including the initial attempt; `max_attempts`
  is the total budget. `failed` exposes only safe `failure_reason` (`retry_exhausted`,
  `terminal_input`, `terminal_config` or `resource_limit`) plus a safe error code.
- Polling returns `200 OK` with status, attempt counts, `next_attempt_at` only when retry is
  scheduled, UTC RFC 3339 created/started/updated/terminal timestamps, terminal result or safe
  error, and `poll_after_seconds` or `Retry-After`. Responses use `Cache-Control: no-store`.
  `superseded` may include replacement Document Version and Ingestion Job IDs; `reprocess_of` is
  only on a newly created processing generation. Missing or cross-Workspace jobs return the same
  `404 INGESTION_JOB_NOT_FOUND` response.
- Job status exposes `target_document_version_id`, `current_document_version_id` and nullable
  `served_document_version_id` resolved from `active_embedding_set_id` in one consistent database
  snapshot. It also exposes server-computed `serving_state`: `unavailable` when no active set
  exists, `current` when served equals current source, or `previous` otherwise. This state never
  replaces `job.status`; a later Document detail/status projection should expose the same serving
  projection.
- PDF citation provenance is pinned to `document_version_id` plus the persisted `chunk_id` (or a
  versioned Chunk identity), `page_start`, `page_end`, and stable offsets within normalized page
  text. `page_start` and `page_end` are 1-based physical PDF page indexes. `page_label` is
  display-only metadata and must not determine identity or retrieval provenance.
- `start_line` and `end_line` may remain in the Citation Projection for compatibility, but they
  are derived metadata and must not be the sole PDF provenance because parser, OCR or normalization
  changes can shift line boundaries. The schema must leave room for future bounding-box metadata;
  bounding boxes are out of scope for Milestone 2.
- Queue observability records queue depth, oldest-job age, claim latency, retry rate and
  lease-expiry recovery. Polling clients should use jitter and must not rely on synchronized tight
  loops.

### PDF extraction safety and versioning

- `PdfTextExtractor` is the only application-facing PDF extraction interface. It wraps the pinned
  `pypdf` baseline and owns extraction mode/options, deterministic Unicode/whitespace/newline/
  control-character/line-joining normalization, and page-order preservation. Library behavior is
  not treated as a determinism guarantee.
- Every extraction records immutable `parser_version`, extraction-options identity,
  `normalizer_version` and `chunking_config_version`. A parser, option, normalizer or chunker
  change creates a new derivation identity and never mutates historical Document Versions, Chunk
  Sets or Embedding Sets.
- Encrypted/password-protected, malformed, unsupported and textless PDFs fail with distinct safe
  terminal domain codes. A file must not succeed with an empty extracted corpus.
- Upload and worker processing enforce configured raw file-size, page-count, content-stream-size,
  timeout and memory limits before activation. Limit failures do not create a successful
  derivation. Multi-column reading order, table reconstruction, OCR and perfect layout fidelity
  are not promised by the baseline parser.
- The extractor runs in an isolated child process. The parent enforces a hard RSS/container/process
  ceiling and can kill the child. The inspection/extraction timeout covers only PDF inspection and
  extraction; object storage, chunking and embedding have separate timing behavior.
- Milestone 2's initial budget is `25 MiB` raw upload, `500` physical pages, `4 MiB` decompressed
  content stream per page, `64 MiB` aggregate decompressed content streams, `30 seconds` for
  inspection plus extraction, and `256 MiB` hard extractor RSS/container/process memory ceiling.
  The complete budget is part of the versioned ingestion configuration.
- A file that exceeds a budget is terminal `PDF_RESOURCE_LIMIT_EXCEEDED` with an internal reason
  from `RAW_FILE_SIZE`, `PAGE_COUNT`, `PAGE_STREAM_SIZE`, `TOTAL_STREAM_SIZE`,
  `EXTRACTION_TIMEOUT` or `EXTRACTOR_MEMORY`. Infrastructure failure, worker crash or extractor
  eviction is retryable under the bounded job policy.
- Failure preserves the original staged object and terminal Ingestion Job/failure record for
  diagnosis and cleanup, leaves existing Document Versions unchanged, does not activate a Chunk
  Set or Embedding Set, and never exposes partial derivation to retrieval. Budget changes apply
  only to new ingestion or reprocessing and never mutate historical derivations.
- PDF Chunk Sets do not cross physical page boundaries in Milestone 2. The normalized page text is
  split into deterministic paragraph/block units and packed toward `target_tokens = 500` with at
  most `overlap_tokens = 75`, preferring complete blocks. Only a block exceeding `max_tokens =
  650` may be hard-split with deterministic token windows, and overlap must not cause a Chunk to
  exceed `max_tokens`.
- PDF chunk token counts use normalized text and record the tokenizer name and exact version in
  the immutable Chunking Configuration. Every PDF Chunk records `page_number`, `chunk_ordinal`,
  content checksum and character offsets with `start` inclusive and `end` exclusive. Empty or
  whitespace-only pages produce no Chunk. Each Milestone 2 PDF Chunk has `page_start = page_end`;
  both fields remain in the projection for citation compatibility. Changing tokenizer, normalizer
  or chunking policy creates a new Chunk Set/version and never mutates historical chunks.

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
