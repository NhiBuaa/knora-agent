# Manual Test Guide: Public polling, reprocess, and PDF citation integration

## Metadata

- Status: Draft. Await explicit human approval. Do not lock, implement, or execute this guide.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #19 — Public polling, reprocess, and PDF citation integration
- Authority: Issue #19; `CONTEXT.md`; Architecture Standard; ADRs 0002 and 0005–0013
- Guide revision: `m2-issue-19-r5`
- Replaces: `m2-issue-19-r4`; r1–r4 remain unchanged and unapproved.

## Scope and evidence rules

- Use two Workspaces, deterministic providers, controlled clock/lease/retry, barrier-controlled
  application/PostgreSQL seams, and reset database/ObjectStore state between cases.
- Capture safe IDs, bodies/headers, configuration IDs, page/offset values, checksums, equality
  results, and approved spy counts only. Do not capture raw internal details.
- Do not use sleep, latency, timing luck, manual race clicking, ranking internals, or SQL assertions.

## Locked Test Cases

### TC-01: Prove upload/reprocess idempotency and the complete upload response contract

Every upload response below MUST contain `ingestion_job_id` equal to the logical matched job, the
exact listed `submission_outcome`, and public `status` from exactly `queued`, `processing`,
`retry_scheduled`, `succeeded`, `superseded`, or `failed`. Status MUST describe that job. No internal
lifecycle state may substitute for public `status`.

| Request setup | Required result |
| --- | --- |
| New upload key and new authoritative fingerprint | One job; `created`; non-terminal `202 Accepted`. |
| Same scoped upload key/request while non-terminal | Same job; `idempotency_replay`; `202 Accepted`. |
| Same scoped upload key/request after terminal | Same job; `idempotency_replay`; `200 OK`. |
| Different key, eligible equal fingerprint, matched job non-terminal | Matched job; `deduplicated`; `202 Accepted`. |
| Different key, eligible equal fingerprint, matched job terminal | Matched job; `deduplicated`; `200 OK`. |
| Same scoped upload key, different authoritative fingerprint | `IDEMPOTENCY_KEY_CONFLICT`; no extra job/Document Version. |
| Same raw bytes/canonical source/configs but different client filename | Equal authoritative fingerprint; replay/dedup behavior, not conflict/new work. |
| Missing reprocess `Idempotency-Key` | Safe rejection; zero new generation. Do not require unapproved error/status. |
| Same scoped reprocess key/request | Same generation; no extra generation. |
| Same scoped reprocess key, authoritative fingerprint difference | `IDEMPOTENCY_KEY_CONFLICT`; zero extra generation. |
| New reprocess key, equal work while matching generation processing | Reuse matching generation; no extra generation. |
| New reprocess key, equal work after matching generation succeeded | Reuse matching generation; no extra generation. |

**Scope probes.** Use the same literal key in Workspace A and B for independent uploads. Require
independent bindings/jobs and no replay, conflict, or cross-Workspace reuse. In one Workspace, use
the same literal key once for upload and once for manual reprocess. Require independent
operation-scoped bindings and no cross-operation replay/conflict.

**Concurrent probes.** Parameterize a deterministic approved application/PostgreSQL concurrency seam
for both PDF upload and manual reprocess. Hold same Workspace + operation + key + fingerprint
requests immediately before competing durable idempotency persistence, then release them together.
Require one Idempotency Record, one job/generation, two responses to it, no 500/uniqueness leakage,
and no duplicate work. Repeat with two distinct authoritative fingerprints F1/F2: exactly one winner
binding/job/generation; the other returns `IDEMPOTENCY_KEY_CONFLICT`; no loser-side durable work.

**False pass eliminated.** Missing/mismatched public fields, filename-sensitive identity,
cross-scope replay, and check-then-insert duplicates cannot pass.

### TC-02: Poll all six public states from one committed snapshot

Construct and capture one safe poll projection for every state without sleep:

