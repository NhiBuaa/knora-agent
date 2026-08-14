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
- Knora uses `1536` dimensions, PostgreSQL `vector(1536)` and cosine distance. Approved immutable
  Embedding Configurations are `embedding-local-m1-v2` for deterministic-local structural tests
  (`text-embedding-3-small` as a model label), `embedding-openai-m1-v1` for OpenAI-compatible
  `text-embedding-3-small`, and `embedding-gemini-m1-v1` for the native Gemini API `v1beta`
  `models.embedContent` contract with `gemini-embedding-2`. The completed Milestone 1 spec records
  the historical Gemini semantic-baseline meaning; final Issue #56 authority R9 supersedes that
  runtime meaning for this configuration ID.
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
- `embedding-gemini-m1-v1` pins deployment identity
  `gemini-api-generativelanguage-googleapis-com-v1beta`, `utf8-nfkc-v1`, input policy
  `gemini-m3-qa-asymmetric-v1`, and `EmbedContentConfig.outputDimensionality = 1536`. Query input is
  exactly `task: question answering | query: {content}` and document input is exactly
  `title: none | text: {content}` after NFKC normalization. Each logical Chunk or query uses
  exactly one text Content; document identity and evaluation gold metadata are forbidden inputs.
  The adapter validates 1536 returned values and must not client-normalize Gemini output.
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
  increments both attempt count and a fencing/lease version in the same transaction. Candidate
  selection and claim must not be separate operations. A worker whose lease is expired or fenced
  out must not publish a result. Expiry recovery first schedules a bounded retry or records
  exhaustion; another worker may claim only when that retry is due.
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
- Each started attempt has one durable history row whose number equals the atomically incremented
  job `attempt_count`. A partial unique constraint permits at most one row with `closed_at IS NULL`
  per job. Claim inserts an open row; one transaction closes it exactly once and applies the
  corresponding job projection transition. Closed rows reject all later updates. Heartbeats update
  only the current lease on the job projection, while attempt history snapshots its lease version
  and retains retry policy version, scheduled-next-attempt time and safe outcome/failure metadata.
- Any current-attempt timing duplicated on the job projection is explicitly named
  `current_attempt_number`, `current_attempt_started_at` and `current_attempt_deadline_at`. While
  processing these exactly match the one open attempt; the transaction leaving processing clears
  them. Attempt history names its claim-time lease snapshot `initial_lease_expires_at`; only
  `ingestion_jobs.lease_expires_at` reflects heartbeat renewal.
- The only durable job transitions are `queued -> processing`, `retry_scheduled -> processing`,
  and `processing -> retry_scheduled | succeeded | superseded | failed`. Terminal states have no
  outgoing edge. Queued requires `attempt_count = 0`; processing requires
  `1 <= attempt_count <= max_attempts`; retry-scheduled requires
  `1 <= attempt_count < max_attempts`; terminal states require
  `1 <= attempt_count <= max_attempts`. Processing has exactly one open attempt and its number
  equals job `attempt_count`.
- Lease version has one canonical initial value and increments exactly once on each successful
  transition into processing. Heartbeat and every transition out of processing preserve it. Exit
  clears active worker and lease expiry while retaining the final generation for fencing history.
- Entering processing and inserting its open attempt are one transaction. Leaving processing,
  closing that attempt and updating the job projection are one transaction. Database constraints,
  deferrable commit-time constraint triggers or an equivalent mechanism enforce the cross-table
  rule that processing is equivalent to exactly one open attempt while allowing valid intermediate
  statement order inside the transaction; a partial unique index alone proves only at-most-one.
  Retry schedule on the job matches the latest closed attempt's retry snapshot, and terminal job
  state matches the latest attempt disposition.
- Job `terminal_at` is null in non-terminal states and required in terminal states; attempt
  `closed_at` records durable attempt closure. Succeeded and superseded jobs have no failure
  reason; failed jobs require one canonical safe failure reason. Retry and terminal states have no
  active lease.
- For operations requiring a fencing token, ownership is checked before requested-transition
  legality: stale or non-current ownership returns `FENCED`; current valid ownership requesting an
  illegal transition returns `INVALID_TRANSITION`. A duplicate outcome call after ownership was
  cleared is fenced, not a second terminalization.
- Milestone 2 uses four attempts total (one initial plus three retries). Backoff is a versioned
  full-jitter policy with windows of 5 seconds, 30 seconds and 2 minutes, capped at 5 minutes;
  the windows are not described as exponential without an explicit formula. Lease duration is 2
  minutes, heartbeat is every 30 seconds and extends to `now + 2 minutes`, and maximum attempt
  runtime is separately bounded at 15 minutes. Every heartbeat and commit checks `worker_id`,
  `lease_version`, an unexpired lease and the required job state. Expiry loses ownership even if
  no other worker has reclaimed the job; an expired worker cannot revive its old lease.
- PostgreSQL wall clock is authoritative for persisted attempt start, lease expiry, deadline,
  closure and retry timestamps and for claim/retry eligibility and lease fencing. Every
  lease-sensitive transition samples fresh database time at its linearization point after all
  potentially blocking lock acquisition, then reuses that sample for predicates and written
  timestamps. Transaction-start time (`now()`, `CURRENT_TIMESTAMP` or equivalent) must not let a
  transaction that waited on a lock revive expired ownership. Failure to obtain authoritative
  database time is an infrastructure failure; application wall clock is never a fallback.
- An injected monotonic clock separately owns local 30-second heartbeat cadence and 15-minute
  elapsed-runtime scheduling. It is never compared with persisted database timestamps. Supervisor
  monotonic state decides handler completion versus timeout; persisted `deadline_at` records the
  intended deadline for audit and is not a second success-finalization predicate in Issue #17.
  PostgreSQL remains the final arbiter of lease ownership.
