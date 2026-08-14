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
- A **Failed-upload Diagnostic Artifact** is a source or staging object from a failed upload that
  never became the Original Source Object of a committed Document Version. Its separate, bounded
  diagnostic-retention lifecycle is defined by the Object Lifecycle Retention decision in ADR
  0006; it never transfers to an Original Source Object merely because an Ingestion Job reaches a
  terminal state.
- An **Object Lifecycle Work Item** is a durable, Workspace-scoped cleanup or reconciliation work
  identity independent of an Ingestion Job outcome. Its attempt history, lease/fencing capability,
  operation-ID replay, and deletion-preparation generation belong to Object Lifecycle Maintenance;
  it can never make a retained Original Source Object eligible for deletion.
- Object Lifecycle Work transitions only `queued -> processing -> retry_scheduled | succeeded |
  failed`. Its independent Object Lifecycle Retry Policy V1 permits four total attempts and uses
  full-jitter windows of 5 seconds, 30 seconds and 2 minutes; cleanup failure is observable but
  never reverses the related Ingestion Job outcome.
- **OperationalObservability** collects authoritative ingestion/lifecycle snapshots and evaluates
  immutable versioned Alert Configuration V1. It emits typed low-cardinality metrics and alerts;
  Workspace, object, job, attempt and source identities are never telemetry labels or annotations.
- **S3ObjectStore** is the S3-compatible ObjectStore adapter selected by typed runtime
  configuration. Its provider boundary exposes only streaming put/get, head and delete through an
  auditable capability client; caller code never selects keys or invokes SDK capabilities directly.
- An **Embedding Set** is the vectorization of one Chunk Set under exactly one Embedding
  Configuration.
- A completed Embedding Set may become a Document's **Active Embedding Set**; inactive historical
  sets remain immutable for traceability and are excluded from retrieval.
- An **Evidence Set** is the ordered collection of retrieved Chunks supplied to answer generation.
- An **Evidence Alias** is a request-scoped opaque identifier such as `E1`; application code owns
  its mapping to one Chunk and providers never receive database Chunk IDs.
- A **Retrieval Configuration** is an immutable definition of candidate count, similarity
  threshold, evidence count, token budget, overlap-redundancy policy and retrieval strategy/fusion
  version. Its contract is retrieval-strategy-agnostic to application callers.
- **Retrieval v2 authority proposal:** `retrieval-m3-rrf-v2` is a separate immutable upstream
  configuration proposal. It uses a production-supported semantic embedding configuration,
  explicit versioned OR lexical policy, a calibration-selected numeric vector threshold,
  `candidate_k=8`, and separately versioned reproducible `rrf-v2` fusion. `m3-dataset-v1` is development-exposed for
  retrieval improvement and cannot evidence unbiased v2 improvement; a later frozen held-out
  dataset is required. It must be approved and independently verified before Issue #51 can resume;
  `retrieval-m3-rrf-v1` and `m3-corpus-v1` remain immutable.
- **Hybrid Retrieval** is one implementation of the `AnsweringStore.retrieve_candidates` seam. It
  combines vector and PostgreSQL full-text candidates inside the PostgreSQL adapter, applies
  Workspace and Active Embedding Set predicates in every branch before fusion, deduplicates by
  canonical Chunk identity, and emits one deterministic total order. The initial fusion policy is
  versioned `rrf-v1`: each branch returns at most `candidate_k`, ranks its own deterministically
  ordered results, and contributes `1 / (60 + rank)` to the canonical Chunk's fusion score; final
  ordering is `fusion_score DESC → chunk_id ASC`.
- **Production Retrieval V2** is the Issue #56 configuration family. Both
  `retrieval-m3-vector-v2` and `retrieval-m3-rrf-v2` use the calibrated vector threshold
  `0.657410732025` and `vector_candidate_k = 8`; hybrid v2 additionally uses
  `fts-m3-or-v2`, `fts_candidate_k = 8`, and `rrf-v2`. The paired configurations preserve the
  same downstream Evidence Selection policy and differ only by strategy, FTS candidate budget,
  lexical policy, and fusion policy.
