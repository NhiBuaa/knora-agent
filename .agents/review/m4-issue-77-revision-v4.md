## Parent

#74 — Milestone 4 — Tools and human approval

## What to build

Deliver the approved `create_ticket` execution path end to end. Execution requires current Workspace,
resource, capability and execution authorization independently of human approval. PostgreSQL owns a
typed atomic execution lease and immutable authorized binding snapshot; the SQLite provider boundary
owns the authoritative idempotency outcome.

## Acceptance criteria

- [ ] `ExecuteApprovedProposal` starts only from an approved, exact-compatible and non-expired
  proposal. It runs current Workspace/resource authorization, `ExecutionAuthorizer` and exact
  capability/binding/policy compatibility before acquisition, then reruns all current authorization
  and compatibility checks after `AcquireApplied` immediately before provider invocation. A
  deterministic barrier may revoke authority or change compatibility in that interval. A denied
  second check records a sanitized `before_provider_receive` observation under the current lease,
  makes zero provider calls, keeps lifecycle `executing` and returns `ExecutionIndeterminate` HTTP
  202; it cannot authorize an immediate blind retry.
- [ ] `ExternalResourceReferenceVerifier.verify_for_side_effect` fully verifies the exact approved
  `m4r1` reference/key/expiry/binding before acquisition and again as part of the post-acquisition
  current check. Denial produces zero provider calls.
- [ ] `request_fingerprint` is the server-computed `canonical-json-v1` digest of operation, exact
  capability, exact external-scope binding, target reference/resource claims and normalized
  `{title, description}`. It and the logical execution ID are immutable stored values, never client
  input.
- [ ] `ToolActionStore.acquire_execution` uses PostgreSQL transaction time and the approved typed CAS
  contract to atomically create generation 1, owner/deadline, `executing` state, audit and an
  immutable `AuthorizedExecutionBindingSnapshot` containing no raw provider ID.
- [ ] Concurrent acquisition returns exactly one `AcquireApplied`; every loser receives the typed
  current `ExecutionInProgress`, conflict or non-executable projection without a provider call.
- [ ] `record_execution_observation` and `finalize_execution` require current owner, exact generation
  and unexpired lease. Issue #77 proves wrong-owner, wrong-generation and expired generation-1 calls
  are `ExecutionFenced`; creation/takeover of a higher durable generation and post-takeover stale-owner
  fencing remain Issue #78 acceptance scope.
- [ ] The provider sees one immutable logical execution identity and the exact stored fingerprint.
  Same-key/same-fingerprint repeats replay; same-key/different-fingerprint returns idempotency
  conflict; concurrent calls create at most one logical side effect.
- [ ] The SQLite reference provider commits its externally visible ticket mutation (or definitive
  rejection) and authoritative idempotency fingerprint/outcome in one `BEGIN IMMEDIATE` transaction.
  Faults before commit roll back both; faults after commit replay the one durable outcome. Fault
  injection around the commit boundary proves replay cannot create a second logical side effect.
- [ ] Direct provider success finalizes `succeeded`. Closed terminal failures are only
  `target_not_found`, `validation_rejected` or `policy_rejected` and finalize `failed` with sanitized
  audit and `502/TOOL_PROVIDER_FAILURE` projection.
- [ ] Timeout, acknowledgement loss, provider unavailability or unknown/malformed response whenever
  external receipt is possible returns `ExecutionIndeterminate` HTTP 202, keeps lifecycle
  `executing`, and preserves the same logical ID/fingerprint. It never becomes false failed/succeeded.
- [ ] A same-logical-ID/different-fingerprint provider response is the typed non-terminal
  `ProviderIdempotencyConflict`: lifecycle remains `executing`, audit stores only the sanitized
  conflict code, public mapping is HTTP 409 `TOOL_PROVIDER_IDEMPOTENCY_CONFLICT`, and no provider
  retry is allowed from that execution. Issue #78 must observe provider truth first and may not
  convert the mismatch into success, failure or write authority.
- [ ] The deterministic before-provider-receive case also returns a non-terminal 202 projection; its
  no-receipt evidence is consumed only by provider-first reconciliation and cannot authorize an
  immediate blind retry.
- [ ] Observation/reconciliation authority alone does not grant write retry authority.
- [ ] Execution actor, both current authorization decisions, exact compatibility evidence, lease
  generation, provider identity, immutable binding/fingerprint/logical ID, observation and outcome
  are reconstructable from append-only audit.
- [ ] Existing M1–M3 authorization, provenance and regression behavior remains green.

## Deterministic test seams

- A barrier after `AcquireApplied` and before `SupportToolGateway.create_ticket` changes current
  authorization/compatibility while counting provider calls. It is test composition only and is not
  request input.
- SQLite fault injection has `before_atomic_commit` and `after_atomic_commit_before_ack` modes.
  The first rolls back ticket and idempotency rows; the second leaves both committed and returns an
  indeterminate acknowledgement.
- Generation-1 fencing tests use the typed store API with wrong owner, wrong generation or an
  expired lease. No fixture creates generation 2 in #77; takeover fencing belongs to #78.
- The HTTP/result matrix separately covers definitive terminal outcomes, receipt-possible
  indeterminate outcomes, deterministic before-receive interruption and non-terminal fingerprint
  conflict.

## Blocked by

- #75 — M4.1 — Read-only ticket lookup with pre-gateway authorization
- #76 — M4.2 — Immutable write proposal and human approval boundary

## Revision provenance

- Supersedes `.agents/review/m4-issue-77-revision-v3.md` for Issue #77 delivery.
- Closes the four Major findings in
  `.agents/review/m4-issue-77-ticket-external-review-v1.json` without changing the approved M4
  module boundaries or moving `ReconcileExecution`/takeover into #77.