- Retry policy returns a typed relative delay and policy metadata. Persistence anchors
  `next_attempt_at` to fresh database time without rerolling jitter, choosing a window, clamping,
  classifying retryability or deciding exhaustion.
- Retry Policy V1 uses exact non-floating durations and the same closed coordinator-level cause
  taxonomy for handler/provider/database failures, unexpected worker exceptions, attempt timeout
  and lease-expiry recovery. Retryable causes after attempts 1, 2 and 3 consume exactly one random
  sample from inclusive full-jitter ranges `[0, 5s]`, `[0, 30s]` and `[0, 2m]`; zero delay is
  valid. Retryable failure at attempt 4 is exhaustion. Non-retryable failure is terminal at every
  attempt, including attempt 4, and neither terminal nor exhausted decisions consume randomness.
  A future nominal window above 5 minutes is clamped before sampling; no artificial 5-minute V1
  retry is introduced. Production randomness is process-local decorrelation, not a security
  boundary or a fixed/shared replica seed.
- Every scheduled attempt closure records retry policy version, jitter algorithm/version, selected
  upper bound, chosen exact delay and database-anchored `next_attempt_at`. Persisting PRNG state is
  unnecessary.
- Failure Cause V1 is a single closed/versioned coordinator-level taxonomy of observed facts. It
  includes provider/database/storage transient observations, unexpected ordinary worker exception,
  attempt timeout, lease expiry, invalid/unsupported input, invalid configuration, deterministic
  per-input configured processing-limit breach and vector mismatch. Cause does not encode
  retryability; Retry Policy V1 alone maps it to schedule, terminal failure or exhaustion.
- `WORKER_CRASH` is not a V1 cause. Crash, partition, process pause, machine loss and heartbeat
  failure are indistinguishable to durable coordination and are recorded as `LEASE_EXPIRED` only
  when recovery proves expiry. Attempt timeout remains distinct because supervisor monotonic time
  observes it directly.
- A pure/versioned cause mapper translates handler-specific `WorkFailed.failure_kind` into Failure
  Cause V1. Raw provider, SQL or exception text is never persisted; known categories map to bounded
  allowlisted safe codes and unknown ordinary exceptions map to `WORKER_UNEXPECTED`, with raw
  diagnostics restricted to internal telemetry.
- Coordination-store database/network failure—including ambiguous commit—is not
  `DATABASE_TRANSIENT`; it follows persistence/indeterminate semantics. That cause is available
  only when the business-work layer legitimately observes a transient database dependency.
- Lease-expiry recovery closes the expired attempt and atomically moves
  the job to `retry_scheduled`, or to `failed/retry_exhausted` when the final counted attempt has
  expired. It never directly creates a replacement attempt or exceeds `max_attempts`.
- Policy treats known provider/storage/database transients, unexpected worker exceptions, attempt
  timeout and lease expiry as retryable in V1. Invalid/unsupported input, invalid pinned
  configuration, deterministic per-input processing-limit breach, deterministic parser failure and
  vector mismatch are terminal. Temporary provider throttling/quota/capacity remains a provider
  transient rather than deterministic resource-limit cause.
- Expired-attempt observation is an immutable optimistic snapshot, not a fencing token, lock or
  mutation capability. It contains job/attempt identity, worker, lease version, exact observed
  lease expiry, attempt count and maximum attempts. Conditional recovery revalidates every field;
  an expiry changed by heartbeat makes the observation stale even when lease version is unchanged.
- Expiry recovery results are disjoint: `STALE_OBSERVATION` means the observed snapshot is no
  longer current, while `NOT_EXPIRED` means it remains exactly current but fresh database time is
  before its lease expiry. A matching snapshot paired with a policy decision inconsistent with
  remaining capacity is `INVALID_DECISION` or an explicit invariant error, never a race or
  infrastructure failure.
- Attempt history records observed closure cause, canonical failure cause/version, policy version and
  policy result separately. An abandoned final attempt therefore retains `lease_expired` and
  `LEASE_EXPIRED` alongside `RetryExhausted`, while the job projection records
  `failed/retry_exhausted`.
- Normal claim never selects a processing row, even when its lease is expired. Canonical recovery
  is `processing(expired) -> retry_scheduled | failed`; when retry is scheduled, only a later due
  claim creates the new attempt. Zero delay does not collapse these transactions.
- `ProcessIngestionJob.run_once` has deterministic recovery-first precedence. It observes at most
  one expired attempt; a durably applied recovery returns immediately, including at zero delay.
  No observation or a stale/not-expired recovery falls through exactly once to an atomic claim of
  at most one queued or due retry-scheduled job. It does not loop recovery observation in the same
  invocation. This is per-invocation behavior, not a fleet fairness guarantee.
- `RunOnceResult` is a tagged value with exactly six lifecycle variants:
  `NO_ELIGIBLE_JOB`, `SUCCEEDED`, `SUPERSEDED`, `RETRY_SCHEDULED`, `FAILED_TERMINAL` and
  `LEASE_LOST`. It may carry typed job/attempt and safe diagnostic metadata without expanding the
  lifecycle state space. Recovery race results remain internal control flow; invalid decisions are
  invariant failures; infrastructure failures are not lifecycle results.
- A lifecycle result is emitted only when the durable outcome is known. A connection failure after
  possible commit must be reconciled through authoritative idempotent read-back when supported or
  propagated as an explicit indeterminate infrastructure failure. The coordinator must not guess
  that the transition committed or rolled back.
- An operation ID identifies one logical mutation and is generated once before its first transport
  call. Every retry/read-back reuses it. Durable records bind operation kind, job/attempt identity,
  decision/disposition and any deterministic payload fingerprint; incompatible reuse is an
  invariant failure rather than replay.
- Attempt history retains claim and transition operation IDs with their durable result. Replaying a
  committed claim additionally uses fresh database time to prove its job/attempt/token is still
  current, processing and unexpired before returning an executable Claimed Attempt. Historical
  commit without current ownership returns claim/lease loss and never claims another job with the
  same operation ID.
