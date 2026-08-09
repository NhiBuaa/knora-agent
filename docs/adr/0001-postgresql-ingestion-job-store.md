# PostgreSQL-backed ingestion jobs with fenced leases

Status: accepted

Milestone 2 uses PostgreSQL as the durable Ingestion Job store and worker coordination mechanism,
with atomic claims, expiring leases and a fencing/lease version. Expired claims are first recovered
as a bounded retry or exhaustion transition; another worker may claim the retry when its schedule
is due. Parsing, chunking and embedding never run inside the claim transaction. This preserves one
transactional source of truth for job state, retry metadata, derivation constraints and active
Embedding Set compare-and-swap while keeping the existing deployment small. Delivery is
at-least-once, so processing must be idempotent and database constraints remain the final guard
against duplicate derivations. Redis or another broker is deferred until measured queue depth,
queue latency, claim latency or contention demonstrates that PostgreSQL cannot meet the required
throughput; the worker must expose those metrics before that decision can be revisited.

Worker coordination mutations use one logical operation ID across transport retry and read-back.
Claim and transition IDs are retained with attempt history and bound to their immutable request;
replay returns the persisted result only after any required current-ownership check. Heartbeat
retains only its latest ID/result and therefore permits one logical heartbeat in flight. An
unreconciled ambiguous commit is an explicit indeterminate infrastructure outcome, never an
invented lifecycle transition. A generic operation ledger is deferred because Issue #17 does not
require historical heartbeat replay or exact replay of a no-op claim.