- Initial PostgreSQL FTS policy `fts-v1` uses explicit `simple` configuration:
  `to_tsvector('simple', chunk_text)`, `plainto_tsquery('simple', query_text)`, eligibility with
  `@@`, and `ts_rank_cd(..., 0) DESC → chunk_id ASC`. It does not depend on database defaults,
  `websearch_to_tsquery`, stemming or language-specific stop-word behavior.
- **Candidate Budget** (`candidate_k`) is the per-branch retrieval limit and is distinct from the
  final Evidence Set top-k/count limit.
- **Evidence Sufficiency Policy** is a separately versioned policy that decides whether retrieved
  evidence is sufficient for generation or refusal. RRF fusion score is a ranking signal only and
  is never used as an uncalibrated evidence-confidence threshold. Under the initial policy, the
  vector branch applies `min_similarity` before rank/RRF contribution; the full-text branch applies
  its native eligibility and rank without conversion to similarity; only eligible contributions
  enter fusion. A canonical Chunk with an ineligible vector result and eligible full-text result is
  retained as a full-text-only candidate. An empty Evidence Set deterministically refuses, while a
  non-empty Evidence Set still permits a structured Generation Provider refusal.
  Initial M3 has no independent numeric post-fusion threshold: after fusion, Evidence Selection
  applies overlap, chunk-count and token-budget policies. A future post-fusion threshold requires
  its own immutable/versioned policy with defined metric and semantics.
- A **Retrieval Candidate Decision** records a candidate's raw score and whether it was selected or
  excluded by threshold, redundancy or token budget, together with ordered rank and retrieval
  provenance sufficient to analyze vector, full-text and fusion contributions without exposing SQL
  details through the application interface. For hybrid retrieval it records canonical Chunk
  identity, fused retrieval rank, fusion score, and a closed decision/reason taxonomy. Branch
  observations are separate from fused outcomes: vector status is `ELIGIBLE`, `BELOW_THRESHOLD`,
  or no contribution; full-text status is `ELIGIBLE`, `INELIGIBLE`, or no contribution. Only
  eligible branch contributions create a fused candidate. A fused candidate's final decision is
  `SELECTED`, `REDUNDANT_OVERLAP`, `BUDGET_EXCEEDED`, or `ELIGIBLE_NOT_SELECTED`; its reason
  distinguishes `TOKEN_BUDGET` from `CHUNK_COUNT_LIMIT`.

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
- A **Claimed Attempt** is an immutable application capability for one Ingestion Job attempt. It
  binds the job and worker to one lease version, attempt number, start time, deadline and lease
  expiry; it is not an ORM snapshot. Heartbeats and outcome transitions consume this capability
  but still prove ownership against the current, unexpired database lease.
- An **Ingestion Job Attempt** is the durable history of one started attempt. Its attempt number is
  the parent job's incremented `attempt_count`; at most one attempt per job is open. Claim inserts
  it, closure records one durable disposition and retry decision, and a closed attempt is
  immutable. Current lease expiry remains on the job projection because heartbeats do not rewrite
  attempt history.
- While processing, explicitly named current-attempt fields on the job projection exactly mirror
  its one open attempt and are cleared atomically on exit; they are never pseudo-history. Attempt
  history calls the claim-time expiry `initial_lease_expires_at`, while heartbeat-renewed expiry
  exists only on the job projection.
- Public job states are `queued`, `processing`, `retry_scheduled`, `succeeded`, `superseded` and
  `failed`. Upload responses always include `ingestion_job_id`, `submission_outcome` and `status`;
  non-terminal create/reuse returns `202`, while terminal idempotency replay or fingerprint
  deduplication returns `200`. Submission outcomes are `created`, `idempotency_replay` and
  `deduplicated`.