- Replaying a committed outcome or expiry recovery returns the recorded disposition, policy audit
  and database-anchored timestamps. It never reruns policy, consumes randomness, re-anchors delay
  or repeats business work.
- Exactly one logical heartbeat may be in flight per supervisor. The job projection retains its
  latest heartbeat operation ID and resulting lease expiry. A new heartbeat ID is forbidden until
  the prior heartbeat is authoritatively applied, fenced or reconciled. Because older heartbeat
  IDs are overwritten, database-global historical uniqueness is not claimed without a future
  operations ledger.
- Definite heartbeat fencing is lease loss. An unreconciled ambiguous heartbeat closes future
  scheduling, signals best-effort cancellation, prevents durable handler outcome commit and raises
  `CoordinationOutcomeIndeterminate`; it is not a retry cause, worker exception or run-once result.
  The exception carries only non-secret operation kind/ID and known job/attempt identity.
- A no-op claim has no durable operation record. The guarantee is at most one durable claim per
  claim operation ID: an existing attempt record replays/reconciles, while absence permits retrying
  claim against current eligibility. Exact historical replay of no eligible job and arbitrary old
  heartbeat replay are out of scope and do not justify a generic operations ledger in Issue #17.
- Claim, transition and heartbeat operation IDs use distinct code types. The coordinator generates
  globally unique values; PostgreSQL enforces uniqueness and immutable request binding within each
  retained operation kind. Separate columns do not claim cross-kind database-global uniqueness,
  and incompatible cross-kind reuse remains a programming invariant failure.
- Attempt history permits one mutation from open to closed. After `closed_at`, normal application
  role cannot update or delete the row. Any future retention/admin deletion path is separate from
  the worker-coordination API.
- Claim/recovery indexes contain stable candidate predicates only: queued status, retry-scheduled
  status ordered by retry time, and processing status ordered by non-null lease expiry. Dynamic
  database time is applied by queries after locking, never embedded in index predicates. Indexes
  are performance aids; row locks, fresh-time revalidation, fencing and transactional constraints
  provide correctness.
- Issue #17 migration adds coordination/history schema in add/backfill/validate/tighten order. Since
  pre-Issue-17 production code only creates queued jobs with zero attempts, migration asserts that
  fact and aborts on any other legacy state rather than inventing worker, lease or attempt history.
- Issue #17 defines generic typed fenced success finalization and tests it with fake payload/store,
  but its PostgreSQL migration adds no generic JSON/opaque success payload and no production
  success transition lacking activation. Issue #18 supplies the concrete data-only value/schema
  and PostgreSQL transaction that atomically commits derivation/activation with `status=succeeded`
  before production handler wiring.
- `AttemptRunner` owns only execution mechanics: start, single-assignment completion, cooperative
  cancellation and logical detachment. It has no store, fencing, retry policy, transition API or
  run-once result. Handler completion captures immutable `completed_at` from the injected monotonic
  clock at the execution boundary when the invocation returns or raises; handler and supervisor
  wall clocks are not used.
- Detachment is not termination. Completion versus detach resolves exactly once: orchestration
  accepts the completion, or permanently discards every later outcome/exception. Late completion
  is consumed into internal telemetry without finalization, retry scheduling, disposition change,
  operation-ID reuse or run-once result. Cancellation and detach are idempotent.
- Normal completion is single-assignment and consumed at most once; OS thread join is not a
  correctness primitive. Supervisor still quiesces in-flight heartbeat before durable
  finalization. Timeout/lease loss requests cancellation, detaches, quiesces heartbeat and
  proceeds without waiting for handler termination.
- Fencing protects coordination/activation commits, not arbitrary external side effects. A
  detached handler may continue provider, storage or other I/O; those effects require their own
  idempotency/deduplication. Attempt Runner is not process isolation.
- The Issue #17 thread-backed runner has fixed bounded execution capacity. `run_once` reserves a
  live single-use execution permit after recovery fallback and before normal claim. No permit
  raises an explicit operational capacity error and performs no claim. Claim-none/error releases
  the permit; accepted execution holds it until the handler actually exits, including after
  detach. This prevents unbounded stuck threads but may exhaust capacity when handlers never exit;
  Issue #18 production wiring may use a stronger bounded process-isolated runner.
- A reserved permit guarantees start acceptance and serializes runner shutdown/capacity races, so
  normal capacity refusal cannot occur after claim. Process death remains recoverable through
  lease expiry. Deterministic fake runner tests completion before observation, exact deadline,
  indefinite hold, cancellation, post-detach completion and completion/lease-loss races without
  real threads or sleeps.
- A stale activation CAS is not a terminal failure. It atomically changes `processing` to terminal
  `superseded` under the same lease/fencing predicates as other outcomes, records a terminal time
  and allowlisted outcome code, clears retry scheduling, and leaves failure reason null. The
  already-started attempt remains counted; `superseded` schedules no additional retry and unused
  attempt capacity becomes irrelevant. A fenced finalization returns lease loss instead of
  `superseded`. Exhausted attempts remain public state `failed` with safe
  `failure_reason = retry_exhausted`; a new manual reprocess never mutates the old attempt counter.
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
  `config_mode` of `same_as_job` or `current`. A `same_as_job` request must explicitly provide
  `config_source_job_id`. The selected Job must be in the authorized Workspace and target the same
  Document Version; the handler snapshots its immutable parser, normalizer, chunking and embedding
  configuration IDs. Timestamps, UUID ordering, `MAX(id)` and a hidden latest-Job rule are invalid
  selectors. A `current` request has no source selector and snapshots active immutable
  configuration IDs. Invalid, missing or mismatched source selectors reject before generation
  creation. The handler checks Original Source Object availability and enqueues without reading or
  parsing the object. The worker reads the object and never resolves mutable/current configuration.
