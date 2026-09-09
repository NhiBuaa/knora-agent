## Parent

#74 — Milestone 4 — Tools and human approval

## What to build

Deliver deterministic recovery and reconciliation for an approved write execution that may be
orphaned by a crash. Provider truth is observed before recovery chooses takeover or retry. The
observation-only authorization path remains available for an already-started execution after
reference expiry/key revocation, but it can never authorize a new provider write.

## Acceptance criteria

- [ ] `ReconcileExecution` handles both an indeterminate observation and an orphaned `executing`
  record with no durable provider-invocation observation.
- [ ] Recovery first calls `get_execution_outcome` with the stored logical execution identity after
  current path-Workspace and `WorkspaceResourceAuthorizer` checks.
- [ ] `ObservationReferenceResolver.resolve_started_execution` uses the immutable
  `AuthorizedExecutionBindingSnapshot`, validates it against proposal/execution state and resolves
  only the trusted opaque routing handle. It does not create write authority.
- [ ] Provider outcome observation and terminal finalization remain allowed after the original
  proposal/reference expires or its key is revoked, provided current Workspace/resource observation
  authorization still passes. A missing/mismatched snapshot or trusted-store record stays typed
  non-terminal and never becomes `failed`.
- [ ] Any provider retry reruns full `m4r1` side-effect verification, current Workspace/resource
  authorization, `ExecutionAuthorizer` and exact capability/binding/policy compatibility. Expired or
  revoked reference/key and material mismatch forbid retry and require a new proposal/approval.
- [ ] `takeover_stale_execution` uses PostgreSQL transaction time, exact expected generation and
  `lease_expires_at < transaction_timestamp()`; Applied increments generation exactly once and
  changes owner/deadline atomically.
- [ ] A current lease returns `ExecutionNotStale`; changed generation returns `ExecutionFenced`;
  already-terminal state returns the persisted outcome. Stale owners cannot record or finalize after
  takeover.
- [ ] `record_execution_observation` and `finalize_execution` enforce exact current owner/generation
  and unexpired lease and expose only the approved typed outcomes.
- [ ] Crash after provider commit but before Knora persistence reconciles provider-authoritative
  success/failure without a duplicate side effect.
- [ ] Crash after Knora persists `executing` but before provider receipt observes not-found, takes
  over only when stale and safely retries using the same stored logical ID and fingerprint when all
  current write checks pass.
- [ ] Provider not-found and observation-unavailable remain distinct non-terminal observations.
- [ ] SQLite provider state/idempotency survives Knora restart independently of `ToolActionStore`.
- [ ] Recovery, takeover, authorization decisions, observations, retries, fencing and finalization
  remain reconstructable from append-only audit.

## Blocked by

- #77 — M4.3 — Approved create-ticket execution with authority and idempotency
