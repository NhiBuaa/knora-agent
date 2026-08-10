# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft. Await explicit human approval. Do not lock, implement, or execute this guide.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #19 — Public polling, reprocess, and PDF citation integration
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/19
- Current authority: `CONTEXT.md`, `docs/standards/architecture.md`, and ADRs 0002, 0005–0013
- Guide revision: `m2-issue-19-r2`
- Replaces: `m2-issue-19-r1`; r1 remains unchanged and unapproved.
- Approved by: Pending
- Approved at: Pending

## Scope and evidence rules

- Use two authorized Workspaces, deterministic providers, controlled clock/lease/retry mechanisms,
  controlled PostgreSQL interleavings, and a reset database/ObjectStore between cases.
- Record only safe IDs, public statuses, response headers, timestamps, configuration IDs, page and
  offset values, checksums, and equality results. Do not record keys, PDF content, credentials,
  provider payloads, SQL text, or stack traces.
- Use approved HTTP, application, evaluation, PostgreSQL, ObjectStore-spy, and Question Trace seams.
  Do not use sleep, latency, timing luck, manual race clicking, ranking internals, or SQL assertions
  as an oracle.
- The matrix below measures guide coverage, not an executed acceptance verdict. `PASS` means the
  guide contains a complete deterministic oracle. `PARTIAL` means one part lacks an authority-grade
  oracle. `BLOCKED` means authority must decide before that criterion can pass.

## Locked Test Cases

### TC-01: Separate request idempotency from fingerprint/work deduplication

**Purpose.** Verify each submission branch has one deterministic observable outcome.

| Request setup | Required observable outcome | Evidence |
| --- | --- | --- |
| New upload key and new authoritative request fingerprint | One new job; `submission_outcome=created`; non-terminal `202 Accepted`. | Response, job ID, and job-count delta. |
| Same scoped upload key and same request while the job is non-terminal | Same job; `submission_outcome=idempotency_replay`; `202 Accepted`. | Both response bodies and equal job IDs. |
| Same scoped upload key and same request after the job is terminal | Same job; `submission_outcome=idempotency_replay`; `200 OK`. | Both response bodies, terminal status, and equal job IDs. |
| Different new upload key with an eligible equal fingerprint while the matched job is non-terminal | Matched job; `submission_outcome=deduplicated`; `202 Accepted`. | Response and equal job IDs. |
| Different new upload key with an eligible equal fingerprint after the matched job is terminal | Matched job; `submission_outcome=deduplicated`; `200 OK`. | Response and equal job IDs. |
| Same scoped upload key with a different authoritative request fingerprint | `IDEMPOTENCY_KEY_CONFLICT`; no extra job or Document Version. | Safe error and before/after job/version counts. |
| New reprocess key for equal current-version/configuration work while equal work is processing | Reuse the existing generation; no extra generation. | Both generation IDs and generation-count delta. |
| Another new reprocess key for equal current-version/configuration work after equal work succeeded | Reuse the existing generation; no extra generation. | Both generation IDs and generation-count delta. |

**False pass eliminated.** An implementation cannot label every replay or deduplication result as
“reused” or return `202` for terminal work and still pass.

### TC-02: Poll a complete safe lifecycle projection from one consistent snapshot

**Purpose.** Verify the public polling matrix, serving-state meanings, and auth-before-lookup.

| State/probe | Required oracle | Evidence |
| --- | --- | --- |
| Every lifecycle state | Poll returns `200 OK` and exactly one of `queued`, `processing`, `retry_scheduled`, `succeeded`, `superseded`, or `failed`. `failed` remains the public state; its `failure_reason` is from the authoritative safe taxonomy. | Six safe response bodies. |
| Attempt counters | `queued` has zero attempts. `processing` and terminal states have 1..max attempts. `retry_scheduled` has 1..max-1 attempts. | Response bodies and safe attempt projections. |
| Retry scheduling | `next_attempt_at` appears only for `retry_scheduled`; polling returns `poll_after_seconds` or `Retry-After`. | Retry-scheduled and non-retry responses/headers. |
| Timestamps and caching | Every returned lifecycle timestamp validates as UTC RFC 3339. Every poll response sends `Cache-Control: no-store`. | Header capture and timestamp validation output. |
| Serving-state meanings | With no active Embedding Set, result is `unavailable`. With served=current, result is `current`. With older served A and newer current B, result is `previous`. | Three safe pointer/status projections. |
| Snapshot interleaving | A barrier-controlled PostgreSQL transition changes current/active pointers while one status projection runs. The projection equals all of pre-transition S0 or all of post-transition S1. A hybrid tuple is FAIL. | Barrier trace and S0/S1/projection tuples. |
| Poll authentication and authorization | Authentication failure causes zero resource lookups. Authenticated but unauthorized Workspace access causes zero resource lookups. Only an authenticated, authorized request reaches the lookup spy. Unknown and cross-Workspace job requests return the same `404 INGESTION_JOB_NOT_FOUND` body. | Lookup-spy counts and redacted responses. |