- One logical accepted manual-reprocess request is the first processing of its scoped
  `(workspace_id, reprocess operation, Idempotency-Key)`. It creates exactly one audit record. A
  same-key/same-request replay creates none, while a fresh key creates one even when equal work
  reuses an existing processing or succeeded generation. The audit record, Idempotency Record and
  created-versus-reused durable generation decision commit atomically in one PostgreSQL transaction.
  The read-only audit projection exposes safe audit ID, Workspace ID, actor/key ID,
  `document_version.reprocess` action, target Document Version ID, requested/resolved config mode,
  resulting Job ID, created-versus-reused outcome, database-created timestamp and available opaque
  correlation ID. It never exposes raw credentials or Idempotency Keys. Rejected requests need no
  Issue #19 audit record: authentication/authorization failure, invalid/missing config mode,
  historical target or unavailable source.
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
- A failed-upload diagnostic artifact is only a source or staging object that never became the
  Original Source Object of a committed Document Version. It is retained for at least 24 hours from
  the Knora-owned durable timestamp recorded at classification; it cannot be automatically cleaned
  before expiry, and is only eligible—not required—to be cleaned afterwards. This retention is
  independent of Idempotency Record retention.
- An Original Source Object remains subject to Document Version retention regardless of a later
  failed, retry-exhausted, resource-limit, superseded, or other terminal Ingestion Job outcome. It
  may be hard-deleted only through an approved path after authoritative deletion-time checks show
  no current/active ownership constraint or citation/trace/evaluation/version-retention reference.
  Cleanup and orphan reconciliation must revalidate authoritative database ownership and Workspace
  scope immediately before deletion; stale discovery snapshots are insufficient, and an object
  attached as a retained Original Source Object since discovery must be preserved. Cleanup is
  idempotent, retries independently on failure, and cannot change submission or ingestion outcome.
- The minimum `ObjectStore` interface is streaming `put_stream`, streaming `open_read`, `head`,
  and idempotent `delete`. Objects carry Workspace identity, a server-generated opaque key,
  SHA-256 content hash, byte size and media type. ETag is not a content hash, and callers must not
  create storage paths or call a whole-object `read()` API.
- Database and object storage do not share an atomic transaction. An orphan sweeper/reconciler
  must find and clean unreferenced staging/temporary objects, retry cleanup failures, expose
  cleanup/orphan metrics and alert without reversing a committed ingestion success. Contract tests
  must run against MinIO and the configured production S3-compatible provider.
- `ObjectLifecycleMaintenance` owns asynchronous cleanup and reconciliation through its
  consumer-owned application port. PostgreSQL owns Workspace-scoped Object Lifecycle Work Items,
  their immutable attempts, lease/fencing state, operation-ID request binding, replay results, and
  deletion-preparation generation. An Ingestion Job terminalization transaction atomically records
  a deduplicated lifecycle work item with its Job/Attempt result; lifecycle retry state and outcome
  are independent and cannot change that already-durable ingestion outcome.
- A lifecycle worker claims one work item with its own lease/fencing capability and logical
  operation ID. Before destructive ObjectStore deletion it obtains a fenced delete-preparation
  capability that authoritatively revalidates Workspace, artifact class, ownership, retention
  expiry and every blocking reference. Attach and hard-deletion paths use the same lifecycle
  gateway, so a later attach fences or suppresses stale deletion. After idempotent external delete,
  completion consumes that capability. A crash between delete acknowledgement and completion is
  reconciled from durable work state plus `ObjectStore.head`; it neither repeats an unverified
  destructive effect nor changes the Ingestion Job outcome.
- Object Lifecycle Work dispatch is PostgreSQL polling, not a new broker. It atomically claims
  eligible `queued` or due `retry_scheduled` work using `FOR UPDATE SKIP LOCKED` (or equivalent),
  a lease/fencing capability and operation-ID replay. Its only transitions are `queued ->
  processing -> retry_scheduled | succeeded | failed`. Object Lifecycle Retry Policy V1 permits
  four total attempts with full-jitter windows of 5 seconds, 30 seconds and 2 minutes. Duplicate
  delivery or replay returns the one durable operation result without creating another attempt or
  external effect; failure changes only lifecycle work, metrics and alerts.
- Object Lifecycle Retry Policy V1 receives an injectable deterministic random-source abstraction at
  its application/policy boundary. Production wiring uses process-local randomness; deterministic
  tests inject a controlled sequence, and equal policy input plus sequence produces the same exact
  chosen delay. Policy logic must not read global/process randomness directly. The chosen delay is
  inside the authoritative inclusive full-jitter window and is persisted exactly. Reuse of the
  Issue #17 `RandomSource` seam is allowed when compatible but is not required.
- The Object Lifecycle random-source contract supplies one full-jitter sample for the policy's
  requested upper bound, and the policy must use that returned sample as its chosen persisted delay.
  Controlled sample X produces persisted delay X; a different valid sample Y produces Y. Calling
  and ignoring the source is invalid. No SDK/library RNG implementation or separately persisted
  jitter-version field is required.
- `OperationalObservability` owns Operational Metrics V1 collection and pure Alert Policy V1.
  Its consumer-owned `OperationalMetricsStore` port provides purpose-specific authoritative
  read-only snapshots; the PostgreSQL adapter exposes no ORM/session through it. Immutable,
  versioned `OperationalAlertConfigurationV1` is loaded by `config.py` at bootstrap. The module
  emits typed snapshots and alerts only to `OperationalTelemetry`; that port accepts metric names,
  numeric values, durations, fixed low-cardinality enum labels and configuration version, never
  Workspace/object/Job/Attempt IDs, keys, checksums or raw annotation maps.
- `S3ObjectStore` is the S3-compatible adapter selected by typed `ObjectStoreSettings` loaded from
  runtime configuration at bootstrap. It is the only application-facing S3 seam. Its injected
  provider capability client permits only streaming put/get, head and delete; a capability-audit
  wrapper at that boundary rejects any other provider operation in contract tests without exposing
  SDK internals, keys or credentials.
