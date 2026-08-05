# Knora Knowledge Agent

Knora is an independent AI support and knowledge service. It turns workspace-scoped source
documents into evidence that can support cited answers and, in later milestones, controlled tool
proposals.

## Current Model

### Knowledge ownership

- A **Workspace** is the tenant boundary for every document, chunk, retrieval operation, trace,
  and evaluation.
- A **Document** is the stable identity of a logical source, uniquely named by `source_key` inside
  one Workspace. Equal content under different source keys remains different Documents. Its
  `current_document_version_id` pointer selects the current source version, while its nullable
  `active_embedding_set_id` pointer selects the Embedding Set currently visible to retrieval; the
  pointers may temporarily refer to different source versions.
- A **Document Version** is an immutable source revision within a Document. Milestone 1 text uses
  normalized-content checksum identity; Milestone 2 PDF uses the Original Source Object's raw
  SHA-256 identity so changing parser, normalizer, chunker or embedding configuration never creates
  a new Document Version.
- A **Chunking Configuration** is an immutable parser, chunker and tokenizer configuration.
- A **Chunk Set** is one derivation of a Document Version under one Chunking Configuration.
- A **Chunk** is an ordered retrieval unit inside one Chunk Set and records enough source position
  metadata for its citation to be verified.
- A PDF Chunk's canonical source locator is pinned to its Document Version and Chunk identity,
  with a 1-based physical page range and stable offsets in the normalized page text. A page label
  is display metadata only; line ranges may be retained as derived compatibility metadata.
- Milestone 2 PDF Chunk Sets never cross physical page boundaries. Normalized page text is split
  into deterministic paragraphs/blocks and packed toward `target_tokens = 500` with at most
  `overlap_tokens = 75`; a block over `max_tokens = 650` is hard-split by deterministic token
  windows. Tokenizer name/version, normalized-text token counts and chunking policy are immutable
  configuration. Each PDF Chunk records page number, ordinal, half-open character offsets,
  content checksum and derived page fields; empty pages create no Chunk.
- An **Original Source Object** is the immutable PDF artifact owned by a Document Version. Its
  lifecycle follows version retention, citation/trace/evaluation references and approved hard
  deletion, not the terminal state of an Ingestion Job. Job staging objects and partial
  derivations are separate temporary artifacts.
- An **Embedding Set** is the vectorization of one Chunk Set under exactly one Embedding
  Configuration.
- A completed Embedding Set may become a Document's **Active Embedding Set**; inactive historical
  sets remain immutable for traceability and are excluded from retrieval.
- An **Evidence Set** is the ordered collection of retrieved Chunks supplied to answer generation.
- An **Evidence Alias** is a request-scoped opaque identifier such as `E1`; application code owns
  its mapping to one Chunk and providers never receive database Chunk IDs.
- A **Retrieval Configuration** is an immutable definition of candidate count, similarity
  threshold, evidence count, token budget and overlap-redundancy policy.
- A **Retrieval Candidate Decision** records a candidate's raw score and whether it was selected or
  excluded by threshold, redundancy or token budget.

### Ingestion

- **Ingest Document** is the single application use case shared by HTTP and CLI entrypoints.
- An **Ingestion Outcome** is `created` when any requested derivation is newly persisted and
  `reused` when the complete requested derivation chain already exists.
- **Activation Changed** reports whether ingestion changed the Document's active pointer,
  independently of whether the derivation chain was created or reused.
- An **Ingestion Job** is the durable, Workspace-scoped lifecycle record for asynchronous
  ingestion. It references staged source content by an opaque object key, owns attempt and lease
  metadata, and reaches a terminal success only when the requested derivation and activation are
  committed.
- An **Idempotency Record** is scoped by `(workspace_id, operation, key)` and binds a finite-retention
  request key to one immutable request fingerprint and Ingestion Job response. Request idempotency,
  Document Version deduplication and processing generations are separate concepts.
- An ingestion content fingerprint is `(workspace_id, canonical_source_key, raw_sha256,
  parser_config_version_id, normalizer_config_version_id, chunking_config_version_id,
  embedding_config_version_id)`. Filename, upload time and object key never participate. Immutable
  config version IDs, not mutable blobs or model names, define the target derivation.
- An Ingestion Job is processed with at-least-once delivery. Atomic claim, lease expiry and a
  fencing/lease version permit recovery by another worker without allowing an expired worker to
  publish a stale result. Processing is idempotent; database constraints protect job and
  derivation deduplication independently of queue delivery. Its terminal states include success,
  retry exhaustion and `superseded` when a stale CAS target has already been replaced.
- Public job states are `queued`, `processing`, `retry_scheduled`, `succeeded`, `superseded` and
  `failed`. Upload responses always include `ingestion_job_id`, `submission_outcome` and `status`;
  non-terminal create/reuse returns `202`, while terminal idempotency replay or fingerprint
  deduplication returns `200`. Submission outcomes are `created`, `idempotency_replay` and
  `deduplicated`.
