## Parent

#74 — Milestone 4 — Tools and human approval

## What to build

Deliver the approved `create_ticket` execution path end to end behind the existing deep
`WriteProposalWorkflow.handle(ExecuteApprovedProposal, principal, actor_context)` interface.
Execution requires current Workspace, resource, capability and execution authorization independently
of human approval. PostgreSQL owns the typed generation-1 execution lease, immutable authorized
binding snapshot, dispatch-authority ordering and permit provenance. The SQLite reference provider
owns the independent authoritative external-effect/idempotency outcome.

No caller orchestrates `check -> acquire -> authorize -> permit -> dispatch -> observe -> finalize`.
The implementation hides that ordering, all lock/time rules and every permit field. The capability
registry remains static and typed; this ticket adds no plugin framework, takeover, generation 2+ or
reconciliation workflow.

## Acceptance criteria

- [ ] `ExecuteApprovedProposal` starts only from an approved, exact-compatible and non-expired
  proposal. A pre-acquisition current Workspace/resource authorization, `ExecutionAuthorizer`, exact
  capability/binding/policy compatibility and exact `m4r1` verification may fail fast, but it is not
  dispatch authority. A denied pre-acquisition check makes zero provider calls and creates no
  execution.
- [ ] `request_fingerprint` is the stored server-computed `canonical-json-v1` digest of operation,
  exact capability, exact external-scope binding, target reference/resource claims and normalized
  `{title, description}`. It and the logical execution ID are immutable, never client input and are
  reused unchanged at every generation and provider boundary.
- [ ] `ToolActionStore.acquire_execution` locks the approved proposal/execution row, samples one
  fresh PostgreSQL `clock_timestamp()` after every potentially blocking lock acquisition, and
  atomically creates generation 1, owner, `lease_started_at`,
  `lease_expires_at = database_time + lease_duration`, lifecycle `executing`, audit and an immutable
  `AuthorizedExecutionBindingSnapshot` without a raw provider ID. Application, process and provider
  clocks never decide lease creation or expiry.
- [ ] Concurrent acquisition returns exactly one `AcquireApplied`; every loser receives the typed
  current `ExecutionInProgress`, conflict or non-executable projection without a provider call.
- [ ] PostgreSQL owns one typed Workspace-scoped `dispatch_authority_epoch`. Every supported mutable
  change that can alter current Workspace access, resource authorization, execution authorization,
  exact capability/binding/policy selection or reference-key validity must lock and advance that
  epoch in the same transaction as the change. A mutable authority source that cannot participate
  in this protocol is not eligible to authorize M4 dispatch; immutable runtime inputs must carry an
  exact version/digest in the epoch-bound state.
- [ ] After `AcquireApplied`, one private `authorize_and_issue_dispatch` transaction locks the
  execution row and the Workspace `dispatch_authority_epoch` in canonical order. It reloads and
  verifies the exact proposal, current principal/Workspace grant, `m4r1` trusted-store record and key
  state, resource grant, `ExecutionAuthorizer` inputs and current exact capability/binding/policy
  tuples. It evaluates current Workspace/resource authorization, `ExecutionAuthorizer` and
  `CompatibilityCheckerV1` inside that transaction; caller-computed booleans or compatibility
  assertions are forbidden.
- [ ] After those locks and evaluations, `authorize_and_issue_dispatch` samples a fresh PostgreSQL
  `clock_timestamp()`, requires the current owner, exact generation and `db_now < lease_expires_at`,
  then atomically stores one permit record/digest plus sanitized audit and returns an opaque
  `ExecutionDispatchPermit`. The authorization decision and permit issuance have no callback,
  await, caller-visible seam or mutable-authority gap. Revocation/change committed first denies
  issuance; issuance committed first has an exact epoch witness. An ambiguous same-generation
  issuance is reconciled by read-back of the one stored permit and never mints a second claim set.
- [ ] `ExecutionDispatchPermit` is domain-separated `m4-dispatch-v2` provenance binding Workspace,
  proposal/logical execution ID, stored fingerprint, exact capability/binding/policy/reference
  digests, authority epoch/witness digest, owner, generation, PostgreSQL issued time, lease deadline,
  purpose and signing-key version. It is integrity-protected, has a private constructor, is never
  request input and is the only envelope accepted by `SupportToolGateway.create_ticket`.
