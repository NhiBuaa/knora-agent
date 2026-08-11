# Durable Object Lifecycle Maintenance

Status: accepted

Cleanup and reconciliation use a separate `ObjectLifecycleMaintenance` application module with
PostgreSQL-owned Object Lifecycle Work Items and attempt history, rather than extending Ingestion
Job terminal states or making ObjectStore deletion synchronous. Terminalization atomically records
deduplicated lifecycle work; the maintenance worker claims it with an independent lease/fencing and
operation-ID replay boundary, revalidates ownership through a delete-generation capability before
idempotent external deletion, and reconciles a crash between deletion and completion with `head`.
This preserves terminal ingestion outcomes while preventing stale discovery from deleting a newly
retained Original Source Object.

Object Lifecycle Work uses PostgreSQL polling, atomic eligible claim, and states `queued`,
`processing`, `retry_scheduled`, `succeeded` and `failed`. Object Lifecycle Retry Policy V1 has
four total attempts and full-jitter windows of 5 seconds, 30 seconds and 2 minutes. Replaying a
logical operation returns its durable result without creating another attempt or external effect.

The policy receives an injectable deterministic random-source abstraction at its application
boundary. Production wiring supplies process-local randomness; deterministic tests supply a
controlled sequence, so equal policy input and sequence yield equal chosen delay. The policy never
reads global/process randomness directly in deterministic logic. A compatible Issue #17 seam may be
reused, but reuse is not required. Chosen delay remains inside the authoritative inclusive window
and is persisted exactly.

The random-source contract supplies one deterministic full-jitter sample for the policy-requested
upper bound. The policy must use that returned sample as its chosen delay, not merely call and
ignore it. Known controlled samples therefore produce their exact persisted delays, while production
samples remain process-local. This ADR does not require a separately persisted jitter-version field.
