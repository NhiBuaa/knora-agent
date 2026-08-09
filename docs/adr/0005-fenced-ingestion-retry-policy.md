# Fenced leases and bounded retry generations

Status: accepted

Milestone 2 uses four attempts per Ingestion Job, versioned full-jitter backoff windows of 5
seconds, 30 seconds and 2 minutes capped at 5 minutes, a 2-minute lease with 30-second heartbeat,
and a separate 15-minute maximum attempt runtime. Heartbeats and commits require the matching
`worker_id` and `lease_version` plus an unexpired lease; expiry loses ownership without requiring
another worker to reclaim the row. Retryable infrastructure/provider/database/worker failures are
bounded; invalid input and deterministic processing failures are not retried. A stale activation
CAS becomes `superseded` without scheduling or consuming an additional retry attempt. The attempt
that reached the stale CAS remains counted in `attempt_count`; because the job is then terminal,
unused attempt capacity is irrelevant. Exhausted attempts become `failed` with
`failure_reason = retry_exhausted`; manual reprocess always creates a new job generation. Public
job state remains separate from failure taxonomy. Lease expiry is observed as a retryable worker
failure: recovery atomically closes the expired attempt and schedules the versioned backoff, or
terminally exhausts the job when the expired attempt already used the final attempt. Expiry never
creates an attempt beyond `max_attempts` and does not permit immediate direct reclaim before the
retry schedule is due. PostgreSQL wall clock is authoritative for durable timestamps, scheduling
eligibility and lease fencing. Each lease-sensitive transition samples fresh database time after
potentially blocking lock acquisition and uses that same sample for its predicates and writes;
transaction-start time must not resurrect an expired lease. A separate injected monotonic clock
owns local heartbeat cadence and maximum-runtime scheduling. The persisted deadline is audit data,
not a second predicate that retroactively changes a supervisor completion disposition.

Retry Policy V1 uses one coordinator-level retry-cause taxonomy for handler/provider/database
failures, unexpected worker exceptions, attempt timeout and lease-expiry recovery. After attempts
1, 2 and 3 it samples exact full-jitter durations from `[0, 5s]`, `[0, 30s]` and `[0, 2m]`;
zero delay is valid. It consumes exactly one random sample only when scheduling a retry. A
retryable cause at attempt 4 exhausts without sampling; a non-retryable cause is terminal at any
attempt and never becomes exhaustion. The 5-minute cap applies to a nominal window before sampling
and does not bind any V1 window. Persisted audit includes policy/jitter versions, selected upper
bound, chosen delay and the database-anchored `next_attempt_at`; PRNG state is not persisted.

Expiry recovery is an optimistic observe/conditional-apply protocol. Observation confers no lock
or ownership and includes the exact current lease expiry because heartbeat can extend expiry
without changing lease version. Apply revalidates all policy and identity inputs, then records the
observed `lease_expired` cause separately from the V1 result (`ScheduleRetry` or
`RetryExhausted`). Stale snapshot and current-but-not-expired are disjoint expected race results;
decision/capacity mismatch is an invariant error. Recovery always commits retry-scheduled before a
separate due claim, including when selected delay is zero.

Failure Cause V1 is one closed coordinator-level taxonomy of observed facts, not separate retryable
and terminal taxonomies. A pure versioned mapper converts handler-specific failure kinds; attempt
timeout and lease expiry originate directly from supervisor/recovery. Worker crash is not a V1
cause because the database cannot distinguish crash, partition, pause or heartbeat loss—only
`LEASE_EXPIRED` is durable fact. Retry Policy V1 alone maps canonical cause to schedule, terminal
failure or exhaustion. Attempt history persists cause/version so later policy changes cannot
reinterpret it.
