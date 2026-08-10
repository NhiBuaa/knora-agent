# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft. Await explicit human approval. Do not lock, implement, or execute this guide.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #19 — Public polling, reprocess, and PDF citation integration
- Authority: Issue #19; `CONTEXT.md`; `docs/standards/architecture.md`; ADRs 0002 and 0005–0013
- Guide revision: `m2-issue-19-r3`
- Replaces: `m2-issue-19-r2`; r1 and r2 remain unchanged and unapproved.
- Approved by: Pending
- Approved at: Pending

## Scope and evidence rules

- Use two authorized Workspaces, deterministic providers, controlled clock/lease/retry mechanisms,
  barrier-controlled PostgreSQL interleavings, and reset database/ObjectStore state between cases.
- Capture only safe IDs, public bodies and headers, timestamps, configuration IDs, page/offset
  values, checksums, equality results, and approved spy counts. Never capture raw PDF/object/
  provider/SQL/credential/exception detail.
- Use approved HTTP, application, Question Trace, PostgreSQL, and ObjectStore-spy seams. Do not use
  sleep, latency, timing luck, manual race clicking, ranking internals, or SQL assertions as oracles.
- `PASS` in the matrix means this guide has a deterministic oracle. It is not an execution verdict.

## Locked Test Cases

### TC-01: Separate request idempotency, fingerprint deduplication, and atomic concurrent binding

| Request setup | Required observable outcome | Evidence |
| --- | --- | --- |
| New upload key and new authoritative request fingerprint | One new job; `submission_outcome=created`; non-terminal `202 Accepted`. | Response, job ID, job-count delta. |
| Same scoped upload key and same request while non-terminal | Same job; `submission_outcome=idempotency_replay`; `202 Accepted`. | Equal job IDs and response bodies. |
| Same scoped upload key and same request after terminal | Same job; `submission_outcome=idempotency_replay`; `200 OK`. | Equal job IDs, terminal status, responses. |
| Different new upload key with eligible equal fingerprint while non-terminal | Matched job; `submission_outcome=deduplicated`; `202 Accepted`. | Equal job IDs and response. |
| Different new upload key with eligible equal fingerprint after terminal | Matched job; `submission_outcome=deduplicated`; `200 OK`. | Equal job IDs and response. |
| Same scoped upload key with different authoritative request fingerprint | `IDEMPOTENCY_KEY_CONFLICT`; no extra job or Document Version. | Safe error and before/after counts. |
| Same scoped reprocess key and same authoritative request | Replay the same generation; no extra generation. | Equal generation IDs and count. |
| Same scoped reprocess key with fingerprint difference using only authoritative config identity | `IDEMPOTENCY_KEY_CONFLICT`; no extra generation. | Safe error and before/after count. |
| Missing reprocess `Idempotency-Key` | Safe rejection; zero new generation. Do not require an unapproved status/error code. | Safe response and count. |
| New reprocess key with equal current-version/configuration work while equal work is processing | Reuse the existing generation; no extra generation. | Equal generation IDs and count. |
| Another new reprocess key with equal work after equal work succeeded | Reuse the existing generation; no extra generation. | Equal generation IDs and count. |

**Concurrent binding probe.** Start two barrier-held requests with the same Workspace, operation,
`Idempotency-Key`, and authoritative request fingerprint. Release both at the atomic binding point.
Require exactly one durable idempotency binding and one logical job/generation. Both responses must
resolve to that same job/generation. Neither response may expose an unhandled uniqueness error or
500. No duplicate Document Version, job, or generation may result from check-then-insert.

**False pass eliminated.** An endpoint cannot omit reprocess keys, create a second generation on a
same-key replay, or race into duplicate durable work while returning a superficially valid response.

### TC-02: Poll a complete safe lifecycle projection from one consistent snapshot

