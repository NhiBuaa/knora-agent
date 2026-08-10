# Stable asynchronous ingestion job HTTP contract

Status: accepted

PDF uploads return `202` while a created or reused job is non-terminal and `200` for terminal
idempotency replay or fingerprint deduplication. Every accepted response includes the job ID,
`submission_outcome` and public state. The six public states are `queued`, `processing`,
`retry_scheduled`, `succeeded`, `superseded` and `failed`; retry exhaustion is a safe failure reason,
not a seventh state. Cross-Workspace and unknown jobs share one 404 code.

Polling is cache-free and guided by server polling hints. It projects these UTC RFC 3339 lifecycle
timestamps:

- `created_at` is required, is set by PostgreSQL when the Job generation is durably created, and is
  immutable.
- `started_at` is null before the first successful transition to `processing`, then records that
  first PostgreSQL timestamp and remains immutable across retries and terminalization. It is not a
  current-attempt timestamp.
- `updated_at` is required and records the latest PostgreSQL mutation to the public Job lifecycle
  projection. It changes when public lifecycle fields change, but not for heartbeat-only lease
  renewals or independent Document serving-pointer changes.
- `terminal_at` is null in `queued`, `processing` and `retry_scheduled`. It is set once by the
  PostgreSQL transition to `succeeded`, `superseded` or `failed`, then remains immutable.

For `succeeded`, polling includes exactly one successful terminal-result field:

```json
{
  "result": {
    "document_version_id": "<target_document_version_id>"
  }
}
```

`result.document_version_id` equals the Job target Document Version. `result` appears only after a
complete derivation and activation compare-and-swap commit. Non-terminal, `failed` and `superseded`
states do not expose a successful `result`. Failed polling continues to expose its safe
`failure_reason` and `error_code`. Superseded polling may retain the separately governed optional
replacement Document Version and Job metadata. The successful result must not expose Chunk Set,
Embedding Set, lease, worker or other internal coordination identifiers.