- Durable job transitions are only `queued -> processing`, `retry_scheduled -> processing`, and
  `processing -> retry_scheduled | succeeded | superseded | failed`. Processing corresponds to
  exactly one open attempt whose number equals `attempt_count`; entering processing increments
  both attempt count and lease version once, while heartbeat and exit keep the lease version.
  Terminal states have no outgoing transition.
- `attempt_count` counts attempts started, including the initial attempt; `max_attempts` is the
  total budget. Failed jobs expose safe `failure_reason` values `retry_exhausted`,
  `terminal_input`, `terminal_config` or `resource_limit`. Polling returns UTC RFC 3339 timestamps,
  retry scheduling hints, terminal result/error metadata and no-store caching; clients add jitter.
- Counter constraints are state-specific: queued jobs have zero attempts; processing and terminal
  jobs have between one and `max_attempts`; retry-scheduled jobs have at least one but fewer than
  `max_attempts`. A final counted attempt cannot schedule another retry.
- A `superseded` outcome does not schedule or consume an additional retry attempt. The
  already-started attempt remains counted in `attempt_count`; because the job becomes terminal,
  any remaining attempt capacity is irrelevant.
- Job status may expose `target_document_version_id`, `current_document_version_id` and nullable
  `served_document_version_id` resolved from the active Embedding Set in one database snapshot.
  Server-computed `serving_state` is `unavailable`, `current` or `previous`; it describes retrieval
  serving, not the Ingestion Job lifecycle. A future Document detail/status projection should
  expose the same serving view.
- The durable job store is PostgreSQL for Milestone 2. Workers claim eligible jobs atomically
  (including `FOR UPDATE SKIP LOCKED` where appropriate), do not hold a database transaction
  during parsing, chunking or embedding, and record bounded retries with exponential backoff,
  `next_attempt_at`, attempt count and terminal failure.
- Lease expiry is a retryable worker failure, not an immediate direct reclaim. Recovery
  conditionally closes the expired attempt and atomically changes the job to `retry_scheduled`, or
  to exhausted terminal failure when the counted attempt already equals `max_attempts`. A later
  invocation may claim the next attempt only after `next_attempt_at` is due.
- Expiry recovery uses an immutable optimistic observation, not an ownership capability. The
  conditional transition revalidates attempt, worker, lease generation, counters and the exact
  observed lease expiry before closing history. It preserves `lease_expired` as the observed cause
  separately from the policy result. Even zero-delay recovery must commit `retry_scheduled` before
  a separate claim can start the next attempt.
- `ProcessIngestionJob.run_once` deterministically tries at most one expired-attempt recovery before
  one normal claim. A successful recovery returns immediately; a stale/not-expired observation may
  fall through once to claim. Each invocation therefore durably applies at most one recovery or
  processes at most one newly claimed handler attempt. Its six outcomes are no eligible job,
  succeeded, superseded, retry scheduled, terminal failure and lease lost.
- Each worker-coordination mutation has one logical operation ID reused across transport retries
  and authoritative read-back. Attempt history binds claim and closure IDs to immutable request
  identity and durable results. A historical claim is executable only while its attempt remains
  current and leased; indeterminate persistence never becomes a lifecycle result or permission to
  run business work.
- An **Attempt Runner** owns only bounded execution mechanics for one Work Handler invocation. It
  publishes a single immutable monotonic-timestamped completion, supports idempotent cancellation
  and logical detachment, and never owns persistence or lifecycle policy. Detachment discards late
  results without terminating the handler. A bounded permit is reserved before claim so capacity
  failure cannot strand a newly claimed job; detached work retains its permit until it actually
  exits.