**False pass eliminated.** A handler cannot assemble target/current/served values from different
commits, or look up a job before authorization and mask the result with a 404.

### TC-03: Retrieve only active evidence during processing, failure, and activation

**Purpose.** Prove that inactive PDF evidence never enters an Evidence Set.

1. Activate PDF version A with a known active Embedding Set and capture its chunk IDs.
2. Submit changed version B under the same `source_key`. Hold B while it processes.
3. Ask the A-supported question during B processing. Capture the Question Trace or deterministic
   provider observation of every retrieved Evidence Set/Chunk ID.
4. Make B fail safely. Ask the same question and capture the retrieved identities again.
5. Complete a succeeding B generation. Ask the B-supported question and capture the retrieved
   identities and serving projection.

**Required oracle.** During B processing and after B failure, every retrieved chunk belongs to A's
active Embedding Set and no B/inactive chunk enters the Evidence Set. B's status projection shows
target/current B and served A with `serving_state=previous`. After successful activation, retrieval
uses B's active Embedding Set and polling shows successful/current serving state.

**Evidence.** Safe Evidence Set/Chunk IDs, active-set IDs, question responses, and status snapshots.

**False pass eliminated.** A response that happens to cite A while its Evidence Set included an
inactive B chunk fails this case.

### TC-04: Reprocess only the current version with immutable configuration and safe preconditions

**Purpose.** Verify reprocess authorization, source availability, config snapshots, and worker ownership.

1. Use a lookup spy for reprocess. Send invalid credentials, then an authenticated credential for
   the wrong Workspace, then an authorized request. Require zero lookup for the first two requests
   and lookup only for the authorized request. Do not require a job-specific 404 code for a
   cross-Workspace Document Version request.
2. Reprocess the current version with `config_mode=same_as_job` and a new scoped `Idempotency-Key`.
   Require the stored configuration IDs to equal the selected prior job IDs.
3. Reprocess the current version with `config_mode=current`, hold the worker, then change mutable
   active configuration. Require the worker to use the IDs snapshotted at enqueue.
4. Target a historical version. Require `409 DOCUMENT_VERSION_NOT_CURRENT`.
5. Make the Original Source Object unavailable. Require no new generation. If the approved
   ObjectStore spy is available, require the enqueue handler to perform the availability check and
   not synchronously read or parse the object; only the worker reads the source.

**Required oracle.** Each accepted reprocess is a fresh immutable generation linked by
`reprocess_of_job_id`, starts with a reset attempt budget, and never mutates the prior job. Do not
assert an unapproved public error code for unavailable source.

**Evidence.** Lookup-spy counts, safe generation/configuration projections, worker input IDs,
historical-version response, and ObjectStore-spy operation names/counts.

**False pass eliminated.** A worker that resolves changed mutable configuration after enqueue, or
an endpoint that reads/parses a source during enqueue, fails this case.

### TC-05: Reuse equal reprocess work and safely supersede stale work

**Purpose.** Verify generation deduplication and stale current-pointer protection.

1. Run the two equal-work reprocess branches from TC-01: one while equal work is processing and one
   after equal work succeeded.
2. Hold reprocess generation A before finalization. Advance the Document to a newer current version
   with the correct served state. Release A.

**Required oracle.** Equal work reuses one generation without mutation. A ends terminal
`superseded`; its already-started attempt remains counted; it schedules and consumes no additional
retry; it cannot replace current or served pointers; and old jobs remain immutable.

**Evidence.** Generation IDs, before/after counts, attempt history, ordered pointer projections,
and safe terminal job projections.

**False pass eliminated.** An implementation cannot create a second post-success generation, reset
the old job, or retry stale A before returning `superseded`.

### TC-06: Project exact page-bounded PDF provenance and retain legacy citation compatibility

**Purpose.** Verify the public PDF citation locator against persisted evidence.