- [ ] The SQLite reference provider verifies permit syntax/MAC and exact request equality before
  touching SQLite. It then opens `BEGIN IMMEDIATE` only to obtain the SQLite writer lock, with zero
  row mutation, and invokes a private PostgreSQL receipt-admission Adapter. Admission locks the
  current execution row and Workspace authority-epoch row, samples fresh PostgreSQL
  `clock_timestamp()` only after those locks, and requires exact stored permit digest, unchanged
  authority epoch/witness, owner, generation, logical ID/fingerprint/binding and
  `db_now < lease_expires_at`.
- [ ] Receipt admission retains the PostgreSQL execution/epoch locks while the bounded local SQLite
  transaction atomically commits its ticket or definitive rejection plus idempotency outcome. Only
  after SQLite durability does it release the PostgreSQL locks. Therefore a provider admission and
  a later authority revocation or Issue #78 takeover have one deterministic order: if the mutation
  or takeover wins first, the old permit is rejected before SQLite mutation; if admission wins
  first, the external outcome is durable before that later change can commit. Provider/process
  wall-clock skew is irrelevant.
- [ ] Successful receipt admission is the provider-acceptance linearization point. A request admitted
  before its PostgreSQL deadline may finish its already-admitted bounded SQLite commit after that
  deadline; the same logical ID/fingerprint still permits at most one outcome. If the PostgreSQL
  guard session becomes unavailable before SQLite durability, the reference Adapter must roll back
  before any ticket/idempotency commit and return proof no write. This fail-closed guard-loss path is
  deterministic release evidence; M4 makes no claim for an arbitrary remote vendor or distributed
  partition protocol.
- [ ] Failed or unavailable receipt admission rolls back the untouched SQLite transaction and
  returns proof-no-write `provider_request_rejected`. Knora records sanitized
  `before_provider_receive`, remains `executing` and returns `ExecutionIndeterminate` HTTP 202. The
  proof grants no immediate blind retry authority; Issue #78 must observe provider truth first.
- [ ] `record_execution_observation` and `finalize_execution` require current owner, exact generation
  and a fresh PostgreSQL-time unexpired lease. Issue #77 proves wrong-owner, wrong-generation and
  expired generation-1 calls are `ExecutionFenced`; higher-generation takeover and post-takeover
  stale-owner finalization remain Issue #78.
- [ ] The SQLite provider commits its externally visible ticket mutation or definitive rejection and
  authoritative idempotency fingerprint/outcome in one `BEGIN IMMEDIATE` transaction. Faults before
  commit roll back both; faults after commit replay one durable outcome. Same-key/same-fingerprint
  repeats replay; same-key/different-fingerprint conflicts; no fault or concurrency creates a second
  logical side effect. The SQLite ledger remains durable and independently queryable when Knora's
  PostgreSQL action state or process restarts.
- [ ] Direct provider success finalizes `succeeded`. Closed terminal failures are only
  `target_not_found`, `validation_rejected` or `policy_rejected` and finalize `failed` with sanitized
  audit and `502/TOOL_PROVIDER_FAILURE`. Timeout, acknowledgement loss, provider unavailability or
  unknown/malformed response whenever receipt is possible returns `ExecutionIndeterminate` HTTP
  202, keeps lifecycle `executing`, and preserves the same logical ID/fingerprint.
- [ ] Same-logical-ID/different-fingerprint is non-terminal `ProviderIdempotencyConflict`: lifecycle
  remains `executing`, audit stores only the sanitized code, public mapping is HTTP 409
  `TOOL_PROVIDER_IDEMPOTENCY_CONFLICT`, and no provider retry is allowed. Observation authority alone
  never grants write authority.
- [ ] Execution actor, both current authorization decisions, exact compatibility, authority epoch
  and witness, PostgreSQL lease/permit times, provider identity, immutable binding/fingerprint/
  logical ID, observations and outcome are reconstructable from append-only audit. Raw provider IDs,
  routing handles, permit MAC/key bytes and authority secrets never enter public projections or
  audit.
- [ ] Existing M1–M3 authorization, provenance and regression behavior remains green.

## Deterministic test seams

