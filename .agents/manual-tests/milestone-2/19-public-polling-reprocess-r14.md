# Manual Test Guide Revision: Resolved authority oracles

## Metadata

- Status: Locked after explicit human approval. Do not change this revision.
- Feature/Slice: Milestone 2, GitHub Issue #19
- Guide revision: `m2-issue-19-r14`
- Base guide: `m2-issue-19-r13`
- Scope: this revision replaces only the four formerly BLOCKED oracles below. Every PASS criterion
  and Test Case in r13 remains unchanged and is incorporated by reference.
- Authority: ADR 0009, ADR 0010, and Architecture Standard, approved by human review.
- Approved by: human reviewer (user)
- Approved at: 2026-08-10T12:16:02+07:00

## Replacement oracle A: Manual-reprocess audit contract

Extend the reprocess cases in r13 with an approved read-only application, repository, or audit
projection seam.

1. Submit one accepted manual reprocess with scoped `(workspace_id, reprocess operation,
   Idempotency-Key)`. Require exactly one audit record and one request-idempotency binding.
2. Require the audit record, binding, and durable created-generation or reused-generation decision
   to commit atomically in one PostgreSQL transaction. No accepted logical reprocess request or Job
   binding may exist without its audit record.
3. Repeat the same key and request. Require the same logical request/generation and no extra audit
   record.
4. Submit a fresh key that equal-work deduplicates/reuses an existing processing or succeeded
   generation. Require one new audit record for the fresh logical request and a reused-generation
   outcome.
5. Inspect the safe audit projection. Require audit event ID, Workspace ID, safe actor/key ID,
   `action=document_version.reprocess`, target Document Version ID, requested/resolved config mode,
   resulting Ingestion Job ID, created-versus-reused outcome, database-created timestamp, and any
   available opaque trace/correlation ID. Raw credentials and raw Idempotency Keys are absent.
6. For authentication/authorization failure, invalid/missing config mode, historical target, and
   unavailable source, do not require an Issue #19 manual-reprocess audit record.

**False pass eliminated.** A same-key replay cannot write a duplicate audit record, and an accepted
created/reused decision cannot commit without the matching audit record and Idempotency binding.

## Replacement oracle B: Public lifecycle timestamps

Use controlled PostgreSQL time and public polling to observe one Job through creation, first claim,
retry scheduling, a later claim, and terminalization.

| Field | Required public oracle |
| --- | --- |
| `created_at` | Present in every state; equals PostgreSQL time at durable Job-generation creation; immutable. |
| `started_at` | Null before the first successful transition to `processing`; equals PostgreSQL time of that first transition; remains immutable across retries, later attempts, and terminalization; never equals a current-attempt timestamp by definition. |
| `updated_at` | Present in every state; equals PostgreSQL time of the latest durable public lifecycle mutation. It changes for public status, attempt count, `next_attempt_at`, or terminal-outcome change; it does not change for heartbeat-only lease renewal or another Job's serving-pointer change. |
| `terminal_at` | Null in `queued`, `processing`, and `retry_scheduled`; set once at PostgreSQL transition to `succeeded`, `superseded`, or `failed`; immutable thereafter. |

Every non-null public timestamp serializes as UTC RFC3339. The controlled retry sequence proves that
retries do not reset `started_at`; it also distinguishes public `updated_at` from heartbeat-only
coordination updates.

**False pass eliminated.** A current-attempt timestamp cannot masquerade as `started_at`, and lease
heartbeats cannot falsely advance public `updated_at`.

## Replacement oracle C: `same_as_job` explicit selector

For `config_mode=same_as_job`, supply an explicit `config_source_job_id`.

1. Use a source Job in the authorized Workspace that targets the exact reprocessed Document Version.
   Require its immutable parser, normalizer, chunking, and embedding configuration IDs to be copied
   to the request target. If a fresh generation is created, require
   `reprocess_of_job_id=config_source_job_id`.
2. With matching Document Version/configuration work already processing or succeeded, require the
   established equal-work reuse behavior without resolving mutable/current configuration in the
   worker.
3. Omit, invalidate, or mismatch `config_source_job_id`. Require rejection before generation
   creation. Do not require an unrelated public validation error code.
4. Verify that timestamp, UUID ordering, `MAX(id)`, and a hidden latest-Job rule cannot select a
   configuration source.
5. For `config_mode=current`, require no source Job selector and preserve r13's C1→C2 immutable
   snapshot oracle.

**False pass eliminated.** A handler cannot infer an ambiguous previous generation or use a source
Job from another Workspace or Document Version.

## Replacement oracle D: Successful polling result

After the actual worker completes a complete derivation and activation CAS for one Job, poll it as
`succeeded`. Require exactly this successful public result projection:

```json
{
  "result": {
    "document_version_id": "<target_document_version_id>"
  }
}
```

Require `result.document_version_id` to equal the Job `target_document_version_id`. The result appears
only after the successful durable commit. It is absent for `queued`, `processing`, `retry_scheduled`,
`failed`, and `superseded`. Failed retains safe `failure_reason` and `error_code`; superseded retains
only separately governed optional replacement metadata. The result exposes no Chunk Set, Embedding
Set, lease, worker, or other internal coordination identifier.

**False pass eliminated.** A worker cannot publish success before activation commit, and failed or
superseded polling cannot expose a successful result.

## Acceptance-criteria traceability matrix

| Issue #19 criterion | Tests | Coverage |
| --- | --- | --- |
| Upload response: status, job ID, outcome, public state | r13 TC-01 | PASS |
| Six public states and terminal metadata | r13 TC-01/TC-02 | PASS |
| Poll fields, timestamps, hints, no-store | r13 TC-02; replacement B/D | PASS |
| One-snapshot pointers and serving states | r13 TC-02 | PASS |
| Auth-before-lookup and scoped job 404 | r13 TC-02/TC-04 | PASS |
| Reprocess auth, audit, key, historical conflict | r13 TC-01/TC-04; replacement A | PASS |
| `same_as_job` and `current` snapshots | r13 TC-04; replacement C | PASS |
| Fresh generation and equal-work reuse | r13 TC-01/TC-04/TC-05; replacement C | PASS |
| PDF provenance and backward compatibility | r13 TC-06 | PASS |
| Active-only cited answers and refusal | r13 TC-03/TC-07 | PASS |
| E2E, serving, reprocess, supersession, tenant isolation | r13 TC-03–TC-05/TC-07 | PASS |
| No percentage progress, tokens, SSE, or UI | r13 TC-07 | PASS |

## Locked execution gate

This locked guide may authorize the next `implement` transition only. Acceptance execution still
requires a completed implementation result and a separate human approval of the acceptance verdict.