- Retry policy is four attempts total (one initial plus three retries) with versioned full-jitter
  windows of 5 seconds, 30 seconds and 2 minutes, capped at 5 minutes. Lease duration is 2
  minutes with a 30-second heartbeat extending to `now + 2 minutes`; maximum attempt runtime is
  separately bounded at 15 minutes. Every heartbeat and commit checks `worker_id`,
  `lease_version` and an unexpired lease. Expiry loses ownership even when no other worker has
  reclaimed the job.
- Retry Policy V1 applies one coordinator-level cause taxonomy to handler/provider/database
  failures, unexpected worker exceptions, attempt timeout and lease-expiry recovery. A retryable
  cause after attempts 1, 2 or 3 samples exactly once from full-jitter windows `[0, 5s]`,
  `[0, 30s]` or `[0, 2m]`; zero is valid. A retryable cause at attempt 4 is exhausted, while a
  non-retryable cause is terminal at any attempt, and neither consumes randomness. Windows are
  exact durations and any future nominal window above 5 minutes is clamped before sampling.
- **Failure Cause V1** is the single closed taxonomy of facts observed by worker coordination;
  causes do not encode retryability. A pure versioned mapping translates handler-specific failure
  kinds into it, while supervisor timeout and database-observed lease expiry originate directly.
  `LEASE_EXPIRED`, not an unverifiable worker-crash claim, records abandoned ownership. Attempt
  history persists canonical cause and version before Retry Policy V1 chooses the disposition.
- Worker timing has two independent clock domains. Fresh PostgreSQL wall-clock samples own durable
  timestamps, eligibility and lease fencing; transaction-start timestamps cannot revive an
  expired lease. An injected monotonic clock owns only local heartbeat cadence and attempt-runtime
  scheduling. The persisted deadline is audit evidence of the intended runtime, while supervisor
  disposition decides handler completion versus timeout.
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
  by `reprocess_of_job_id`; the old job and attempt budget remain immutable. A `superseded` job does not
  block explicit reprocessing, and reprocessing an older version never automatically replaces a
  newer current version.
- **Reprocess Document Version** is the explicit backend operation for rebuilding the current
  Document Version. It snapshots immutable configuration versions at enqueue time using
  `same_as_job` or `current`, records `reprocess_of_job_id`, resets the attempt budget and never
  resolves configuration again in the worker. `same_as_job` requires an explicit
  `config_source_job_id`; `current` snapshots the active immutable configuration without a source
  Job selector. The HTTP handler authorizes, checks source-object availability and enqueues; the
  worker reads the Original Source Object.
- The Issue #19 public Job projection is the stable HTTP view over this lifecycle. It includes
  attempt/max-attempt counts, retry scheduling and polling hints, Workspace-scoped target/current/
  served pointers, `serving_state`, UTC RFC 3339 lifecycle timestamps, safe terminal failure
  metadata, and a successful `result.document_version_id` only after derivation and activation
  commit. The projection is cache-free; `next_attempt_at` is present only for `retry_scheduled`.
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
  evaluation, including the ordered fused candidate set before Evidence Selection; it is not
  conversation state and production retrieval/answering never depends on it. Trace-level retrieval
  metadata includes retrieval configuration ID, fusion-policy version, and embedding/chunk-set
  provenance once per invocation. A candidate's fused rank is retrieval rank, not its later
  Evidence Set position.
- An **Evaluation Case** is a versioned question fixture. Its contract separates retrieval
  relevance applicability and acceptable relevant Chunks from answer expectations (including
  non-empty required facts for an answerable case) and evidence expectations (expected source
  Documents and acceptable cited Chunks). An insufficient-evidence case has explicit refusal
  expectations and non-applicable retrieval relevance; it is not a retrieval miss. An Evaluation
  Dataset version includes both case definitions and gold relevance/evidence judgments.
- The **Milestone 3 Evaluation Dataset V1** is the 50-case fixture set pinned by
  `m3-dataset-v1` and `m3-corpus-v1`. It covers lexical/exact-match, semantic/paraphrase,
  multi-source, and insufficient-evidence/refusal behavior. Its dataset and corpus/Chunk Set
  manifests are immutable inputs; metric execution and reporting are separate later work.