- A barrier after `AcquireApplied` but before private `authorize_and_issue_dispatch` changes each
  current Workspace/resource/execution authority, capability/binding/policy selector and reference
  key state independently. The final transaction observes the change, emits no permit, makes zero
  gateway calls, records `before_provider_receive` and remains `executing`/202.
- A barrier while dispatch authorization holds its locks races an epoch-advancing revocation against
  permit issuance. The only outcomes are: revocation commits first and issuance denies, or issuance
  commits first with its exact epoch witness and revocation commits later. There is no permit whose
  witness was stale at issuance, and concurrent same-generation issuers persist at most one
  canonical permit.
- A barrier after permit issuance but before provider admission holds delivery until PostgreSQL time
  passes the permit/lease deadline and freezes/skews application and provider clocks both far behind
  and ahead. Admission rejects before any SQLite row mutation.
- `sqlite_writer_locked_before_postgres_admission` proves `BEGIN IMMEDIATE` has changed zero rows.
  `postgres_admitted_before_sqlite_commit` proves the execution/epoch locks remain held until the
  terminal SQLite outcome is durable. A competing epoch mutation is ordered after that commit; a
  competing fenced generation change cannot overlap the admitted write. No generation-2 fixture or
  takeover operation is implemented by #77.
- A guard-session-loss fault after admission but before SQLite durability rolls back ticket and
  idempotency rows and returns proof no write. A separately paused, healthy admission that crossed
  its deadline after admission may finish once and still cannot duplicate the logical effect.
- Acquisition, permit issuance, receipt admission, observation and finalization tests compare their
  decisions to fresh PostgreSQL `clock_timestamp()` sampled after lock acquisition. A deliberately
  blocked transaction proves a transaction-start timestamp cannot revive expired authority.
- SQLite fault injection retains `before_atomic_commit` and `after_atomic_commit_before_ack`. The
  first rolls back ticket and idempotency rows; the second leaves both committed and replays one
  outcome after independent provider restart.
- The HTTP/result matrix separately covers definitive outcomes, receipt-possible indeterminate,
  pre-acquisition denial, post-acquisition denial/fence, receipt-admission rejection and non-terminal
  fingerprint conflict.

## Boundary and lock-order constraints

- `WriteProposalWorkflow.handle` remains the only application-facing write workflow Interface.
  `authorize_and_issue_dispatch`, the authority epoch and provider receipt admission are internal
  seams; HTTP callers and tests cannot construct their capabilities.
- PostgreSQL operations that need both rows lock execution first and Workspace authority epoch
  second. Reference-provider write admission obtains the SQLite writer lock before those PostgreSQL
  locks and performs no SQLite mutation until admission succeeds. Every reference-provider write
  follows this order and uses bounded transaction/idle timeouts.
- Holding PostgreSQL locks across the short local SQLite commit is approved only for the
  deterministic M4 reference provider. A future remote vendor that cannot participate in this
  admission protocol requires a separately approved dispatch/time protocol; M4 does not generalize
  this into distributed transactions.
- The provider admission Adapter may read/lock Knora execution authority but cannot write proposal,
  lifecycle, observation or audit state. SQLite remains the sole owner of provider tickets and
  idempotency outcomes; `ToolActionStore` cannot invent provider truth.

## Blocked by

- #75 — M4.1 — Read-only ticket lookup with pre-gateway authorization
- #76 — M4.2 — Immutable write proposal and human approval boundary

## Revision provenance

- Supersedes `.agents/review/m4-issue-77-revision-v5.md` for Issue #77 delivery and is exceptional
  ticket-contract revision 4 authorized by the repository owner on 2026-08-23.
- Closes `authority_permit_linearization_gap` by binding current authority, compatibility, epoch
  witness and permit issuance in one PostgreSQL transaction, then checking the same epoch again at
  receipt admission.
- Closes `provider_deadline_time_authority_gap` by using fresh PostgreSQL `clock_timestamp()` after
  receipt locks and retaining the PostgreSQL fence through the bounded SQLite commit; no provider or
  process wall clock is trusted.
- Preserves Issue #78 ownership of provider-first reconciliation, stale-lease takeover, generation
  2+, retry authorization and stale-owner finalization. Final M4 code review remains forbidden until
  Issues #75–#79 are accepted, integrated and closed.
