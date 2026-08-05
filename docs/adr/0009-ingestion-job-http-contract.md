# Stable asynchronous ingestion job HTTP contract

Status: accepted

PDF uploads return `202` while a created or reused job is non-terminal and `200` for terminal
idempotency replay or fingerprint deduplication. Every response includes the job ID,
`submission_outcome` and public state. The six public states are `queued`, `processing`,
`retry_scheduled`, `succeeded`, `superseded` and `failed`; retry exhaustion is a safe failure reason,
not a seventh state. Polling is cache-free, UTC RFC 3339 timestamped and guided by server polling
hints; cross-Workspace and unknown jobs share one 404 code.