- An **Evaluation Report** separates structural pipeline checks, retrieval metrics, generation
  semantic metrics and system metrics with versioned dataset/configuration/scorer provenance. A
  vector-only baseline and hybrid result are a paired comparison: immutable corpus and Chunk Set
  provenance, dataset, embedding, generation and scorer settings remain fixed; only Retrieval
  Configuration differs.
- A **Chunk Set Persisted Instance Identity** is the production `ChunkSet.id` UUID. It identifies
  one stored derivation instance and is not portable corpus provenance.
- A **Chunk Set Provenance Identity** is an immutable manifest identity such as
  `chunk-set-m3-v1`. It identifies the released corpus/Chunk Set derivation independently of a
  production UUID.
- An **M3 Evaluation Environment Binding** is an immutable run/environment artifact that verifies
  `dataset_manifest_identity`, `corpus_manifest_identity`, `chunk_set_provenance_id`, Workspace
  ID, Retrieval Configuration ID, and one production binding entry per manifest `source_key`.
  Each entry contains its `source_key`, persisted Document Version UUID and persisted Chunk Set
  UUID. Its entries cover exactly the corpus manifest sources: no missing, extra or duplicate
  source is valid. Before measurement, bootstrap also proves the retrieval-eligible active corpus
  source-key set exactly equals the manifest: each manifest source has exactly one active
  manifest-matching Document Version and corresponding Chunk Set, and no extra active source or
  document exists. Missing, extra, duplicate or multiple-active source/version is a setup failure.
  It proves the configured production corpus/chunking derivation matches the manifest; it is never
  inferred from a current, latest, or named resource.
- **M3 Evaluation Chunk Identity** is `(chunk_set_provenance_id, source_key, ordinal)`. Dataset
  gold shorthand `source_key#ordinal` becomes canonical only after the corpus manifest scopes it
  with `chunk_set_provenance_id`; it is not globally canonical. The evaluator projects candidates
  from the exactly correlated production trace and, for that candidate's `source_key`, verifies
  the exact `(source_key, persisted Document Version UUID, persisted Chunk Set UUID)` binding
  triple before it replaces the UUIDs with the bound provenance identity. The trace/evaluation
  reader must project the persisted Document Version UUID, or must instead establish an equivalent
  mandatory verified source → Document Version → Chunk Set relation; version verification cannot
  be skipped. Database `chunk_id`, persisted Document Version UUID and persisted Chunk Set UUID
  are operational/environment provenance only and never participate in portable gold matching.
- **M3 Retrieval Metrics V1** is the versioned evaluation metric contract `m3-retrieval-metrics-v1`.
  It pins `k = 8` for comparable runs and records its identity and `k` in report provenance. It
  matches M3 Evaluation Chunk Identities against the ordered fused candidates from the exactly
  correlated trace. For each successful, retrieval-applicable case with non-empty gold set `G`,
  `Recall@k = |G ∩ top_k| / |G|`; `k` limits Recall only. `RR = 1 / r` for the first rank `r` in
  the entire ordered fused candidate sequence containing a member of `G`, or `0` when there is no
  hit. `MRR` and aggregate `Recall@k` are arithmetic macro-means of their per-case values. A
  candidate list shorter than `k` uses all available candidates while `|G|` remains the Recall
  denominator. Valid retrieval misses contribute zero scores; non-applicable cases and
  execution/observation failures have no quality score and are excluded from every
  retrieval-quality denominator. `MRR` has no cutoff; any future cutoff metric must be named and
  versioned explicitly (for example, `MRR@k`).
- **EvaluationEnvironmentBootstrap** is a control-plane application seam. It provisions or reuses
  one isolated Evaluation Workspace, a scoped API credential obeying production credential
  invariants, and the manifest-bound corpus, then writes the verified M3 Evaluation Environment
  Binding. Raw credentials are runtime-only/redacted. This seam never performs measured Q&A,
  evaluation retrieval, or a public acceptance-only admin HTTP operation.
