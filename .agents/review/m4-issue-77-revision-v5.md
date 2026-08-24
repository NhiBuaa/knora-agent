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
  capability/binding/policy compatibility before acquisition, then reruns them after
  `AcquireApplied` at a deterministic barrier immediately before dispatch authorization. A denied
  second check records sanitized `before_provider_receive`, makes zero provider calls, remains
  `executing` and returns `ExecutionIndeterminate` HTTP 202 without blind retry authority.
- [ ] `ExternalResourceReferenceVerifier.verify_for_side_effect` verifies the exact approved `m4r1`
  key/expiry/Workspace/capability/binding before acquisition and again in the post-acquisition
  current check. Denial produces zero provider calls.
- [ ] `request_fingerprint` is the server-computed `canonical-json-v1` digest of operation, exact
  capability, exact external-scope binding, target reference/resource claims and normalized
  `{title, description}`. It and the logical execution ID are immutable stored values, never client
  input.
- [ ] `ToolActionStore.acquire_execution` captures PostgreSQL `transaction_timestamp()` once and
  atomically creates generation 1, owner, `lease_started_at`, `lease_expires_at = transaction_time +
  lease_duration`, `executing`, audit and an immutable `AuthorizedExecutionBindingSnapshot` without
  raw provider ID. Application/process time never decides lease creation or expiry.
- [ ] Concurrent acquisition returns exactly one `AcquireApplied`; every loser receives the typed
  current `ExecutionInProgress`, conflict or non-executable projection without a provider call.
- [ ] After the second authorization/compatibility check, `authorize_execution_dispatch` performs a
  PostgreSQL-time CAS/validation of current owner, exact generation and unexpired deadline and
  returns one opaque integrity-protected `ExecutionDispatchPermit`. A wrong owner/generation or
  expired lease is `ExecutionFenced`, records no dispatch permit and produces zero provider calls.
- [ ] `ExecutionDispatchPermit` is domain-separated `m4-dispatch-v1` provenance binding Workspace,
  proposal/logical execution ID, stored fingerprint, exact capability/binding/policy digests,
  owner, generation, database-issued time and lease deadline. It is server-minted, never request
  input, and `CreateTicketRequest` must carry the exact permit.
- [ ] The SQLite provider verifies permit integrity, logical ID/fingerprint/binding equality and
  deadline before opening its write transaction. An invalid/expired permit creates no external or
  idempotency row and returns proof-no-write `provider_request_rejected`; Knora records
  `before_provider_receive`, remains `executing` and returns HTTP 202. Because takeover can begin
  only after the prior PostgreSQL deadline, an old generation permit is expired before Issue #78 can
  issue a higher-generation permit.
- [ ] `record_execution_observation` and `finalize_execution` require current owner, exact generation
  and unexpired lease. Issue #77 proves wrong-owner, wrong-generation and expired generation-1 calls
  are `ExecutionFenced`; higher-generation takeover and post-takeover stale-owner finalization remain
  Issue #78.
- [ ] The SQLite reference provider commits its externally visible ticket mutation (or definitive
  rejection) and authoritative idempotency fingerprint/outcome in one `BEGIN IMMEDIATE` transaction.
  Faults before commit roll back both; faults after commit replay one durable outcome. Same-key/
  same-fingerprint repeats replay; same-key/different-fingerprint conflicts; no fault or concurrency
  creates a second logical side effect.
- [ ] Direct provider success finalizes `succeeded`. Closed terminal failures are only
  `target_not_found`, `validation_rejected` or `policy_rejected` and finalize `failed` with sanitized
  audit and `502/TOOL_PROVIDER_FAILURE`.
- [ ] Timeout, acknowledgement loss, provider unavailability or unknown/malformed response whenever
  external receipt is possible returns `ExecutionIndeterminate` HTTP 202, keeps lifecycle
  `executing`, and preserves the same logical ID/fingerprint.
- [ ] Same-logical-ID/different-fingerprint is non-terminal `ProviderIdempotencyConflict`: lifecycle
  remains `executing`, audit stores only the sanitized code, public mapping is HTTP 409
  `TOOL_PROVIDER_IDEMPOTENCY_CONFLICT`, and no provider retry is allowed. Issue #78 may only observe
  provider truth and cannot convert the mismatch to terminal outcome or write authority.
- [ ] The deterministic before-provider-receive case returns non-terminal 202; its no-receipt proof
  is consumed only by provider-first reconciliation and cannot authorize an immediate blind retry.
- [ ] Observation/reconciliation authority alone does not grant write retry authority.
- [ ] Execution actor, both current authorization decisions, exact compatibility evidence,
  PostgreSQL-time lease/dispatch permit, provider identity, immutable binding/fingerprint/logical ID,
  observations and outcome are reconstructable from append-only audit.
- [ ] Existing M1–M3 authorization, provenance and regression behavior remains green.

## Deterministic test seams

- A barrier after `AcquireApplied` but before `authorize_execution_dispatch` changes current
  authorization/compatibility or lets the generation-1 lease expire. Denial/fencing yields zero
  gateway calls. No generation-2 fixture or takeover is created by #77.
- A second barrier after permit issuance but before provider receipt proves an expired/invalid
  permit is rejected by the provider before any SQLite write. Permit MAC/key bytes are never
  evidence or request input.
- A skewed/frozen application clock is set far before and far after PostgreSQL time. Acquisition and
  dispatch evidence records database-issued time and deadline, asserts the configured duration
  exactly, and proves expiry/fencing follows PostgreSQL transaction time despite application skew.
- SQLite fault injection has `before_atomic_commit` and `after_atomic_commit_before_ack`. The first
  rolls back ticket and idempotency rows; the second leaves both committed and replays one outcome.
- The HTTP/result matrix separately covers definitive outcomes, receipt-possible indeterminate,
  pre-dispatch denial/fence, provider permit rejection and non-terminal fingerprint conflict.

## Blocked by

- #75 — M4.1 — Read-only ticket lookup with pre-gateway authorization
- #76 — M4.2 — Immutable write proposal and human approval boundary

## Revision provenance

- Supersedes `.agents/review/m4-issue-77-revision-v4.md` for Issue #77 delivery.
- Closes the two Major findings in
  `.agents/review/m4-issue-77-ticket-external-review-v2.json` while retaining takeover,
  generation 2+ and `ReconcileExecution` in Issue #78.
- `ExecutionDispatchPermit` deepens the approved execution/provider seam; it does not introduce
  dynamic capabilities, a plugin framework or a second workflow owner.
