# Manual Test Guide: PDF derivation, embedding, and CAS activation

## Metadata

- Status: Draft — revision `m2-issue-18-r3` awaits explicit human approval. Do not implement or
  execute this guide.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub issue #18 — PDF derivation, embedding, and CAS activation
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/18
- Design: `docs/design/issue-18-pdf-derivation-activation.md`
- Guide revision: `m2-issue-18-r3`
- Supersedes: draft `m2-issue-18-r2` at
  `.agents/manual-tests/milestone-2/18-pdf-derivation-activation-r2.md`; r1 and r2 remain
  unchanged.
- Approved by: Pending
- Approved at: Pending

## Authority and fixed test conventions

The authority for PDF source identity is the current domain model, ADR 0013 and completed Issue
#15: a PDF Document Version is identified by `(document_id, raw_sha256)`. Parser, normalizer,
chunking and embedding IDs identify an immutable derivation target. This guide never uses the
older normalized-content identity wording for a PDF source version.

The controlled environment supplies deterministic fakes/spies for ObjectStore, extractor,
Embedding Provider, worker runner/scheduler, PostgreSQL clock and finalization transaction/lock
probe. An injection has one named action and cannot be selected by an operator at execution time.
Evidence contains only safe IDs, checksums, counts, lifecycle values and allowlisted error codes;
it contains no opaque object key, raw PDF bytes, provider payload, SQL text or credential.

The completed Document Version owns its Original Source Object. `run_once` must not immediately
delete that object on success, supersession or failure. Physical cleanup of staging, temporary or
partial objects is asynchronous and cannot reverse a terminal ingestion result; this guide does
not invent a synchronous cleanup action that no approved Issue #18 contract defines.

## Prerequisites

- Environment: local PostgreSQL/pgvector with the Issue #17 coordination schema, deterministic
  ObjectStore, isolated PDF extractor, deterministic Embedding Provider and an assembled PDF
  worker. Database-focused cases use a real PostgreSQL instance, not an ORM fake.
- Data: an authorized Workspace; two valid text PDFs with distinct raw SHA-256 values under one
  `source_key`; a pre-existing completed historical active Embedding Set; exact immutable profile
  A and a distinct immutable profile B; and resettable Document/Job/attempt state per case.
- Instrumentation: provider/extractor/ObjectStore call counters; bounded-reader trace; injected
  monotonic heartbeat schedule; PostgreSQL fresh-time/row-lock trace; transition-operation-ID
  replay trace; and a transaction probe that observes final persistence transaction begin/end and
  activation-row lock acquisition.
- Access: an authorized API credential for HTTP/status/question observations. A separate authorized
  Workspace is available for cross-Workspace constraint attempts.

## Acceptance traceability matrix