- `attempt_count` counts attempts started, including the initial attempt; `max_attempts` is the
  total budget. Failed jobs expose safe `failure_reason` values `retry_exhausted`,
  `terminal_input`, `terminal_config` or `resource_limit`. Polling returns UTC RFC 3339 timestamps,
  retry scheduling hints, terminal result/error metadata and no-store caching; clients add jitter.
- Job status may expose `target_document_version_id`, `current_document_version_id` and nullable
  `served_document_version_id` resolved from the active Embedding Set in one database snapshot.
  Server-computed `serving_state` is `unavailable`, `current` or `previous`; it describes retrieval
  serving, not the Ingestion Job lifecycle. A future Document detail/status projection should
  expose the same serving view.
- The durable job store is PostgreSQL for Milestone 2. Workers claim eligible jobs atomically
  (including `FOR UPDATE SKIP LOCKED` where appropriate), do not hold a database transaction
  during parsing, chunking or embedding, and record bounded retries with exponential backoff,
  `next_attempt_at`, attempt count and terminal failure.
- Retry policy is four attempts total (one initial plus three retries) with versioned full-jitter
  windows of 5 seconds, 30 seconds and 2 minutes, capped at 5 minutes. Lease duration is 2
  minutes with a 30-second heartbeat extending to `now + 2 minutes`; maximum attempt runtime is
  separately bounded at 15 minutes. Every heartbeat and commit checks `worker_id` and
  `lease_version`.
- A Document Version becomes current only after its Original Source Object is durable, checksums
  are confirmed and the version record plus `current_document_version_id` are committed in one
  database transaction; chunking, embedding and activation do not delay source-version identity.
  Concurrent source uploads serialize on the Document row/CAS and allocate sequential
  `version_number` values.
- Retrieval reads only `active_embedding_set_id`; it never derives a served set from the current
  source version. Activation requires the job's valid lease/fencing token, the target to remain
  `current_document_version_id`, a complete Embedding Set and matching Document/Workspace
  ownership. A newer source version supersedes an older job.
- A failed retry-exhausted job may be explicitly reprocessed as a new processing generation linked
  by `reprocess_of`; the old job and attempt budget remain immutable. A `superseded` job does not
  block explicit reprocessing, and reprocessing an older version never automatically replaces a
  newer current version.
- **Reprocess Document Version** is the explicit backend operation for rebuilding the current
  Document Version. It snapshots immutable configuration versions at enqueue time using
  `same_as_job` or `current`, records `reprocess_of_job_id`, resets the attempt budget and never
  resolves configuration again in the worker. The HTTP handler authorizes, checks source-object
  availability and enqueues; the worker reads the Original Source Object.
- **PdfTextExtractor** is the Knora adapter around the pinned `pypdf` baseline. Deterministic
  behavior belongs to the adapter: extraction mode/options, `parser_version`,
  `normalizer_version` and `chunking_config_version` are explicit immutable identities. Unicode,
  whitespace, newline, control-character and line-joining normalization are versioned; changing
  any of them creates new ingestion/chunk derivations and never mutates historical results.
- PdfTextExtractor runs in an isolated child process with a versioned ingestion budget: raw file
  size, physical page count, per-page and aggregate decompressed content-stream size, inspection/
  extraction timeout and hard RSS/container memory ceiling. The parent can kill an over-budget or
  timed-out extractor without losing the worker process. Terminal budget failures retain the
  source object and failure record but never activate or expose a partial derivation.
- **ObjectStore** is the streaming storage interface for source and staging objects. Its minimal
  operations are `put_stream`, `open_read`, `head` and idempotent `delete`; objects are immutable
  and carry Workspace, opaque key, SHA-256, byte size and media type metadata. Callers never
  construct storage paths or load an object wholesale into memory.
- Queue health is observable through queue depth, oldest-job age, claim latency, retry rate and
  lease-expiry recovery metrics. Polling clients use jitter rather than synchronized tight loops.

### Access boundary

- A **Workspace Principal** is an authenticated application identity authorized for exactly one
  Workspace in Milestone 1.
- An **API Credential** is a rotatable key record identified by safe `key_id`; multiple credentials
  may authorize the same Workspace, but one credential never spans Workspaces.

### Question answering

- A **Question Request** asks Knora to answer within one Workspace.
- A **Cited Answer** is generated from an Evidence Set and exposes citations to its source Chunks.
- A **Structured Generation Result** is either an answer whose inline Evidence Alias markers are
  validated or a structured refusal with reason `INSUFFICIENT_EVIDENCE`.
- A **Citation Projection** is server-resolved metadata pinned to one Document Version and exposed
  for each Evidence Alias used in the answer. For PDF evidence it includes the canonical page
  locator and normalized-text offsets while preserving existing line fields when available.
- A **Refusal** is the valid application response when retrieval finds no qualified evidence or a
  valid Structured Generation Result reports insufficient evidence.