| Fixture | Required state oracle |
| --- | --- |
| Accepted job held before claim | `queued`, `attempt_count=0`, no `next_attempt_at`. |
| Claimed handler held | `processing`, attempt count 1..max, no `next_attempt_at`. |
| Controlled classified transient failure via deterministic failure/clock seam | `retry_scheduled`, attempt count 1..max-1, and `next_attempt_at`. |
| Successful completion | `succeeded`, attempt count 1..max, no `next_attempt_at`, terminal result, no failure reason. |
| Deterministic terminal failure or retry exhaustion | `failed`, attempt count 1..max, no `next_attempt_at`, exact failure taxonomy below and separate safe `error_code`. |
| TC-05 stale-CAS result | `superseded`, attempt count 1..max, no `next_attempt_at`, no failure reason. |

For `failed`, require `failure_reason` exactly one of `retry_exhausted`, `terminal_input`,
`terminal_config`, or `resource_limit`. Do not invent an error-code allowlist. Failed bodies and
error codes must exclude raw exception/provider/SQL/storage/object details. Every poll has `200 OK`,
`poll_after_seconds` or `Retry-After`, and `Cache-Control: no-store`.

Serving/snapshot/auth probes remain mandatory: `unavailable`, `current`, and `previous`; valid
committed S0/S1 with one atomic controlled pointer transition and no hybrid response; invalid key
gets `401 UNAUTHENTICATED` with zero lookup; Workspace-B principal on Workspace-A route gets
`403 WORKSPACE_ACCESS_DENIED` with zero lookup; Workspace-B route plus A job ID performs scoped
lookup and returns the same `404 INGESTION_JOB_NOT_FOUND` body as unknown B job.

**Timestamp projection.** UTC RFC3339 format is authoritative. Do not mark timestamp projection
PASS until the schema/semantic blocker below is resolved; do not invent public timestamp fields.

**False pass eliminated.** Vocabulary-only state coverage, missing retry scheduling proof, invalid
failure taxonomy, hybrid state, pre-auth lookup, or terminal leakage cannot pass.

### TC-03: Retrieve only active evidence and activate B through a fresh generation

1. Activate A and capture active Embedding Set/chunk IDs. Submit changed B and hold generation J1.
2. During J1 processing, and after J1 terminally fails, ask A's supported question. Capture all
   Evidence Set/Chunk IDs. J1 remains immutable; do not transition it from `failed`.
3. Create fresh eligible generation J2 for still-current B through `config_mode=current` and a new
   scoped Idempotency-Key. Do not use `same_as_job`. Complete J2 successfully.
4. Require activation and retrieval to move to B's active Set.

**Oracle.** Before J2 activation, every retrieved chunk belongs to A's active Set; zero B/inactive
chunk enters Evidence Set. B projects target/current B, served A, `previous`. After J2 activates,
retrieval uses B.

**False pass eliminated.** A failed terminal job cannot be silently reopened, and citing A cannot
hide inactive B evidence in the Evidence Set.

### TC-04: Reprocess current version with authorization, immutable `current` config, and activation

Exercise TC-02's 401 → 403 → scoped lookup shapes for reprocess; preserve safe no-leakage for a
cross-Workspace Document Version without requiring job-specific 404. Establish eligible fresh
`config_mode=current` work with no equal processing/succeeded generation. Hold its worker, mutate
current config, release it, and require enqueue-snapshotted IDs, success, active complete derivation,
served=current/`serving_state=current`, and retrieval from that Set. Historical target returns
`409 DOCUMENT_VERSION_NOT_CURRENT`. Unavailable source creates no generation; approved ObjectStore
spy proves enqueue checks availability without read/parse, while worker reads source.

Do not test exact `same_as_job` configuration until prior-generation selection is defined.

**False pass eliminated.** Late config resolution, no-activation success, and unavailable-source
generation cannot pass.

### TC-05: Reuse equal reprocess work and supersede stale work

Execute TC-01 equal-work branches while matching work processes and after it succeeds. Hold A before
finalization, advance current/served state, then release A. Require immutable reuse; A terminal
`superseded`; already-started attempt counted; no added retry; no current/served pointer replacement;
and old jobs immutable.

**False pass eliminated.** Post-success duplicate work, old-job mutation, and stale retry cannot
look like valid supersession.

### TC-06: Project exact PDF provenance and frozen legacy citation compatibility

Use deterministic multi-page PDF fixture. Obtain normalized page text from pinned extractor/normalizer
output, not a required persisted page-text artifact. Compare cited exact Document Version, persisted
Chunk ID, 1-based page, half-open offsets, and checksum. Apply `[start:end]` to normalized page text
and require persisted Chunk content/checksum equality plus `page_start == page_end`.