| Issue #18 acceptance criterion | Test case / execution step | Distinguishing expected result | Required evidence |
| --- | --- | --- | --- |
| Worker orchestrates claimed work through storage, extraction, embedding, persistence, activation and terminal/retry outcome | TC-01 steps 1–3; TC-03A steps 1–3 | One `run_once` yields only an authoritative success/retry result after all owned stages | Ordered worker stage trace, job/attempt projection, derivation IDs |
| Worker uses job-snapshotted configuration IDs, never mutable current selection | TC-01B steps 1–3; TC-02B steps 1–2 | Profile A is used after current selection moves to B; invalid A never falls back to B | Handler profile trace, persisted configuration IDs, provider call count |
| Original-object checksum and ObjectStore metadata are verified; reads stream | TC-07A steps 1–3; TC-07B steps 1–3 | Mismatch stops before extractor/provider; reader rejects unbounded application read | Metadata comparison, zero call counts, bounded-reader trace |
| Parser/chunker creates or reuses the correct PDF Chunk Set | TC-01A steps 1–3; TC-05A steps 1–3 | Exact full derivation identity creates/reuses one immutable complete Chunk Set | Chunk Set identity, chunk ordinal/checksum/page-offset projection |
| Embedding calls occur outside DB transactions and validate count/dimension/provider/model/configuration | TC-01A step 2; TC-01C steps 1–3; TC-03B steps 1–3 | No attempt-owned application DB transaction remains open during provider work; only exact vector identity persists | All-connection transaction-depth trace, finalization lock trace, provider trace, vector validation projection |
| Retry taxonomy covers approved transient categories; deterministic failures are terminal | TC-03A–TC-03E and TC-03G–TC-03L; TC-03F is the upstream blocker | Every executable fixed injection maps to its named failure kind/cause and policy disposition | Handler fact, canonical cause, attempt history, policy metadata, call counts |
| Final persistence atomically creates/reuses a complete chain with no partial retrieval-visible derivation | TC-01A; TC-05C steps 1–3 | Commit has complete chain plus terminal outcome, while definite rollback has neither | Transaction outcome, all derivation row counts, active pointer, attempt/job fields |
| Activation CAS requires live fencing, current target and same Document/Workspace complete set | TC-01A; TC-04; TC-06B; TC-08A–TC-08C | Valid claim activates; stale claim is fenced; stale target is superseded; invalid pointers are rejected | Token/result, pointer state, transaction result and DB constraint error class |
| Newer source makes old target superseded without another retry and records replacement when available | TC-04 steps 1–4 | Older job reaches `superseded`, not failed/retried, while newer version stays current/served | A/B job snapshots, attempt count, replacement fields, current/active/served projection |
| Current and active source versions may differ while prior knowledge remains served | TC-02A steps 1–4 | Failed/in-progress new current version is not retrieval-visible; historical active version remains cited | Current, active and served IDs plus historical question response |
| Constraints prevent cross-Document/Workspace/incomplete pointers and protected deletion | TC-08A–TC-08E | Database rejects every direct invalid mutation atomically | Direct mutation outcome, constraint/FK evidence, unchanged rows/pointers |
| Integration coverage includes local activation, retry, terminal failure, lease loss, stale CAS, duplicate delivery and rollback | TC-01 through TC-06 | Each named lifecycle path has one deterministic full or focused integration seam | Per-case evidence listed below and Evaluation record links after execution |
| Isolated extractor child failure is a handler fact; worker process disappearance is durable lease expiry | TC-03E; TC-06C | Extractor unavailability maps through the handler; vanished worker is recorded only as `LEASE_EXPIRED` during recovery | Extractor error/cause trace; expiry observation/recovery and later-claim trace |

## Locked Test Cases

### TC-01: Commit one complete PDF derivation and activation as one authoritative outcome

#### TC-01A: Happy-path chain identity, atomic success and citation provenance

- Injection: deterministic ObjectStore returns exact claimed metadata; deterministic extractor
  returns the fixed multi-page fixture projection; deterministic provider returns exactly one
  1536-dimensional vector per ordered Chunk, with the profile-A provider/model.
- Steps:
  1. Submit the fixture under profile A and record the durable job's target Document Version and
     parser/normalizer/chunking/embedding IDs.
  2. Execute one worker `run_once`; poll the authorized job status after it returns.
  3. Query a fact unique to the fixture through the existing question seam.
- Expected results:
  - The Chunk Set is created or reused only for the target Document Version and the exact pinned
    parser, normalizer and chunking IDs. Its ordered Chunks have matching checksum, page locator
    and half-open normalized-text offsets.
  - The Embedding Set is complete and matches the exact embedding configuration, provider, model,
    vector count and 1536 dimensions. No other configuration is mixed into either set.
  - `succeeded`, closed successful attempt, complete derivation/result IDs/counts and active pointer
    are visible from the same committed outcome. Current attempt/lease fields are cleared.
  - Retrieval cites the active PDF Chunk with 1-based physical page locator and start-inclusive,
    end-exclusive normalized-text offsets.
- Evidence to capture:
  - Job/status/result snapshot; attempt closure; complete chain IDs/counts/config IDs; vector
    validation projection; Document current/active/served IDs; and redacted citation locator.

#### TC-01B: Use immutable profile A after mutable current selection moves to B

- Injection: enqueue the fixture with profile A; before claim, change only the mutable
  worker/bootstrap “current” selection to distinct profile B. Immutable profile-A records remain
  unchanged and readable.
- Steps:
  1. Record the job's A IDs and switch the controlled current selection to B.
  2. Run one worker iteration for the A job.
  3. Inspect extractor/provider invocation configuration and persisted result/chain IDs.
- Expected results:
  - Extractor and provider receive A, never B. The persisted Chunk Set, Embedding Set and terminal
    result all identify A.
  - The worker does not resolve a mutable current configuration during processing.
- Evidence to capture:
  - Durable job snapshot before processing, extractor/provider received-profile traces and complete
    persisted configuration-ID projection.