| State/probe | Required oracle | Evidence |
| --- | --- | --- |
| Every lifecycle state | Poll returns `200 OK` and exactly one of `queued`, `processing`, `retry_scheduled`, `succeeded`, `superseded`, or `failed`. `failed` remains the public state; `failure_reason` uses the safe authoritative taxonomy. | Six safe bodies. |
| Attempt counters | `queued` has zero attempts. `processing` and terminal states have 1..max attempts. `retry_scheduled` has 1..max-1 attempts. | Bodies and safe attempt projections. |
| Scheduling and cache control | `next_attempt_at` appears only for `retry_scheduled`. Every poll has `poll_after_seconds` or `Retry-After` and `Cache-Control: no-store`. | Retry and non-retry bodies/headers. |
| Mandatory lifecycle fields | The authority-named `created`, `started`, `updated`, and `terminal` timestamp fields are projected. Every non-null timestamp validates as UTC RFC 3339. | State-oriented response captures and validator output. |
| Terminal metadata | Successful terminal polling exposes the authoritative terminal result. Failed terminal polling exposes `failure_reason` plus a separate safe `error_code`; its body/code contains no raw exception, provider, SQL, storage, or object detail. | Succeeded and failed bodies plus redaction assertion. |
| Serving-state meanings | No active Embedding Set gives `unavailable`. Served=current gives `current`. Older served A with newer current B gives `previous`. | Three pointer/status projections. |
| Snapshot interleaving | S0 and S1 are valid committed states. One barrier-controlled atomic pointer transition occurs while status projects. The result equals all of S0 or all of S1. A tuple hybrid is FAIL. | Barrier trace and S0/S1/result tuples. |
| Authentication failure | Invalid credential returns `401 UNAUTHENTICATED` and causes zero resource lookup. | Response and lookup-spy count. |
| Route Workspace mismatch | Valid Workspace-B principal sent to a Workspace-A route returns `403 WORKSPACE_ACCESS_DENIED` and causes zero resource lookup. | Response and lookup-spy count. |
| Scoped cross-Workspace lookup | Valid Workspace-B principal uses its Workspace-B route with A's job ID. Workspace authorization succeeds, scoped lookup occurs, and result equals an unknown Workspace-B job: `404 INGESTION_JOB_NOT_FOUND`. | Lookup-spy count and equal redacted 404 bodies. |

**False pass eliminated.** A handler cannot omit mandatory timestamps or terminal metadata, assemble
a hybrid snapshot, lookup before authorization, or hide unsafe terminal details behind `failed`.

### TC-03: Retrieve only active evidence during processing, failure, and activation

1. Activate PDF version A with known active Embedding Set/chunk IDs.
2. Submit changed version B under the same `source_key` and hold B while processing.
3. Ask A's supported question during B processing. Capture every Evidence Set/Chunk ID through a
   Question Trace or deterministic provider observation.
4. Make B fail safely. Repeat the question and capture identities.
5. Complete a successful B generation. Ask B's supported question and capture identities/status.

**Required oracle.** During B processing and after B failure, every retrieved chunk belongs to A's
active Embedding Set; no B/inactive chunk enters the Evidence Set. B projects target/current B,
served A, and `serving_state=previous`. After B activates, retrieval uses B's active Embedding Set.

**False pass eliminated.** Citing A cannot hide that an inactive B chunk entered the Evidence Set.

### TC-04: Reprocess the current version with key enforcement and immutable configuration

1. Exercise reprocess authorization with a lookup spy: invalid credential, Workspace-B principal on
   Workspace-A route, then an authorized request. Require zero lookup for the first two and lookup
   only after authorization. For a cross-Workspace Document Version, require safe no-leakage
   behavior but do not require the job-specific 404 code.
2. Establish a prior job/configuration for `same_as_job` with no equal processing/succeeded target.
   Submit a new-key reprocess and require one fresh immutable generation linked by
   `reprocess_of_job_id`, reset attempt budget, and unchanged prior job.
3. Establish an eligible fresh `current` configuration target with no equal processing/succeeded
   generation. Submit reprocess, hold the worker, mutate mutable active configuration, then release
   the worker.
4. Require the released worker to use enqueue-snapshotted IDs, reach `succeeded`, activate the
   complete intended derivation, project served=current/`serving_state=current`, and retrieve from
   that active derivation.
5. Target a historical version and require `409 DOCUMENT_VERSION_NOT_CURRENT`.
6. Make the Original Source Object unavailable. Require zero new generation. When the approved
   ObjectStore spy is available, require availability check only at enqueue, with no synchronous
   read/parse; the worker owns the read.

**False pass eliminated.** A test cannot accidentally reuse equal work while claiming a fresh
generation, nor pass when reprocess lacks key enforcement, resolves changed configuration late, or
does not complete its activation.

### TC-05: Reuse equal reprocess work and supersede stale work

1. Run the two equal-work branches from TC-01: one while equal work is processing and one after it
   succeeded.
2. Hold reprocess generation A before finalization. Advance the Document to a newer current version
   with the correct served state. Release A.

**Required oracle.** Equal work reuses one generation without mutation. A ends `superseded`; its
already-started attempt remains counted; it schedules/consumes no added retry; it cannot replace
current or served pointers; and old jobs remain immutable.

**False pass eliminated.** A post-success duplicate generation, old-job mutation, or stale retry
cannot appear as a valid supersession result.

### TC-06: Project exact page-bounded PDF provenance and preserve the legacy citation baseline

1. Use a deterministic multi-page PDF fixture with a citation-supported fact. Resolve the cited
   Evidence Alias to the persisted Chunk through an approved safe seam.