- **M3 Evaluation Bootstrap Lifecycle** runs before the production API process starts. Its
  idempotent control-plane Workspace seam provisions or reuses the isolated persisted Workspace
  and its normal ingestion/application path materializes the bound corpus. Bootstrap generates one
  credential scoped to that persisted Workspace under normal API credential invariants. Its raw
  value is ephemeral and is returned only to the runtime launcher; it is never placed in the
  immutable Environment Binding, logs, or committed evidence. The launcher materializes the
  credential's normal startup configuration (`KNORA_API_CREDENTIALS_JSON` or typed equivalent)
  before `create_app()`; the Q&A process then uses its ordinary `ApiKeyAuthenticator`, with no
  evaluation-only auth path or credential mutation during measurement. Evaluators consume the
  credential only. Teardown ends this ephemeral credential lifecycle; #51 requires neither
  hot-reload nor a standalone revocation capability.
- A **Sealed M3 Evaluation Environment** is an evaluation control-plane/orchestration ownership
  boundary held exclusively by one run from before its authoritative closure snapshot until teardown.
  Bootstrap may materialize the corpus before seal, but only after `seal.acquire` succeeds may the
  run verify corpus closure and capture Binding V3/retrieval-configuration provenance as authority
  for measured Q&A. The contract requires no corpus/retrieval-provenance mutation during seal;
  Q&A and Question Trace persistence remain allowed. The guarantee may come from isolated topology,
  exclusive run ownership, restricted actors/credentials, or an existing centralized mutation
  guard; #51 does not require evaluation-specific checks retrofitted into every production mutation
  path. If exclusive ownership cannot be established, setup fails before measurement. After Q&A,
  while still sealed, control plane re-verifies closure, V3 bindings and Retrieval Configuration
  against the sealed snapshot. Drift invalidates the run as environment/observation failure and
  publishes no quality scores. Seal and post-run verification sit outside Q&A intervals and never
  enter `end_to_end_latency_ms`.
- **RetrievalConfigurationResolver** is the production Q&A composition seam that resolves an
  immutable Retrieval Configuration from supported deployment/workspace configuration. The Q&A
  request carries no evaluation override. Its resolved ID is persisted in the trace. M3 #51 pins
  its Evaluation Environment Binding to `retrieval-m3-rrf-v1`; #52 uses separate configured
  baseline/hybrid runs through the same production HTTP contract.

### Provider boundaries

- A **Generation Provider** turns a Question and its Evidence Set into generated answer text.
- An **Embedding Provider** turns text into vectors used by ingestion and retrieval.
- An **Embedding Configuration** is an immutable embedding-space identity comprising provider,
  model, dimensions, distance metric, provider/deployment contract, input normalization and input
  policy. `embedding-gemini-m1-v1` is the Production Retrieval V2 identity: Gemini API `v1beta`
  `models.embedContent`, model `gemini-embedding-2`, 1536 dimensions, cosine distance, and
  `gemini-m3-qa-asymmetric-v1`. Document and query embeddings share one space but intentionally
  use role-specific, NFKC-normalized inputs. Changing that policy creates a new configuration and
  invalidates calibration.
- A **Deterministic Local Provider** exercises orchestration, schemas, citation/refusal behavior
  and trace persistence without representing semantic quality.
- An **OpenAI-compatible Provider** supplies model-backed generation or embeddings for demos and
  semantic evaluation when enabled by runtime configuration.
