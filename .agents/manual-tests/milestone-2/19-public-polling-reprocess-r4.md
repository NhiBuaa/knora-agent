# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft. Await explicit human approval. Do not lock, implement, or execute this guide.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #19 — Public polling, reprocess, and PDF citation integration
- Authority: Issue #19; `CONTEXT.md`; `docs/standards/architecture.md`; ADRs 0002 and 0005–0013
- Guide revision: `m2-issue-19-r4`
- Replaces: `m2-issue-19-r3`; r1, r2, and r3 remain unchanged and unapproved.

## Scope and evidence rules

- Use two authorized Workspaces, deterministic providers, controlled clock/lease/retry mechanisms,
  barrier-controlled PostgreSQL/application interleavings, and reset database/ObjectStore state.
- Capture safe IDs, public bodies/headers, configuration IDs, page/offset values, checksums,
  equality results, and approved spy counts only. Do not capture raw internal details.
- Use approved HTTP, application, Question Trace, PostgreSQL, and ObjectStore-spy seams. Do not use
  sleep, latency, timing luck, manual race clicking, ranking internals, or SQL assertions as oracles.

## Locked Test Cases

### TC-01: Prove upload contract and separate idempotency from deduplication

Every upload response below MUST include: an `ingestion_job_id` equal to the logical matched job;
the exact listed `submission_outcome`; and public `status` from exactly `queued`, `processing`,
`retry_scheduled`, `succeeded`, `superseded`, or `failed`. Status MUST describe the returned job.
No internal lifecycle state may substitute for public `status`.

| Request setup | Required result | Evidence |
| --- | --- | --- |
| New key and new authoritative fingerprint | One job; `created`; non-terminal `202 Accepted`. | Full safe body, job ID, count delta. |
| Same scoped key/request while non-terminal | Same job; `idempotency_replay`; `202 Accepted`. | Full safe bodies and equal job IDs. |
| Same scoped key/request after terminal | Same job; `idempotency_replay`; `200 OK`. | Full safe bodies and equal job IDs. |
| Different key, eligible equal fingerprint, matched job non-terminal | Matched job; `deduplicated`; `202 Accepted`. | Full safe body and equal job ID. |
| Different key, eligible equal fingerprint, matched job terminal | Matched job; `deduplicated`; `200 OK`. | Full safe body and equal job ID. |
| Same scoped key, different authoritative fingerprint | `IDEMPOTENCY_KEY_CONFLICT`; no extra job or Document Version. | Safe error and before/after counts. |
| Missing reprocess `Idempotency-Key` | Safe rejection; zero new generation. Do not require an unapproved status/error code. | Safe response and count. |
| Same scoped reprocess key and same request | Same generation; no extra generation. | Equal generation IDs and count. |
| Same scoped reprocess key with authoritative fingerprint difference | `IDEMPOTENCY_KEY_CONFLICT`; zero extra generation. | Safe error and count. |
| New reprocess key with equal work while matching generation processing | Reuse matching generation; no extra generation. | Equal generation IDs and count. |
| Another new reprocess key with equal work after matching generation succeeded | Reuse matching generation; no extra generation. | Equal generation IDs and count. |

**Concurrent request-idempotency probe.** Parameterize the same deterministic probe for PDF upload
and manual reprocess. For each operation, use an approved application/PostgreSQL seam to hold two
requests immediately before competing durable idempotency persistence, then release them together.
Use the same Workspace, operation, key, and authoritative fingerprint. Require one Idempotency
Record binding, one logical job/generation, two responses to it, no 500/unique-constraint leak, and
no duplicate durable work.

**False pass eliminated.** Public fields cannot be omitted, internal state cannot substitute, and a
same-key race cannot create duplicate work.

### TC-02: Poll safe lifecycle and serving state from one committed snapshot

