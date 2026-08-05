# PostgreSQL-backed ingestion jobs with fenced leases

Status: accepted

Milestone 2 uses PostgreSQL as the durable Ingestion Job store and worker coordination mechanism,
with atomic claims, expiring leases and a fencing/lease version. Workers may reclaim expired jobs,
but parsing, chunking and embedding never run inside the claim transaction. This preserves one
transactional source of truth for job state, retry metadata, derivation constraints and active
Embedding Set compare-and-swap while keeping the existing deployment small. Delivery is
at-least-once, so processing must be idempotent and database constraints remain the final guard
against duplicate derivations. Redis or another broker is deferred until measured queue depth,
queue latency, claim latency or contention demonstrates that PostgreSQL cannot meet the required
throughput; the worker must expose those metrics before that decision can be revisited.