- The PDF upload response is `202 Accepted` when a created or reused job is non-terminal and
  `200 OK` for a terminal idempotency replay or fingerprint deduplication. Every response includes
  `ingestion_job_id`, `submission_outcome` (`created`, `idempotency_replay` or `deduplicated`) and
  `status`.
- Public states are `queued`, `processing`, `retry_scheduled`, `succeeded`, `superseded` and
  `failed`. `attempt_count` counts attempts started, including the initial attempt; `max_attempts`
  is the total budget. `failed` exposes only safe `failure_reason` (`retry_exhausted`,
  `terminal_input`, `terminal_config` or `resource_limit`) plus a safe error code.
- Polling returns `200 OK` with status, attempt counts, `next_attempt_at` only when retry is
  scheduled, `poll_after_seconds` or `Retry-After`, and `Cache-Control: no-store`. It exposes
  `created_at`, `started_at`, `updated_at` and `terminal_at` as UTC RFC 3339 values. `created_at`
  is required and immutable from durable Job-generation creation. `started_at` is null before the
  first successful transition to processing, then records that first PostgreSQL time and remains
  immutable across retries and terminalization. `updated_at` is required and reflects the latest
  durable mutation to public lifecycle fields, excluding heartbeat-only lease updates and unrelated
  serving-pointer changes. `terminal_at` is null in non-terminal states and is set once and immutable
  after transition to `succeeded`, `superseded` or `failed`. PostgreSQL wall clock is authoritative.
  For `succeeded`, polling includes only `result: { document_version_id }`, where the value equals
  `target_document_version_id` after complete derivation and activation CAS commit. Non-terminal,
  failed and superseded states omit a successful `result`; failed retains safe failure reason/error
  and superseded may retain optional replacement Document Version/Job metadata. `result` must not
  expose Chunk Set, Embedding Set, lease, worker or other internal coordination IDs.
  `reprocess_of` is only on a newly created processing generation. Missing or cross-Workspace jobs
  return the same `404 INGESTION_JOB_NOT_FOUND` response.
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
  lease-expiry recovery. Operational Metrics V1 defines `queue_depth` as the non-negative integer
  count, at one fresh PostgreSQL `clock_timestamp()` observation, of Ingestion Jobs eligible for
  claim: `queued` Jobs plus `retry_scheduled` Jobs whose `next_attempt_at <= clock_timestamp()`.
  A future-scheduled retry is not in this metric's population. Polling clients should use jitter
  and must not rely on synchronized tight loops. Operational Metrics V1 defines
  `oldest_job_age` as the non-negative duration `clock_timestamp() - created_at` for the oldest
  Job in that same eligible-for-claim population; its value is zero when that population is empty.
  It defines `claim_latency` as a non-negative duration emitted for each successful claim, from
  the Job's durable eligibility timestamp to its durable claim timestamp: `created_at` for the
  first attempt and the persisted `next_attempt_at` for a retry attempt. PostgreSQL owns both
  timestamps.
  It defines `retry_rate` for a configured trailing window `W` as the dimensionless ratio in
  `[0,1]` of attempt closures with `retry_policy_result = schedule_retry` to all attempt closures
  whose durable PostgreSQL `closed_at` falls within `W`. When that denominator is zero, the metric
  emits no sample rather than zero.
  It defines `lease_expiry_recovery_total` as a monotonic counter that increments exactly once for
  each applied expired-attempt recovery that closes an Attempt with canonical cause
  `LEASE_EXPIRED`. Stale or not-expired observations and transport retry/read-back of the same
  applied recovery do not increment it. The event timestamp is the PostgreSQL-owned `closed_at`;
  both retry-scheduled and retry-exhausted applied recoveries are included.
  It defines `cleanup_attempt_total` as a monotonic counter that increments once when a durable
  cleanup-attempt record is created, and `cleanup_failure_total` as a monotonic counter that
  increments once when that attempt is durably classified failed. A retry creates and counts as a
  new attempt; replay or read-back of the same operation does not increment either counter. Their
  event timestamps are the durable database timestamps of attempt creation and failure
  classification.
  It defines `orphan_discovery_total` as a monotonic counter that increments once when
  authoritative reconciliation state first records an object identity as an orphan; later scans of
  that unresolved identity do not increment it. It defines `orphan_reconciliation_total` as a
  monotonic counter that increments once when a durable corrective disposition completes: repairing
  an inconsistent object record or deleting an eligible unreferenced object. Report-only,
  too-young, retained, cross-Workspace, and delete-suppressed dispositions do not increment the
  reconciliation counter.
  Each Operational Metrics V1 alert definition is versioned configuration that names its metric
  predicate, threshold, sustain window, and recovery condition. V1 sets no numeric default. Tests
  use the configured definition as their oracle: a value below threshold or shorter than its
  sustain window produces no alert; a sustained breach produces the defined alert; and a cleared
  condition follows the configured recovery behavior.
  Operational Metrics V1 permits only low-cardinality operational labels, including metric name,
  cleanup or reconciliation disposition, retry-policy version, and alert-definition version. It
  forbids `workspace_id`, Document/Job/Attempt IDs, opaque object keys, checksums, filenames, raw
  source data, credentials, and ETags in metric labels or alert annotations.

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
  `EXTRACTION_TIMEOUT` or `EXTRACTOR_MEMORY`. Infrastructure failure or extractor eviction is a
  policy input; loss of the worker is recorded through lease-expiry recovery rather than an
  unverifiable crash cause.
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

- The application exposes one retrieval seam through `AnsweringStore.retrieve_candidates`; callers
  and evaluation code must not select vector and full-text paths separately. Hybrid retrieval is
  implemented behind that seam by the PostgreSQL adapter.
