# Fenced leases and bounded retry generations

Status: accepted

Milestone 2 uses four attempts per Ingestion Job, versioned full-jitter backoff windows of 5
seconds, 30 seconds and 2 minutes capped at 5 minutes, a 2-minute lease with 30-second heartbeat,
and a separate 15-minute maximum attempt runtime. Heartbeats and commits require the matching
`worker_id` and `lease_version`. Retryable infrastructure/provider/database/worker failures are
bounded; invalid input and deterministic processing failures are not retried. A stale activation
CAS becomes `superseded` without consuming retry budget, while exhausted attempts become
`failed` with `failure_reason = retry_exhausted`; manual reprocess always creates a new job
generation. Public job state remains separate from failure taxonomy.