| Probe | Required oracle | Evidence |
| --- | --- | --- |
| Public lifecycle | `200 OK`; exactly one six-state public status. `failed` exposes safe `failure_reason` and separate safe `error_code`. Successful terminal polling exposes authoritative terminal result. No raw internal detail leaks. | Safe succeeded/failed bodies. |
| Attempts, scheduling, cache | `queued=0`; `processing`/terminal=1..max; `retry_scheduled`=1..max-1. `next_attempt_at` only when retry scheduled. Poll has `poll_after_seconds` or `Retry-After` and `Cache-Control: no-store`. | State bodies and headers. |
| Serving-state meanings | No active Set=`unavailable`; served=current=`current`; older served A/newer current B=`previous`. | Three pointer/status projections. |
| Snapshot interleaving | S0/S1 are valid committed states. One controlled concurrent pointer change is an atomic test transition. Result equals all S0 or all S1; hybrid tuple FAILS. | Barrier trace and tuples. |
| Invalid credential | `401 UNAUTHENTICATED`; zero resource lookup. | Response and lookup-spy count. |
| Workspace-route mismatch | Workspace-B principal on Workspace-A route: `403 WORKSPACE_ACCESS_DENIED`; zero lookup. | Response and lookup-spy count. |
| Scoped cross-Workspace job | Workspace-B principal on Workspace-B route with A job ID: scoped lookup occurs; result equals unknown Workspace-B job: `404 INGESTION_JOB_NOT_FOUND`. | Lookup count and equal redacted 404 bodies. |

**Timestamp projection.** Do not mark timestamp projection PASS until its authority blocker is resolved.
Do not invent public field names, retry semantics, nullability, or durable-source mappings.

**False pass eliminated.** A handler cannot build hybrid pointers, look up before authorization,
leak terminal internals, or replace public `failed` with a taxonomy value.

### TC-03: Retrieve only active evidence during processing, failure, and activation

1. Activate PDF version A and capture active Embedding Set/chunk IDs.
2. Submit changed B under the same `source_key`, then hold B while processing.
3. Ask A's supported question during B processing and after B fails. Capture every Evidence
   Set/Chunk ID through Question Trace or deterministic provider observation.
4. Complete B successfully. Ask B's supported question and capture identities/status.

**Oracle.** Before B activates, every retrieved chunk belongs to A's active Set; zero B/inactive
chunk enters the Evidence Set. B projects target/current B, served A, and `previous`. After B
activates, retrieval uses B's active Set.

**False pass eliminated.** Citing A cannot hide inactive B evidence inside the Evidence Set.

### TC-04: Reprocess current version with authorization, immutable `current` config, and activation

1. Repeat TC-02's 401 → 403 → scoped lookup shapes on reprocess. Preserve safe no-leakage for a
   cross-Workspace Document Version; do not require job-specific 404.
2. Establish eligible fresh `config_mode=current` work with no equal processing/succeeded generation.
   Submit new-key manual reprocess, hold worker, mutate current config, then release worker.
3. Require enqueue-snapshotted IDs, `succeeded`, complete intended derivation active,
   served=current/`serving_state=current`, and retrieval from that active derivation.
4. Historical target returns `409 DOCUMENT_VERSION_NOT_CURRENT`.
5. Unavailable Original Source Object creates no generation. With approved ObjectStore spy, enqueue
   checks availability but does not read/parse; worker owns source read.

**`same_as_job` constraint.** Do not test exact prior config until selection authority is resolved.
A Document Version does not itself identify one canonical prior generation.

**False pass eliminated.** Reprocess cannot resolve mutable configuration late, report success before
activation, or create work from unavailable source.

### TC-05: Reuse equal reprocess work and supersede stale work

1. Execute TC-01 equal-work branches while matching work processes and after it succeeds.
2. Hold generation A before finalization. Advance to newer current/served state, then release A.

**Oracle.** Equal work reuses one generation without mutation. A ends `superseded`; its started
attempt stays counted; no retry is scheduled/consumed; it cannot replace current/served pointers;
old jobs remain immutable.

**False pass eliminated.** Duplicate post-success work, old-job mutation, or stale retry cannot look
like valid supersession.

### TC-06: Project PDF provenance using normalized extractor output and preserve legacy baseline

1. Use deterministic multi-page PDF fixture. Get normalized page text from approved pinned
   extractor/normalizer output, not from a newly required persisted page-text artifact.
2. Resolve cited Evidence Alias through approved safe seam. Compare exact Document Version, exact
   persisted Chunk identity, 1-based physical page, half-open offsets, and Chunk checksum.
3. Apply `[start:end]` to normalized page text. Require equality with persisted Chunk content/checksum
   and `page_start == page_end`.
4. Compare legacy citation to complete golden JSON in
   `backend/test/adapters/http/test_questions.py::test_question_http_contract_preserves_null_pdf_locators_for_legacy_citations`.

**False pass eliminated.** Correct page cannot hide wrong Chunk/offset/checksum/cross-page locator;
compatibility cannot hide a deleted legacy field.