- A versioned Retrieval Configuration is strategy-agnostic at the application interface and records
  the retrieval strategy and fusion policy/version that determine candidate ordering. The
  vector-only Milestone 1 configuration remains a reproducible baseline. Production Retrieval V2
  adds paired `retrieval-m3-vector-v2` and `retrieval-m3-rrf-v2` configurations.
- Score semantics are `similarity = 1 - cosine_distance`; the threshold applies to similarity.
  Question Trace records both raw cosine distance and derived similarity.
- The versioned Retrieval Configuration baseline is `candidate_k = 8`,
  `max_evidence_chunks = 5`, `max_evidence_tokens = 3000` and `min_similarity = 0.65`.
  The threshold is an initial value to calibrate with evaluation data, not a demonstrated quality
  claim.
- Workspace, Active Embedding Set and Embedding Configuration predicates must be applied inside
  every vector and full-text retrieval branch. Global retrieval followed by application filtering is
  forbidden.
- Initial PostgreSQL FTS policy `fts-v1` explicitly uses `simple` for document and query:
  `to_tsvector('simple', chunk_text)` and `plainto_tsquery('simple', query_text)`. Eligibility is
  `tsquery @@ tsvector`; branch rank is `ts_rank_cd(tsvector, tsquery, 0) DESC`, then `chunk_id ASC`.
  It must not depend on `default_text_search_config`, use `websearch_to_tsquery`, or apply
  language-specific stemming/stop-word configuration. `fts-v1` is immutable/versioned Retrieval
  Configuration policy; the PostgreSQL adapter must not provide an implicit FTS default.
- `fts-m3-or-v2` deterministically NFKC-normalizes the query, extracts Unicode letter/number
  lexemes, deduplicates them in first-occurrence order, and joins them with PostgreSQL OR semantics
  through bound parameters. An input with no lexemes returns no lexical candidates without issuing
  lexical SQL.
- Each retrieval branch has a deterministic total order before its rank is assigned and returns at
  most `candidate_k`; `candidate_k` is distinct from the final Evidence Set top-k/count limit.
- Hybrid candidates are deduplicated by canonical Chunk identity and fused using the immutable
  policy named by the Retrieval Configuration. `rrf-v1` contributes `1 / (60 + rank)` per branch
  and sums contributions for duplicate canonical Chunks. Final ordering is
  `fusion_score DESC → chunk_id ASC`, with all tie-breakers part of configuration semantics.
- `rrf-v2` keeps the same contribution formula and deterministic final ordering while allowing
  distinct branch budgets. Production Retrieval V2 pins both vector and FTS budgets to eight.
  Its calibrated vector threshold is `0.657410732025`; it was selected only after the immutable
  Issue #56 calibration gates passed and is not a post-fusion threshold.
- RRF fusion score is a ranking/fusion signal, not a calibrated relevance score. Evidence
  sufficiency/refusal uses a separate versioned policy with explicit semantics; no magic RRF cutoff
  is permitted. Any threshold must be independently defined and calibrated.
- The initial Evidence Sufficiency Policy applies vector `min_similarity` before that branch assigns
  rank or makes an RRF contribution. The full-text branch uses native eligibility/rank semantics and
  must not be converted to similarity. Only eligible branch contributions are fused: when a
  canonical Chunk is below vector `min_similarity` but is eligible in full-text search, it remains
  a full-text-only candidate with no vector contribution.
- Evidence Selection continues to enforce its versioned chunk count, token budget and overlap
  policy after fusion. An empty Evidence Set returns the deterministic Refusal without generation;
  a non-empty Evidence Set may still yield a valid structured Generation Provider refusal.
  Initial M3 has no independent numeric post-fusion threshold: `fusion_score` is ranking-only, and
  a future post-fusion threshold requires an immutable/versioned policy with explicit metric and
  semantics.
- The Question Trace retains ordered rank, source contribution and raw/derived scores needed to
  analyze vector, full-text and fusion behavior, but SQL details do not cross the application seam.
- Retrieval configuration ID, fusion-policy version, and embedding/chunk-set provenance are
  trace-level metadata and are not repeated for every candidate in one invocation. The trace stores
  the ordered fused candidate set before Evidence Selection. Each candidate stores canonical
  `chunk_id`, fused `final_rank`, `fusion_score`, a closed `final_decision`/`decision_reason`, and
  typed vector (`branch_rank`, `cosine_distance`, `similarity`) and full-text (`branch_rank`,
  `native_rank`) contributions. `final_rank` is fused retrieval rank, never Evidence Set order.
  Branch observations are recorded separately: vector is `ELIGIBLE`, `BELOW_THRESHOLD`, or no
  contribution; full-text is `ELIGIBLE`, `INELIGIBLE`, or no contribution. Pre-fusion losses are
  never represented as fused candidates. A fused candidate decision is only `SELECTED`,
  `REDUNDANT_OVERLAP`, `BUDGET_EXCEEDED`, or `ELIGIBLE_NOT_SELECTED`; `decision_reason`
  distinguishes `TOKEN_BUDGET` from `CHUNK_COUNT_LIMIT`. A full-text native rank is versioned
  provenance and never a general similarity or confidence score.
- A Question Trace is a persisted observation artifact only. Retrieval and answering must not
  depend on a trace to produce a production result. SQL query text, `tsvector`, `tsquery`, execution
  plans, and other database implementation details must not be persisted in the trace.
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
- A dataset version includes both case definitions and gold relevance/evidence judgments. It
  includes answerable lexical/exact-match, semantic/paraphrase and multi-source cases plus
  insufficient-evidence/refusal cases. Cross-Workspace isolation is a separate pass/fail security
  contract and is not a score-corpus category.
- Retrieval metrics are independent of Generation Provider: Recall@k, MRR, hit rate and retrieval
  latency. The evaluation runner calls the production Q&A endpoint and reads that request's exact
  trace by the exact `(workspace_id, trace_id)` pair taken directly from the Q&A response; an
  evaluation-only retrieval path and fallback by timestamp, question or latest trace are forbidden.
  A missing trace, Workspace mismatch, or incomplete provenance is an evaluation
  execution/observation failure, not a zero retrieval-quality score.