- A **Question Trace** records retrieval and generation observations used for debugging and
  evaluation, including every Retrieval Candidate Decision; it is not conversation state.
- An **Evaluation Case** is a versioned question fixture with expected behavior, acceptable source
  documents/chunks and required facts when applicable.
- An **Evaluation Report** separates structural pipeline checks, retrieval metrics, generation
  semantic metrics and system metrics with versioned dataset/configuration/scorer provenance.

### Provider boundaries

- A **Generation Provider** turns a Question and its Evidence Set into generated answer text.
- An **Embedding Provider** turns text into vectors used by ingestion and retrieval.
- An **Embedding Configuration** is an immutable embedding-space identity comprising provider,
  model, dimensions and distance metric.
- A **Deterministic Local Provider** exercises orchestration, schemas, citation/refusal behavior
  and trace persistence without representing semantic quality.
- An **OpenAI-compatible Provider** supplies model-backed generation or embeddings for demos and
  semantic evaluation when enabled by runtime configuration.

### System relationships

- **Document Version → Chunk Set → Embedding Set**: source history, extraction/chunk derivation and
  vector derivation have separate immutable identities. For PDF, Chunk Set identity includes the
  parser, normalizer and chunking configuration versions; re-extracting, re-chunking or
  re-embedding does not create a new Document Version.
- **Ingestion → Retrieval**: ingestion creates or reuses the versioning chain; retrieval selects an
  Evidence Set only from the Active Embedding Sets resolved for that request and Workspace.
- **Ingestion → Document activation**: a compare-and-swap on Document revision activates a
  completed Embedding Set atomically with chain persistence; a stale ingestion cannot overwrite a
  newer activation.
- **HTTP/CLI → Ingest Document**: entrypoints perform transport concerns and delegate all
  ingestion validation and orchestration to the same application use case.
- **Credential → Workspace Principal → Resource**: HTTP authenticates a key and authorizes its
  Workspace before any resource lookup; CLI constructs an explicit principal and uses the same
  authorization policy.
- **Retrieval → Generation**: generation receives evidence through an application contract and
  does not own storage queries; application code supplies request-scoped Evidence Aliases and
  validates the returned markers before resolving citation metadata.
- **Knora → Generation Provider**: application code supplies a Question and Evidence Set through
  the minimal generation contract; domain behavior is not owned by a model vendor.
- **Ingestion → Embedding Provider**: ingestion requests vectors through the minimal embedding
  contract, validates their dimensions and associates the resulting Embedding Set with the
  immutable Embedding Configuration.
- **KittaChat → Knora**: KittaChat may send normalized requests and receive bot responses through
  explicit service contracts; it never shares its database with Knora.
- **Evaluation → Knora**: version-controlled cases exercise public seams and measure retrieval,
  citation, refusal, latency, and cost behavior.
- **Question Trace → Client**: an opaque, workspace-authorized `trace_id` permits debugging without
  granting general trace access.
- **Question Request flow**: retrieve → complete generation → validate structured output and
  citation markers → resolve Citation Projection → persist Question Trace → return response.

## Context Pointers

- Normative rules: [Architecture Standard](docs/standards/architecture.md)
- Product direction: [Project Overview](docs/PROJECT_OVERVIEW.md)
- Approved slice: [Milestone 1 — Cited RAG](docs/specs/milestone-1-cited-rag.md)
- Milestone 2 job-store rationale: [ADR 0001](docs/adr/0001-postgresql-ingestion-job-store.md)
- PDF citation provenance rationale: [ADR 0002](docs/adr/0002-pdf-citation-provenance.md)
- PDF extraction/versioning rationale: [ADR 0003](docs/adr/0003-versioned-pdf-extraction-adapter.md)
- Isolated extractor budget rationale: [ADR 0004](docs/adr/0004-isolated-pdf-extractor-budget.md)
- Fenced retry policy rationale: [ADR 0005](docs/adr/0005-fenced-ingestion-retry-policy.md)
- Document Version-owned source object rationale: [ADR 0006](docs/adr/0006-document-version-owned-source-objects.md)
- Page-bounded PDF chunking rationale: [ADR 0007](docs/adr/0007-page-bounded-pdf-chunking.md)
- Ingestion idempotency/generation rationale: [ADR 0008](docs/adr/0008-ingestion-idempotency-and-generations.md)
- Ingestion job HTTP contract rationale: [ADR 0009](docs/adr/0009-ingestion-job-http-contract.md)
- Document Version reprocess rationale: [ADR 0010](docs/adr/0010-document-version-reprocess-api.md)
- Explicit current Document Version rationale: [ADR 0011](docs/adr/0011-explicit-current-document-version-pointer.md)
- Serving state projection rationale: [ADR 0012](docs/adr/0012-serving-state-projection.md)
- PDF source/derivation identity rationale: [ADR 0013](docs/adr/0013-pdf-source-versus-derivation-identity.md)