2. Compare exact `document_version_id`, exact Chunk ID, 1-based page locator, half-open normalized
   page-text offsets, and content checksum with persisted evidence.
3. Verify that persisted `[start:end]` equals the Chunk text/checksum result and that this
   Milestone 2 evidence has `page_start=page_end`.
4. Run the legacy fixture from `backend/test/adapters/http/test_questions.py`,
   `test_question_http_contract_preserves_null_pdf_locators_for_legacy_citations`. Compare the
   complete citation JSON to its existing golden baseline, including all legacy fields and its four
   `null` PDF locator fields.

**False pass eliminated.** Correct page numbers cannot hide a wrong Chunk/offset/checksum/cross-page
locator, and deleting an existing legacy field cannot pass as “compatible.”

### TC-07: Run the public end-to-end workflow with no streaming or UI change surface

1. In Workspace A, submit the unique PDF, run the worker, poll to success, and ask its unique
   question.
2. In Workspace B, poll A's job, reprocess A's version, and ask A's unique question.
3. Observe the completed transport responses for upload, polling, reprocess, and questions.
4. Inspect the Issue #19 implementation change set at acceptance time for introduced UI/frontend
   artifacts or behavior. Do not assume a framework or directory layout.

**Required oracle.** A observes `upload → worker → poll → cited answer` from active PDF evidence.
B cannot access/reprocess A and receives the existing safe no-leakage/refusal behavior. Each affected
endpoint returns a normal completed HTTP response, with no SSE, token events, percentage-progress,
or streaming contract. The Issue #19 change set introduces no UI/frontend surface.

**False pass eliminated.** A route-only check cannot pass while a changed endpoint streams progress
or the slice adds a UI artifact outside the tested backend route surface.

## Acceptance-criteria traceability and evidence matrix

| Issue #19 criterion | Test case(s) | Coverage | Rejected false pass |
| --- | --- | --- | --- |
| Upload status, job ID, outcome, and public state | TC-01 | PASS | All replay/dedup paths collapse to one outcome. |
| Six public states; safe failure reason/error | TC-02 | PASS | `failed` omits separate safe metadata or leaks raw detail. |
| Poll counters, scheduling, timestamps, hints, and no-store | TC-02 | PASS | Mandatory fields are omitted or timing hints leak to another state. |
| One-snapshot pointers and three serving states | TC-02 | PASS | Pointer tuple combines committed S0/S1 values. |
| Auth/authorization before lookup; equal job 404 | TC-02 | PASS | Lookup happens before auth/route authorization. |
| Reprocess authorization, audit, key, and historical conflict | TC-01, TC-04 | BLOCKED | Audit has no authoritative observation contract. All non-audit portions are covered. |
| `same_as_job` and `current` configuration snapshots | TC-04 | PASS | Worker reads later mutable configuration. |
| Fresh generation and equal-work reuse | TC-01, TC-04, TC-05 | PASS | Check-then-insert or reuse logic creates duplicate/mutated work. |
| PDF citation provenance and backward compatibility | TC-06 | PASS | Locator is not exact/persisted or legacy field disappears. |
| Active-only cited answers and existing refusal | TC-03, TC-04, TC-07 | PASS | Inactive evidence enters Evidence Set or active reprocess never serves. |
| End-to-end, previous serving, reprocess, supersession, tenant isolation | TC-03–TC-05, TC-07 | PASS | A lifecycle branch succeeds only by response appearance. |
| No percentage progress, tokens, SSE, or UI | TC-07 | PASS | Changed endpoint streams or introduces a UI surface. |

## UPSTREAM AUTHORITY BLOCKER: Reprocess audit acceptance oracle

Issue #19, ADR 0010, and the Architecture Standard require an audit record. They do not define a
minimum observable audit record/correlation semantics, an approved safe observation seam, or any
required enqueue/audit atomicity. This guide does not invent an audit schema or oracle.

Human authority must define those three minimum acceptance inputs before the audit-containing
criterion can become PASS.

## Frontier evidence

The repository issue-tracker guide defines native GitHub issue dependencies as blocker authority.
At guide preparation time, these exact read-only commands reported #18 closed:

```powershell
gh issue view 18 --repo NhiBuaa/knora-agent --json number,state,closedAt,url
# {"closedAt":"2026-08-10T01:08:25Z","number":18,"state":"CLOSED",...}

gh api 'repos/NhiBuaa/knora-agent/issues/19/dependencies/blocked_by' --jq '.[] | {number, state, html_url}'
# {"html_url":"https://github.com/NhiBuaa/knora-agent/issues/18","number":18,"state":"closed"}
```

## Approval gate

Do not lock this draft, implement code, execute acceptance, update Issue #19, or change authority
artifacts until explicit human approval of `m2-issue-19-r3`.