- Generation semantic metrics require a model-backed provider: citation entailment, faithfulness,
  answer relevance and refusal correctness.
- System metrics include latency, tokens, cost and provider errors; they are not semantic metrics.
- Citation correctness is split into deterministic validity checks (structural invariants must be
  100%) and semantic support/entailment scored from the final public answer and public citations by
  a human or versioned scorer; retrieval trace provenance alone is insufficient.
- Deterministic citation correctness evaluates the exact public answer, public citations, marker
  order, and Evidence Alias mapping from the correlated request. Semantic citation correctness
  receives only the public answer and public citation excerpts/source locators; hidden retrieved
  chunks in the trace must not be supplied to the scorer. The trace establishes correlation and
  evidence/configuration provenance only.
- `retrieval_latency_ms` and client-observed `end_to_end_latency_ms` are independent metrics with
  distinct clock boundaries: retrieval latency is server work obtaining candidates and selecting
  evidence, while end-to-end latency is the executor's client-side Q&A request/response interval.
  Neither is derived from the other. Future streaming requires a new explicit end-to-end metric
  contract and must not silently change this meaning.
- Milestone 1 hard gates are: structural pipeline checks at 100%, no cross-Workspace retrieval,
  no citation outside Evidence Set, persisted Question Trace, repeatable runner and complete
  provenance for dataset, corpus, chunking, embedding, retrieval, generation and scorer versions.
- Milestone 1 semantic metrics are baseline observations; no arbitrary quality threshold is set
  before the first run.
- A semantic metric may be claimed in portfolio material only after the dataset reaches at least
  50 cases and the report states dataset size and measurement method.
- Milestone 3 Dataset V1 contains 50 version-controlled, corpus-grounded cases in the
  `lexical_exact_match`, `semantic_paraphrase`, `multi_source`, and
  `insufficient_evidence_refusal` quality categories. Security isolation is a separate pass/fail
  authorization contract and must not be a dataset quality category.
- A Milestone 3 case must explicitly separate retrieval relevance applicability and acceptable
  relevant Chunks from answer expectations and evidence expectations. Every answerable case has
  non-empty required facts. Every insufficient-evidence/refusal case explicitly expects
  `INSUFFICIENT_EVIDENCE`, has non-applicable retrieval relevance, and must not be inferred as a
  zero-recall or zero-MRR case.
- Dataset and corpus/Chunk Set manifests checksum-bind released inputs. Validation rejects changed
  bytes, duplicate or unresolved Chunk references, incompatible Workspace/source references, empty
  answerable required facts, and citations outside expected source Documents before execution.
- Dataset V1 is a data-contract boundary. It does not implement retrieval metrics, evaluation
  execution, or report generation.
- Vector-only baseline and hybrid are paired runs: dataset, immutable corpus/Chunk Set provenance,
  embedding, generation and scorer settings must match; only Retrieval Configuration may differ.
  Semantic citation scorer provenance versions its model plus evaluator prompt/policy, and the
  report discloses provider stochasticity when the scorer is non-deterministic.
- Reports provide aggregate metrics and breakdowns for lexical/exact-match, semantic/paraphrase,
  multi-source and refusal categories. Recall@k and MRR apply only to cases with compatible gold
  relevance semantics; refusal correctness is reported separately.
- M3 distinguishes the production `ChunkSet.id` UUID, which identifies one persisted derivation
  instance, from immutable `chunk_set_provenance_id` such as `chunk-set-m3-v1`, which identifies a
  released corpus/Chunk Set derivation. A separate immutable M3 Evaluation Environment Binding
  records dataset and corpus manifest identities, `chunk_set_provenance_id`, Workspace ID,
  Retrieval Configuration ID, and exactly one per-source binding entry for every manifest source.
  Each entry records `source_key`, production Document Version UUID and production Chunk Set UUID.
  Before measured Q&A, bootstrap proves the entire retrieval-eligible active corpus source-key set
  equals the manifest source-key set: every manifest source has exactly one active
  manifest-matching Document Version and corresponding Chunk Set, and no extra active source or
  document exists. Missing, extra, duplicate or multiple-active source/version is setup/provenance
  failure. It proves the production derivation matches the manifest and must never infer a binding
  from a current/latest/name lookup.