- A **Gemini Embedding Provider** supplies Production Retrieval V2 embeddings through the native
  Gemini API. It uses exactly one text Content per logical Chunk or query,
  `EmbedContentConfig.outputDimensionality = 1536`, validates 1536 returned values, and stores
  provider output without client normalization. Its credential exists only at runtime.

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
- **Evaluation → Question Trace**: `HttpEvaluationExecutor` calls the production question endpoint
  and reads the exact opaque trace returned by that request under the exact `(workspace_id,
  trace_id)` correlation pair; it never uses an evaluation-only retrieval path or a fallback by
  timestamp, question, or recency. Missing/mismatched/incomplete trace provenance is an evaluation
  observation failure, not a zero retrieval-quality score. The trace's ordered results and
  versioned retrieval provenance support Recall@k and MRR, while citation correctness is measured
  from the final public answer and citations. Semantic citation scoring receives only public answer
  and public citation excerpts/source locators, never hidden retrieved chunks.
- **EvaluationEnvironmentBootstrap → Production Q&A**: bootstrap completes before measurement and
  is not part of the timed/requested Q&A path. The evaluator reads its binding, verifies the trace
  Workspace, resolved Retrieval Configuration and persisted Chunk Set UUID, then scores only the
  corresponding provenance-scoped canonical references.
- **M3 Retrieval Metrics → Evaluation Report**: report provenance pins
  `m3-retrieval-metrics-v1` and `k = 8`. Per-case and aggregate Recall@k/MRR operate only on
  successful observations whose `retrieval_relevance.applicable` is true and whose canonical gold
  relevant Chunk set is non-empty. Refusal correctness remains a separate outcome.
- **Evaluation duration observations** are per-successful-observation projections: the correlated
  trace supplies server `retrieval_latency_ms`, while the executor measures
  `end_to_end_latency_ms` around the Q&A request/response. The values and their source/provenance
  are reported independently. M3.2 defines no aggregate duration statistic; aggregation requires
  its own approved metric contract.
- **Evaluation Report → Improvement Claim**: an improvement is pre-defined, not selected after a
  run: comparable provenance and zero observation failures are required; primary retrieval metrics
  must improve, citation/refusal guardrails may not regress beyond pre-defined policy, and all
  latency trade-offs are disclosed.
- **Evaluation Finding** is a versioned, stage-assigned failure annotation with one primary
  category and optional contributing categories. `LEXICAL_MISS` and `SEMANTIC_MISS` are branch
  misses; `FUSION_RANKING_ERROR` requires gold evidence in the eligible branch union but ranked
  incorrectly after fusion; `EVIDENCE_SELECTION_ERROR` occurs only after fusion when relevant
  evidence is wrongly excluded by overlap or budget selection. A correct insufficient-evidence
  refusal is a non-failure evaluation outcome for refusal correctness, not a finding.
- An **Evaluation Reproducibility Record** is immutable report metadata comprising dataset version,
  corpus/Chunk Set digest, Retrieval Configuration ID, generation/scorer versions, Git commit, and
  artifact schema version. Normalized reports, manifests, findings and selected-improvement records
  are repository artifacts; raw traces and secrets remain only in authorized persistence.
- **Question Trace → Client**: an opaque, workspace-authorized `trace_id` permits debugging without
  granting general trace access.
- **Question Request flow**: retrieve → complete generation → validate structured output and
  citation markers → resolve Citation Projection → persist Question Trace → return response.

## Context Pointers

- Normative rules: [Architecture Standard](docs/standards/architecture.md)
- Product direction: [Project Overview](docs/PROJECT_OVERVIEW.md)
- Completed slice: [Milestone 1 — Cited RAG](docs/specs/done/milestone-1-cited-rag.md)
- Milestone 2 module ownership: [Milestone 2 Module Seams](docs/design/milestone-2-module-seams.md)
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
- Issue #19 implementation and acceptance evidence: [.agents/issue-19-feature-delivery.json](.agents/issue-19-feature-delivery.json)
- Issue #50 dataset contract and acceptance evidence:
  [.agents/manual-tests/milestone-3/50-evaluation-dataset.evaluations.jsonl](.agents/manual-tests/milestone-3/50-evaluation-dataset.evaluations.jsonl)