#### TC-01C: Prove extraction, chunking and provider work occur with no attempt-owned DB transaction

- Injection: an all-connection transaction probe increments/decrements depth for every application
  database connection acquired by this attempt, including handler/configuration lookups and
  finalization; extractor, chunker and provider spies mark begin/end. The provider blocks until
  the probe reports `open_db_transaction_count == 0`, then returns the fixed valid batch.
- Steps:
  1. Run the profile-A fixture through one worker iteration.
  2. At every observed instant from extraction begin through extraction/chunking end and from
     provider begin through provider end, assert `open_db_transaction_count == 0`.
  3. Inspect the ordered probe trace after success.
- Expected results:
  - Extraction, chunking and provider work have zero attempt-owned open database transactions.
    The probe fails a handler/configuration lookup transaction held through either activity.
  - Finalization transaction begin and activation-row locking occur only after valid provider output
    exists.
  - Finalization runs only after the valid provider output exists and produces TC-01A's atomic
    outcome.
- Evidence to capture:
  - All-connection transaction-depth events, extraction/chunking/provider boundaries, finalization
    begin/end and lock events, plus final lifecycle/derivation projection.

### TC-02: Preserve served historical knowledge during and after deterministic target failure

#### TC-02A: New current source may fail while historical active knowledge remains served

- Injection: Document has a historical active version H. Submit valid newer raw-PDF version N,
  which atomically becomes `current_document_version_id`; controlled extractor returns the exact
  terminal `PDF_TEXT_INSUFFICIENT` input result before embedding.
- Steps:
  1. Record H as active/served, then submit N and observe N current while its job is queued or
     processing.
  2. Ask the historical supported question while N is processing.
  3. Run the N job to terminal failure and ask the same question again.
  4. Inspect all inactive target derivation rows and retrieval candidates.
- Expected results:
  - N remains `current_document_version_id`; H remains active and served both during processing and
    after N fails.
  - Both questions retrieve/cite H. No inactive or partial N Chunk/Embedding Set is retrieval
    visible.
  - N is terminal `failed` with one counted closed attempt, no retry, `failure_reason=terminal_input`
    and `PDF_TEXT_INSUFFICIENT`.
- Evidence to capture:
  - Before/during/after current-active-served projection; both cited answers; N job/attempt result;
    retrieval candidate projection and N derivation row counts.

#### TC-02B: An invalid immutable work/configuration fixture never falls back to profile B

- Injection: focused concrete-handler seam only; public submission is not used. Construct one
  frozen `IngestionWork` whose pinned parser ID is
  `pdf-parser-pypdf-6-14-2-plain-layout-v1`, normalizer ID is `pdf-normalizer-m2-v1`, and chunking
  ID is `chunking-m2-pdf-pypdf-6-14-2-v1`; pair it with a frozen selected profile whose
  `PdfExtractionConfiguration.normalizer_version` is `pdf-normalizer-m2-v2`. The IDs and profile
  are therefore internally inconsistent before the handler begins and no historical immutable
  configuration record is mutated. Mutable current selection is valid profile B.
- Steps:
  1. Assemble the fixed inconsistent work/profile fixture and set current selection to B.
  2. Execute the concrete handler once and inspect received profile, ObjectStore, extractor and
     provider traces.
- Expected results:
  - The canonical cause is `CONFIGURATION_INVALID`; policy is terminal, with
    `failure_reason=terminal_config`; extraction/provider call counts are zero; no profile-B work
    or derivation is created.
  - The fixed invalid fact is the normalizer-ID/version disagreement. The handler rejects it before
    ObjectStore read and never falls back to mutable profile B. Its public code need only be the
    approved allowlisted configuration-invalid code; a distinct code name is not required here.
- Evidence to capture:
  - Work/profile identity comparison, handler failure fact/cause/policy, profile traces, zero
    ObjectStore/extractor/provider calls and zero derivation/pointer delta.

### TC-03: Classify deterministic worker failures and retry only approved transient facts

Every subcase starts from attempt 1 of one profile-A job. For `ScheduleRetry`, expected policy is
V1 `[0, 5 seconds]` full jitter recorded once; a separately controlled run advances to the exact
persisted `next_attempt_at` and proves claim of attempt 2. For `FailTerminal`, expected attempt
count remains one and there is no provider/extractor call after the named failure point.