The immutable pre-Issue-19 legacy baseline is commit `c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`,
blob `92fb06d62d3ce926c14f4302ea60c649983c33da`:

```json
{"evidence_id":"E1","document_id":"document-legacy","document_version_id":"version-legacy","source_key":"support/legacy","source_name":"legacy.md","heading_path":["Legacy"],"start_line":1,"end_line":1,"excerpt":"Legacy citation.","content_checksum":"sha256:legacy","page_start":null,"page_end":null,"start_offset":null,"end_offset":null}
```

**False pass eliminated.** Correct page cannot hide wrong Chunk/offset/checksum/cross-page locator,
and same-change-set tests cannot move the legacy compatibility baseline.

### TC-07: Prove tenant retrieval isolation and frozen refusal compatibility

In A, submit unique PDF, run worker, poll success, and ask its unique question. In B, poll A job,
reprocess A version, and ask A question while capturing Question Trace/deterministic retrieval data.
Require zero A Embedding Set IDs, zero A candidate/retrieved Chunk IDs, and every B retrieval identity
(if any) belongs to B.

Freeze the pre-Issue-19 refusal baseline from commit
`c897c2b80b15b3da1eac4734ea37ae78deb4ebe7`, blob
`92fb06d62d3ce926c14f4302ea60c649983c33da`: `decision="REFUSAL"`; answer
`"Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này."`; `citations=[]`;
`refusal_reason="INSUFFICIENT_EVIDENCE"`; and a present opaque trace ID, not a fixed literal value.

Observe completed upload/poll/reprocess/question transports. At acceptance time, inspect Issue #19
change set for UI/frontend artifacts/behavior without assuming framework/layout. Require no SSE,
token events, percentage progress, streaming response, or introduced UI/frontend surface.

**False pass eliminated.** System cannot retrieve A then refuse, move the refusal oracle with tests,
stream a route, or add untested UI while final response appears safe.

## Acceptance-criteria traceability matrix

| Issue #19 criterion | Tests | Coverage |
| --- | --- | --- |
| Upload response: status, job ID, outcome, public state | TC-01 | PASS |
| Six public states and safe terminal metadata | TC-02 | PASS |
| Poll fields, timestamps, hints, no-store | TC-02 | BLOCKED |
| One-snapshot pointers and serving states | TC-02 | PASS |
| Auth-before-lookup and scoped job 404 | TC-02, TC-04 | PASS |
| Reprocess auth, audit, key, historical conflict | TC-01, TC-04 | BLOCKED |
| `same_as_job` and `current` snapshots | TC-04 | BLOCKED |
| Fresh generation and equal-work reuse | TC-01, TC-05 | PASS |
| PDF provenance and backward compatibility | TC-06 | PASS |
| Active-only cited answers and refusal | TC-03, TC-07 | PASS |
| E2E, serving, reprocess, supersession, tenant isolation | TC-03–TC-05, TC-07 | PASS |
| No percentage progress, tokens, SSE, or UI | TC-07 | PASS |

## UPSTREAM AUTHORITY BLOCKERS

1. **Reprocess audit.** Define minimum observable audit correlation semantics, approved safe
   observation seam, and required audit/enqueue relationship or atomicity.
2. **Public timestamp projection.** UTC RFC3339 format is defined. Define canonical public schema/
   field names plus created/started/updated/terminal semantics, retry behavior, nullability, and
   durable-source mapping.
3. **`same_as_job` selection.** Define canonical prior-generation selection or explicit selector
   when one Document Version has multiple historical generations.

## Frontier evidence

Native GitHub dependency is blocker authority. Current read-only evidence agrees #18 is closed:

```powershell
gh issue view 18 --repo NhiBuaa/knora-agent --json number,state,closedAt,url
# {"closedAt":"2026-08-10T01:08:25Z","number":18,"state":"CLOSED",...}

gh api 'repos/NhiBuaa/knora-agent/issues/19/dependencies/blocked_by' --jq '.[] | {number, state, html_url}'
# {"number":18,"state":"closed","html_url":"https://github.com/NhiBuaa/knora-agent/issues/18"}
```

## Approval gate

Do not lock this draft, implement code, execute acceptance, update Issue #19, or change authority
artifacts until explicit human approval of `m2-issue-19-r5`.