- M3 Evaluation Chunk Identity is `(chunk_set_provenance_id, source_key, ordinal)`. A dataset gold
  `source_key#ordinal` reference becomes canonical only when scoped by the corpus manifest's
  `chunk_set_provenance_id`; it is not globally canonical. Before scoring, the evaluator verifies
  that the exactly correlated trace candidate's exact `(source_key, persisted Document Version UUID,
  persisted Chunk Set UUID)` triple equals one binding entry, then projects candidates to the
  provenance-scoped identity. The trace/evaluation reader must project Document Version UUID; if
  it cannot, it must establish an equivalent mandatory reader-side verified source → Document
  Version → Chunk Set relation. Version verification may not be omitted. Unknown source,
  UUID/version mismatch, duplicate/incomplete binding and provenance mismatch are observation
  failures; unordered UUID-set membership and fallback inference are prohibited. Database
  `chunk_id`, persisted Document Version UUID and persisted Chunk Set UUID are
  operational/environment provenance only and never participate in portable gold matching.
- M3 Retrieval Metrics V1 is `m3-retrieval-metrics-v1` and pins `k = 8`; both the metric-contract
  identity and `k` are immutable report provenance and remain fixed between comparable runs.
  Matching uses M3 Evaluation Chunk Identity against the ordered fused candidates of the exactly
  correlated trace. For each successful observation with
  `retrieval_relevance.applicable == true` and non-empty canonical gold set `G`, per-case
  `Recall@k` is `|G ∩ top_k| / |G|`; `k` limits Recall only. Per-case reciprocal rank is `1 / r`,
  where `r` is the rank of the first member of `G` in the entire ordered fused candidate sequence,
  or `0` for a valid no-hit retrieval. Aggregate Recall@k and MRR are arithmetic macro-means of
  their respective per-case values. Where fewer than `k` candidates exist, `top_k` is the
  available ordered candidate sequence while `|G|` remains the Recall denominator. Valid retrieval
  misses remain zero-valued members of the quality denominator; cases with non-applicable relevance
  and every execution/observation failure have no quality score and are excluded from all
  retrieval-quality denominators. Applicable cases require a non-empty gold-relevant set. MRR has
  no cutoff; a cutoff metric must use an explicit name and version, such as `MRR@8`.
- M3.2 projects independent per-successful-observation duration values and their provenance:
  `retrieval_latency_ms` comes from the correlated trace and `end_to_end_latency_ms` comes from
  the executor's Q&A interval. M3.2 defines no aggregate duration statistic or formula. Any
  aggregation requires a separately approved and versioned metric contract.
- `EvaluationEnvironmentBootstrap` is a control-plane application seam, not a public
  acceptance-only admin endpoint. It provisions/reuses an isolated Workspace, creates a scoped API
  credential under production credential invariants, loads/binds the manifest corpus and publishes
  the verified Evaluation Environment Binding. Raw credentials are runtime-only and redacted. It
  never performs measured Q&A or an evaluation-only retrieval path.
- M3 Evaluation Bootstrap Lifecycle runs before the production API process starts. An idempotent
  control-plane Workspace application seam provisions/reuses the isolated persisted Workspace;
  bootstrap then uses the normal application/ingestion path to materialize and bind the corpus. It
  generates a credential scoped to that persisted Workspace under the same API credential
  invariants used in production. The raw credential is ephemeral bootstrap/launcher state only and
  must never occur in an immutable binding, log, report, or committed evidence. The runtime launcher
  writes its normal startup auth configuration (`KNORA_API_CREDENTIALS_JSON` or typed equivalent)
  before `create_app()`. The subsequently started Q&A process uses only ordinary
  `ApiKeyAuthenticator`; it has no evaluation-only auth path and receives no credential mutation
  during a measured run. The evaluator consumes but never issues, activates, or revokes a
  credential. Environment/process teardown ends the ephemeral credential lifecycle; #51 defines no
  hot reload or revocation capability.
- A Sealed M3 Evaluation Environment is an evaluation control-plane/orchestration ownership
  boundary held exclusively by one run from before its authoritative closure snapshot until
  teardown. Bootstrap may materialize the corpus before seal, but authoritative corpus-closure and
  Binding V3/retrieval-configuration snapshot for measured Q&A occur only after successful seal
  acquisition. The contract forbids corpus/retrieval-provenance mutation while sealed, while Q&A
  and Question Trace persistence remain permitted. The guarantee may be provided by isolated
  evaluation topology, exclusive run ownership, restricted actors/credentials, or an existing
  centralized mutation guard; #51 does not require evaluation-specific seal checks retrofitted
  into every ingestion/reprocess/delete/activation production path. TC-01 proves the supported
  mutation paths and actors present in the evaluation topology cannot mutate the sealed
  environment. If exclusive ownership cannot be established, setup/preflight fails before Q&A.
  Post-run, while seal remains held, control plane re-verifies closure, V3 source bindings and
  resolved Retrieval Configuration against the sealed snapshot. Drift invalidates the whole run as
  an environment/observation failure and no quality score may publish. Seal and post-run checks
  occur outside each Q&A interval and must not contribute to `end_to_end_latency_ms`.
- `RetrievalConfigurationResolver` is the supported deployment/workspace composition seam used by
  production Q&A. It resolves immutable configuration without a per-request evaluation override;
  the resolved configuration ID is persisted in the trace. M3 #51 binds
  `retrieval-m3-rrf-v1`; M3 #52 executes vector baseline and hybrid in separate configured
  environments/runs through the same public Q&A HTTP contract.
- Before observing results, an improvement claim requires comparable provenance, zero observation
  failures, improvement in pre-declared primary retrieval metrics, no citation/refusal guardrail
  regression beyond pre-declared policy, and disclosure of every latency trade-off. Selecting
  favorable metrics after a run is forbidden.
- Failure taxonomy is versioned and stage-assigned. `LEXICAL_MISS` and `SEMANTIC_MISS` are
  branch-level misses. `FUSION_RANKING_ERROR` applies only where gold evidence is present in the
  eligible branch union but ranked incorrectly after fusion. `EVIDENCE_SELECTION_ERROR` applies
  only after fusion where relevant evidence is wrongly excluded by overlap, token budget, or chunk
  count selection. Other categories are `FALSE_REFUSAL`, `CITATION_STRUCTURAL_ERROR`,
  `CITATION_SEMANTIC_UNSUPPORTED`, `CORPUS_OR_CONFIGURATION_MISMATCH`,
  `EVALUATION_OBSERVATION_FAILURE`, `PROVIDER_ERROR`, and `INFRASTRUCTURE_ERROR`. A finding has one
  primary category plus optional contributing categories; provider, observation, and configuration
  failures must not be forced into retrieval-failure categories. `INSUFFICIENT_EVIDENCE_CORRECT` is
  a non-failure outcome used for refusal correctness, not a failure finding.
- Commit dataset/corpus manifests, normalized reports, failure annotations and selected-improvement
  records. Do not commit raw traces or secrets; they remain in authorized persistence. Every
  evaluation report carries immutable reproducibility metadata: dataset version, corpus/Chunk Set
  digest, Retrieval Configuration ID, generation/scorer versions, Git commit, and artifact schema
  version. A selected-improvement record retains metric deltas, guardrail results, latency
  trade-offs, and remaining regressions.

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