| Subcase | Fixed injection | Expected handler kind -> canonical cause | Expected disposition / safe public result | Required call count and persistence delta |
| --- | --- | --- | --- | --- |
| TC-03A | Provider raises fixed timeout classification after extractor succeeds | `PROVIDER_TRANSIENT` -> `PROVIDER_TRANSIENT` | `ScheduleRetry`; the approved allowlisted provider-transient code (shared code permitted) | extractor 1, provider 1; no derivation/activation; closed retry attempt with V1 audit |
| TC-03B | Provider returns fixed HTTP 429 classification after extractor succeeds | `PROVIDER_TRANSIENT` -> `PROVIDER_TRANSIENT` | `ScheduleRetry`; the approved allowlisted provider-transient code (shared code permitted) | extractor 1, provider 1; same retry-only delta |
| TC-03C | Provider returns fixed HTTP 503 classification after extractor succeeds | `PROVIDER_TRANSIENT` -> `PROVIDER_TRANSIENT` | `ScheduleRetry`; the approved allowlisted provider-transient code (shared code permitted) | extractor 1, provider 1; same retry-only delta |
| TC-03D | `ObjectStore.open_read` raises the approved transient-storage sentinel before extractor starts | `STORAGE_TRANSIENT` -> `STORAGE_TRANSIENT` | `ScheduleRetry`; approved allowlisted storage-transient code | extractor 0, provider 0; same retry-only delta |
| TC-03E | Isolated extractor returns `PDF_EXTRACTOR_UNAVAILABLE` with reason `CHILD_CRASH` and `retryable=True` | `WORKER_UNEXPECTED` -> `WORKER_UNEXPECTED` | `ScheduleRetry`; `PDF_EXTRACTOR_UNAVAILABLE` | extractor 1, provider 0; same retry-only delta |
| TC-03F | **Blocked upstream:** no approved handler-owned database dependency/sentinel exists | Required `DATABASE_TRANSIENT` mapping is undefined | Cannot execute or lock until Issue #18 is authoritatively resolved | No invented injection, call count or persistence delta |
| TC-03G | Extractor returns fixed `PDF_TEXT_INSUFFICIENT` with reason `INSUFFICIENT_EXTRACTABLE_TEXT` | `INVALID_INPUT` -> `INVALID_INPUT` | `FailTerminal`, `failure_reason=terminal_input`, `PDF_TEXT_INSUFFICIENT` | extractor 1, provider 0; no derivation/activation |
| TC-03H | Extractor returns fixed `PDF_ENCRYPTED` with reason `ENCRYPTED` | `UNSUPPORTED_INPUT` -> `UNSUPPORTED_INPUT` | `FailTerminal`, `failure_reason=terminal_input`, `PDF_ENCRYPTED` | extractor 1, provider 0; no derivation/activation |
| TC-03I | The fixed internally inconsistent work/profile fixture from TC-02B | `CONFIGURATION_INVALID` -> `CONFIGURATION_INVALID` | `FailTerminal`, `failure_reason=terminal_config`, approved allowlisted configuration-invalid code | extractor 0, provider 0; no derivation/activation |
| TC-03J | Provider returns exactly `chunk_count - 1` vectors | `VECTOR_MISMATCH` -> `VECTOR_MISMATCH` | `FailTerminal`, `failure_reason=terminal_config`, approved allowlisted vector-mismatch code | extractor 1, provider 1; no derivation/activation |
| TC-03K | Provider returns exactly `chunk_count` vectors of 1535 dimensions | `VECTOR_MISMATCH` -> `VECTOR_MISMATCH` | `FailTerminal`, `failure_reason=terminal_config`, `EMBEDDING_DIMENSION_MISMATCH` | extractor 1, provider 1; no derivation/activation |
| TC-03L | Provider returns exactly `chunk_count` 1536-dimensional vectors with fixed provider/model identity different from profile A | `VECTOR_MISMATCH` -> `VECTOR_MISMATCH` | `FailTerminal`, `failure_reason=terminal_config`, approved allowlisted vector-identity code | extractor 1, provider 1; no derivation/activation |