1. Use a deterministic multi-page PDF fixture with known page text and a citation-supported fact.
2. Ask the supported question after activation. Resolve the cited Evidence Alias to its persisted
   Chunk identity through an approved safe seam.
3. Compare the response with persisted provenance: exact `document_version_id`, exact Chunk ID,
   1-based page locator, half-open normalized-page-text offsets, and Chunk content checksum.
4. Verify that the persisted substring at `[start:end]` equals the Chunk text/checksum result and
   that `page_start=page_end` for this Milestone 2 evidence.
5. Run the existing legacy non-PDF fixture. Require its citation response to preserve every existing
   citation-contract field and the established PDF-locator representation from the current contract.

**Evidence.** Safe IDs, page/offset values, checksum/equality result, and redacted PDF/legacy
citation responses. Do not record PDF text.

**False pass eliminated.** A citation with a correct page number but wrong Chunk, offsets, checksum,
or cross-page locator fails this case.

### TC-07: Run the public end-to-end workflow without a progress or streaming contract

**Purpose.** Verify the approved integration seam and Workspace isolation.

1. In Workspace A, submit the unique PDF, run the worker, poll until success, and ask its unique
   question.
2. In Workspace B, poll A's job, reprocess A's version, and ask A's unique question.
3. Observe the transport responses for upload, polling, reprocess, and question requests.

**Required oracle.** A observes `upload → worker → poll → cited answer` from active PDF evidence.
Workspace B cannot access or reprocess A's resources and receives the existing safe authorization/
no-leakage behavior. B's question receives the existing refusal contract. Each affected endpoint
returns a normal completed HTTP response. No endpoint exposes SSE, token events, percentage
progress, or a streaming response contract.

**Evidence.** Safe A lifecycle/citation responses, redacted B responses, refusal response, and
transport headers/body observations.

**False pass eliminated.** Route registration alone cannot pass while an endpoint still emits a
progress stream or exposes A's resource existence to B.

## Acceptance-criteria traceability and evidence matrix

| Issue #19 criterion | Test case(s) | Coverage | Reason |
| --- | --- | --- | --- |
| Upload status, job ID, outcome, and public state | TC-01 | PASS | Each idempotency and fingerprint branch has an exact result. |
| Six public states; safe failure reason/error | TC-02 | PASS | State and failure taxonomy are separate in the polling matrix. |
| Poll counters, scheduling, timestamps, hints, and no-store | TC-02 | PASS | State-oriented projection matrix covers each authority-defined behavior. |
| One-snapshot pointers and three serving states | TC-02 | PASS | Barrier probe rejects hybrid projections and exercises every serving state. |
| Auth/authorization before lookup; indistinguishable job 404 | TC-02 | PASS | Lookup spy proves ordering; HTTP responses prove non-leakage. |
| Reprocess authorization, audit, key, and historical conflict | TC-04 | PARTIAL | Authorization/key/current-version conflict are covered. Audit is blocked below. |
| `same_as_job` and `current` configuration snapshots | TC-04 | PASS | Stored and worker-observed IDs are compared after mutable configuration changes. |
| Fresh immutable reprocess generations and equal-work reuse | TC-01, TC-04, TC-05 | PASS | Processing and succeeded equal-work branches are separate. |
| PDF page/offset/version/Chunk citation provenance | TC-06 | PASS | Exact persisted identity, locator, offset, checksum, and page-boundary oracles apply. |
| Active-only cited answers and existing refusal | TC-03, TC-07 | PASS | Evidence Set identity is captured before/during/after activation; B gets refusal. |
| End-to-end workflow, previous serving, success, supersession, tenant isolation | TC-03, TC-05, TC-07 | PASS | Each lifecycle branch has a deterministic integration oracle. |
| No percentage progress, tokens, SSE, or UI | TC-07 | PASS | Transport observations check completed HTTP behavior directly. |

## UPSTREAM AUTHORITY BLOCKER: Reprocess audit acceptance oracle

Issue #19, ADR 0010, and the Architecture Standard require reprocess to record audit. The current
authority does not define a minimum observable audit record, required fields, read seam, or required
transactionality. The authority search found only the requirement for an audit record/trail.

This guide therefore does not invent an audit schema or PASS oracle. Human authority must define the
minimum observable audit contract: the authorized actor/action/target correlation required for
acceptance, the approved safe read seam, and whether successful enqueue and audit must be atomic.

## Approval gate

This draft is immutable only after explicit human approval of `m2-issue-19-r2`. Until then, do not
lock the guide, implement code, execute acceptance, update Issue #19, or change authority artifacts.