### TC-07: Prove end-to-end tenant retrieval isolation and frozen refusal compatibility

1. In Workspace A, submit unique PDF, run worker, poll success, and ask its unique question.
2. In Workspace B, poll A's job, reprocess A's version, and ask A's unique question. Capture
   Question Trace or deterministic retrieval observation.
3. Compare B's refusal with
   `backend/test/adapters/http/test_questions.py::test_no_qualified_evidence_returns_deterministic_http_refusal`:
   `REFUSAL`, existing standard refusal answer, empty citations, `INSUFFICIENT_EVIDENCE`, and opaque
   trace-ID behavior.
4. Observe transport responses. At acceptance time, inspect Issue #19 change set for UI/frontend
   artifacts/behavior without assuming framework or directory layout.

**Oracle.** B has zero A Embedding Set IDs and zero A candidate/retrieved Chunk IDs. Every retrieved
identity, if any, belongs to B. B returns frozen refusal contract. No endpoint exposes SSE, token
events, percentage progress, or streaming. Change set adds no UI/frontend surface.

**False pass eliminated.** System cannot retrieve A evidence then refuse, stream a route, or add
untested UI while its final response seems safe.

## Acceptance-criteria traceability matrix

| Issue #19 criterion | Test case(s) | Coverage | Rejected false pass/fail |
| --- | --- | --- | --- |
| Upload response: status, job ID, outcome, public state | TC-01 | PASS | Missing/mismatched public field or internal-state substitute. |
| Six public states and safe terminal metadata | TC-02 | PASS | Taxonomy replaces state or terminal body leaks internals. |
| Poll fields, timestamps, hints, no-store | TC-02 | BLOCKED | No authoritative public timestamp projection semantics. |
| One-snapshot pointers and serving states | TC-02 | PASS | Hybrid S0/S1 tuple or missing serving meaning. |
| Auth-before-lookup and scoped job 404 | TC-02, TC-04 | PASS | Early lookup or cross-Workspace job leakage. |
| Reprocess auth, audit, key, historical conflict | TC-01, TC-04 | BLOCKED | Audit lacks observable acceptance contract. |
| `same_as_job` and `current` snapshots | TC-04 | BLOCKED | `same_as_job` lacks canonical prior-generation selection. |
| Fresh generation and equal-work reuse | TC-01, TC-05 | PASS | Same-key concurrency duplicates durable work. |
| PDF provenance and backward compatibility | TC-06 | PASS | Wrong locator or missing legacy field. |
| Active-only cited answers and refusal | TC-03, TC-07 | PASS | Inactive/cross-tenant evidence is retrieved before refusal. |
| E2E, serving, reprocess, supersession, tenant isolation | TC-03–TC-05, TC-07 | PASS | Lifecycle response appears right without retrieval proof. |
| No percentage progress, tokens, SSE, or UI | TC-07 | PASS | Endpoint streams or slice adds UI surface. |

## UPSTREAM AUTHORITY BLOCKERS

### Reprocess audit

Authority requires audit but not minimum observable audit correlation semantics, approved safe
observation seam, or required relationship/atomicity between audit persistence and accepted enqueue.

### Public lifecycle timestamp projection

Authority requires UTC RFC 3339 created/started/updated/terminal timestamps. The search found no
canonical public HTTP schema/field names, retry meaning for `started`, meaning of `updated`,
state/nullability semantics, or durable timestamp-to-public-value mapping.

### `same_as_job` prior-generation selection

Authority says `same_as_job` uses exact prior configuration and stores `reprocess_of_job_id`. The
search found no rule for choosing one prior generation when a Document Version has several. Human
authority must define canonical prior generation or explicit selector; this guide chooses none.

## Frontier evidence

Native GitHub dependency is blocker authority under `docs/agents/issue-tracker.md`:

```powershell
gh issue view 18 --repo NhiBuaa/knora-agent --json number,state,closedAt,url
# {"closedAt":"2026-08-10T01:08:25Z","number":18,"state":"CLOSED",...}

gh api 'repos/NhiBuaa/knora-agent/issues/19/dependencies/blocked_by' --jq '.[] | {number, state, html_url}'
# {"html_url":"https://github.com/NhiBuaa/knora-agent/issues/18","number":18,"state":"closed"}
```

## Approval gate

Do not lock this draft, implement code, execute acceptance, update Issue #19, or change authority
artifacts until explicit human approval of `m2-issue-19-r4`.