TC-03F is deliberately not satisfied by a coordination-store commit, connection or ambiguous-commit
failure: Issue #17 says those failures are infrastructure/indeterminate outcomes, not
`DATABASE_TRANSIENT` business work. Issue #18 still explicitly requires transient database
deadlock/serialization/connectivity coverage. It is the one upstream authoritative contract blocker
until either the approved Issue #18 design adds a legitimate handler-owned database seam with a
fixed sentinel, or Issue #18 itself is approvedly clarified. Shared allowlisted public codes are
valid for transient categories unless an approved contract names a variant-specific code.

Evidence for every subcase is the injected sentinel, handler kind, canonical cause, policy result,
safe code, full attempt-history retry/terminal fields, call counts, and zero derivation/active
pointer delta. A definitive coordination persistence failure is not entered in this matrix.

### TC-04: Supersede an older target with CAS while newer knowledge stays served

- Injection: job A for raw PDF A is claimed and its handler is held after valid provider output;
  job B for distinct raw PDF B under the same `source_key` is completed first and makes B current
  and active.
- Steps:
  1. Record A's claim/token and B's Document Version/current pointer after B submission.
  2. Complete B, then release A to its success finalization.
  3. Poll both jobs and ask a B-only question.
- Expected results:
  - A atomically transitions `processing -> superseded`, closes its already-counted attempt and
    clears lease/current-attempt fields. It schedules no retry and consumes no additional attempt.
  - B remains current, active and served; A cannot replace it. Replacement IDs are recorded when
    available without leaking another Workspace.
- Evidence to capture:
  - Ordered A/B status/attempt projections, Document current-active-served IDs, A replacement
    fields, retry fields and the B citation.

### TC-05: Distinguish duplicate delivery, ambiguous finalization and definite rollback

#### TC-05A: At-least-once duplicate worker delivery yields exactly one visible outcome

- Injection: delivery one has already committed a terminal success for the isolated job. Trigger an
  independent second worker delivery after that authoritative commit; it uses a fresh worker
  invocation and does not replay the first `ClaimOperationId`.
- Steps:
  1. Start delivery one through valid claim and complete its concrete success finalization.
  2. Invoke a fresh `run_once` for delivery two against the isolated single-job environment.
  3. Inspect delivery-two result, chain, activation and attempt history.
- Expected results:
  - Exactly one complete visible derivation/activation and one terminal attempt disposition exist.
  - Delivery two returns `NoEligibleJob`; it cannot claim/process the terminal job and performs no
    handler/provider work or second activation.
- Evidence to capture:
  - Independent worker-invocation IDs, delivery-two `NoEligibleJob`, provider count unchanged after
    delivery one, one-chain row projection, one attempt closure and active pointer.

#### TC-05B: Ambiguous success-finalization transport result reconciles one logical mutation

- Injection: concrete `finalize_success` commits, then its controlled transport raises the exact
  “response lost after possible commit” sentinel. The handler/provider has already produced its
  one `PdfDerivationSuccess` value.
- Steps:
  1. Retain the original `TransitionOperationId` and immutable finalization request fingerprint.
  2. Invoke finalization; receive the transport sentinel after possible commit.
  3. Reinvoke/read back with exactly the same ID and fingerprint; do not rerun handler/provider.
- Expected results:
  - Read-back returns the one authoritative persisted disposition and its IDs/timestamps; no
    policy reroll, re-anchoring, business work or provider call occurs.
  - Incompatible reuse of the ID/fingerprint is an invariant error, never a second outcome.
- Evidence to capture:
  - Original/reused operation ID and fingerprint digest, provider count exactly one, authoritative
    replay result, attempt transition record and chain/pointer state.

#### TC-05C: Definite pre-commit rollback leaves no lifecycle or derivation mutation

- Injection: finalization transaction raises a fixed definite database failure after tentative
  Chunk Set/Chunk/Embedding Set/Chunk Embedding writes and before commit; no commit is possible.
- Steps:
  1. Run the handler once to its valid success value.
  2. Invoke finalization with the fixed pre-commit rollback injection.
  3. Inspect committed database state without replaying or classifying the error as handler work.
- Expected results:
  - There is no Chunk Set, Chunk, Embedding Set, Chunk Embedding, active-pointer update, attempt
    closure, transition-operation record or terminal job success from this invocation.
  - The coordination-store failure propagates as a definite infrastructure error. It is not
    `DATABASE_TRANSIENT`, does not produce `RetryScheduled`, and does not cause the coordinator to
    rerun business/provider work. Recovery/retry handling requires a separately approved
    infrastructure policy; this case ends at the definite error.
- Evidence to capture:
  - Transaction rollback marker, committed row counts before/after, unchanged job/attempt/pointer
    fields, provider count one and propagated error classification.

### TC-06: Lose a lease deterministically and discard a late handler completion

#### TC-06A: Heartbeat fencing causes `LeaseLost`; late completion never finalizes

- Injection: after a valid claim starts a held handler, the deterministic store's next heartbeat
  returns `Fenced` for that exact current `FencingToken`. This is a fencing setup, not elapsed time
  while successful heartbeats renew the lease.
- Steps:
  1. Advance the monotonic scheduler to the first heartbeat; return `Fenced`.
  2. Let `AttemptSupervisor` cancel and detach the handler; assert `run_once` returns `LeaseLost`.
  3. Complete the physical handler afterwards with a valid `PdfDerivationSuccess` and drain its
     runner completion.
- Expected results:
  - The supervisor returns `LeaseLost` after heartbeat fencing, and the late result is discarded.
    The coordinator does not call success finalization, retry scheduling or activation from it.
  - No new transition operation ID, attempt closure, success/retry state or active-pointer mutation
    originates from the late completion.
- Evidence to capture:
  - Heartbeat token/result, cancellation/detach trace, `LeaseLost`, finalization call count zero,
    late-completion telemetry marker and unchanged durable projection.

#### TC-06B: Concrete stale success finalization is fenced with zero mutation

- Injection: focused PostgreSQL call to concrete `finalize_success` with a stale
  `ClaimedAttempt/FencingToken` after ownership is no longer current/unexpired.
- Steps:
  1. Persist the ownership change/recovery independently of the stale claimant.
  2. Invoke concrete success finalization with the stale claim and an otherwise valid fixed success
     value.
- Expected results:
  - It returns `Fenced` before transition legality; it creates/reuses no derivation, changes no
    pointer, closes no attempt and writes no terminal outcome.
- Evidence to capture:
  - Stale/current token generations, typed `Fenced` result, zero row/pointer/attempt delta.

#### TC-06C: Expiry recovery does not create a successor attempt

- Injection: the worker process disappears after claim without publishing a completion; controlled
  PostgreSQL time advances past the exact lease expiry and recovery receives its fixed policy
  decision. This records the durable fact `LEASE_EXPIRED`, not an invented `WORKER_CRASH` handler
  result.
- Steps:
  1. Observe and conditionally recover the expired attempt.
  2. Inspect state immediately after recovery, including the zero-delay policy variant.
  3. Run a separate later due claim.
- Expected results:
  - Recovery closes only the expired attempt and commits `retry_scheduled` or exhausted `failed`.
    It creates no successor attempt, even at zero delay.
  - Only the later due claim may create the next attempt/lease generation.
- Evidence to capture:
  - Observation, recovery result, immediate attempt count/open row count, then later claim trace.

### TC-07: Verify source-object integrity before streaming extraction and prove bounded worker read

#### TC-07A: Raw SHA-256 mismatch stops processing before extractor/provider work

- Injection: durable job expects fixed raw SHA-256 A while controlled `ObjectStore.head` returns
  the same Workspace/key/media/size but raw SHA-256 B.
- Steps:
  1. Claim the job and run its handler once.
  2. Inspect handler result and all call/persistence counters.
- Expected results:
  - The mismatch is detected before `open_read`, extractor or provider; extractor/provider call
    counts are zero.
  - It takes the design's canonical terminal input behavior (`INVALID_INPUT` -> `FailTerminal`,
    `failure_reason=terminal_input`), leaves no partial derivation and preserves the active pointer.
  - Its public safe code is the approved allowlisted input-metadata code; the guide does not require
    a distinct preselected code name beyond the contract's allowlist. No raw metadata is exposed.
- Evidence to capture:
  - Safe expected/observed checksum digests, head/open/extractor/provider counts, failure
    kind/cause/policy/attempt result and zero derivation/pointer delta.

#### TC-07B: Worker consumes the source incrementally without whole-object materialization

- Injection: `ObjectStore.open_read` returns a bounded-consumption spy that rejects its
  whole-object read operation and records incremental consumption, cumulative bytes and peak
  application-resident buffer. The isolated extractor test adapter may receive a bounded wrapper,
  pipe, file descriptor or bounded spool-to-disk; it returns the fixed projection after consuming
  the complete source through that approved bounded transport.
- Steps:
  1. Run the valid fixture handler to extraction completion.
  2. Inspect source-consumption, whole-object-read and application-memory traces before
     provider/finalization.
- Expected results:
  - No worker/application whole-object read API is called, and the application does not materialize
    the full raw PDF in memory. Source consumption is incremental and bounded under the approved
    ingestion limits (25 MiB raw object and 256 MiB isolated-extractor memory ceiling).
  - The case accepts any streaming-valid bounded wrapper/pipe/file-descriptor/spool transport; it
    does not prescribe a Python object identity or chunk size. The valid path makes exactly one
    provider call and continues normally.
- Evidence to capture:
  - Whole-object-read count zero, incremental-consumption trace, peak application-resident buffer,
    bounded transport classification, extractor/provider counts and lifecycle result.

### TC-08: PostgreSQL, not application validation alone, protects activation and retention

Each subcase executes one direct focused PostgreSQL mutation in a transaction, attempts commit and
then reads the unchanged valid state. The test records the named FK/check/constraint-trigger
violation class rather than accepting an application pre-validation error.

| Subcase | Fixed invalid mutation | Expected database enforcement | Evidence |
| --- | --- | --- | --- |
| TC-08A | Point Document D1 active embedding pointer to a completed Embedding Set belonging to D2 in the same Workspace | Commit rejected; D1 pointer unchanged | SQL constraint/FK/trigger error class and before/after pointers |
| TC-08B | Point Document in Workspace W1 to a completed Embedding Set owned through a Document in W2 | Commit rejected; no cross-Workspace pointer | Error class, Workspace/document/set IDs and unchanged rows |
| TC-08C | Point a Document at its own `status != complete` Embedding Set | Commit rejected; active pointer remains complete prior set/null | Error class, status/pointer projection |
| TC-08D | Hard-delete a current Document Version | Delete rejected by database; current pointer/version remains | FK/constraint error and before/after version/pointer |
| TC-08E | Hard-delete an Active Embedding Set | Delete rejected by database; active set remains | FK/constraint error and before/after set/pointer |

### TC-09: Terminal worker outcome preserves the Original Source Object and separates cleanup

- Injection: deterministic ObjectStore delete spy; execute one valid terminal success and one
  terminal deterministic failure from TC-02A in fresh state.
- Steps:
  1. Record the Document Version-owned Original Source Object before each worker iteration.
  2. Complete the terminal worker outcome.
  3. Inspect ObjectStore delete calls and resulting source-object reference.
- Expected results:
  - `run_once` does not delete the referenced Original Source Object for either terminal outcome.
    Terminal success/failure is not changed by absent asynchronous cleanup work.
  - If an approved cleanup-intent/outbox mechanism is introduced in this slice, observe its safe
    intent record separately. Its absence is not a failure of this guide: zero immediate deletion
    is the complete Issue #18 assertion until an authority assigns that mechanism.
- Evidence to capture:
  - Original Source Object reference before/after, delete-spy count zero, terminal status/attempt
    result and any separately approved cleanup-intent projection.

## Approval blockers remaining

| Authoritative blocker | Evidence of conflict | Required authority-level resolution | Affected guide scope |
| --- | --- | --- | --- |
| Issue #18 requires transient database deadlock/serialization/connectivity retry coverage, but Issue #17 forbids classifying coordination-store database/network errors as `DATABASE_TRANSIENT`, and no handler-owned database dependency or deterministic sentinel is approved. | Current Issue #18 acceptance criterion; Issue #17 approved cause-mapping and indeterminate-persistence contract. | Either add an approved handler-owned database seam with a fixed deadlock/serialization/connectivity sentinel to the Issue #18 design, or approve an Issue #18 clarification that changes the criterion. A design note cannot silently narrow it. | TC-03F and the corresponding retry-taxonomy acceptance-matrix row. |

Constraint/trigger names, SQLSTATE values, public-code granularity beyond named PDF codes, and a
cleanup intent/outbox schema are implementation choices, not approval blockers. TC-08 and TC-09
retain their required observable behavior without preselecting those mechanisms.

This guide becomes immutable only after explicit human approval. Any resolution of an ambiguity,
semantic test change, or authoritative-specification change requires a new revision; do not rewrite
`m2-issue-18-r3` after approval. Store future execution observations separately as JSONL
Evaluation records.
