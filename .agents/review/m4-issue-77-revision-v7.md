## Parent

#74 — Milestone 4 — Tools and human approval

## What to build

Deliver the approved `create_ticket` execution path end to end behind the existing deep
`WriteProposalWorkflow.handle(ExecuteApprovedProposal, principal, actor_context)` interface.
Execution requires current Workspace/resource authorization, `ExecutionAuthorizer` approval and
exact capability/binding/policy/reference compatibility independently of the earlier human approval.

PostgreSQL owns the generation-1 execution lease and one durable `DispatchAdmission`. The admission
is the authorization/dispatch linearization point: it is persisted before any gateway invocation and
survives process or database-session loss. The SQLite reference provider independently owns the
authoritative external-effect/idempotency ledger. No PostgreSQL session lock is held across the
SQLite transaction, and no cross-store rollback claim is made.

No caller orchestrates `check -> acquire -> admit -> dispatch -> observe -> finalize`. The
implementation hides that ordering, every authority epoch, admission field and recovery boundary.
The capability registry remains static and typed. This ticket adds no plugin framework, takeover,
generation 2+ or reconciliation workflow.

## Acceptance criteria

- [ ] `ExecuteApprovedProposal` starts only from an approved proposal. Before acquisition it checks
  current Workspace/resource authorization, `ExecutionAuthorizer`, exact capability/binding/policy
  compatibility and exact integrity/trusted-store validity of the opaque `m4r1` target reference.
  These checks are fail-fast only and grant no dispatch authority. Every denial class creates no
  execution or admission, appends no execution-start audit and makes zero gateway/provider calls.
  Temporary execution-authority denial leaves the immutable proposal `approved` but currently
  non-executable; a material capability/binding/policy/reference incompatibility yields a stale
  projection and requires a new proposal and human approval. Proposal expiry is decided at
  acquisition: it blocks starting a new execution, but is not re-applied after acquisition to cancel
  that already-started execution.
- [ ] `request_fingerprint` is the stored server-computed `canonical-json-v1` digest of operation,
  exact capability, exact external-scope binding, target reference/resource claims and normalized
  `{title, description}`. It and the logical execution ID are immutable, never client input and are
  reused unchanged at the admission and every provider/recovery boundary.
- [ ] `ToolActionStore.acquire_execution` locks the approved proposal/execution row, samples fresh
  PostgreSQL `clock_timestamp()` after every potentially blocking lock acquisition, and atomically
  requires database time before proposal expiry, then creates generation 1, owner,
  `lease_started_at`, `lease_expires_at = database_time + lease_duration`, lifecycle `executing`,
  append-only audit and an immutable
  `AuthorizedExecutionBindingSnapshot` without a raw provider ID. Concurrent acquisition has one
  atomic winner; losers return a typed current projection and make zero provider calls.
- [ ] PostgreSQL owns a fixed typed `DispatchAuthorityEpochVector`: one global
  `reference_key_epoch` plus one Workspace-scoped `workspace_dispatch_epoch`. Workspace access,
  resource/execution authorization and current typed capability/binding/policy selectors are
  Workspace-owned rows and advance `workspace_dispatch_epoch` in their mutation transaction.
  Reference-key status changes advance `reference_key_epoch`; a change that also materializes
  Workspace state uses the canonical global-then-Workspace epoch order. The compiled static
  capability registry is immutable and contributes its exact version/digest, not a mutable plugin
  epoch. A mutable source that cannot participate in this fixed protocol is ineligible to authorize
  M4 dispatch.
- [ ] After `AcquireApplied`, one private `authorize_and_admit_dispatch` PostgreSQL transaction locks
  the execution row and both fixed authority-epoch rows in canonical order. It reloads the immutable
  proposal, current principal/Workspace grant, resource grant, `ExecutionAuthorizer` inputs and
  current exact capability/binding/policy tuples. It fully re-verifies the exact approved `m4r1`
  canonical bytes, MAC, claims, Workspace/capability/binding equality, trusted-store record and
  current key status inside that transaction. It evaluates all authorization and
  `CompatibilityCheckerV1` decisions there and accepts no caller-computed authorization,
  compatibility, epoch, digest, time or admission claim.
- [ ] Only after all potentially blocking locks and evaluations,
  `authorize_and_admit_dispatch` samples fresh PostgreSQL `clock_timestamp()`, requires current
  owner, exact generation, `db_now < lease_expires_at` and `db_now < m4r1.expires_at`, and atomically
  persists one immutable `DispatchAdmission` plus sanitized audit. The unique admission binds
  Workspace, proposal, logical execution ID, request fingerprint, exact capability/binding/policy/
  reference identities and digests, both authority epochs and their witness, owner, generation,
  database issue time, lease deadline, purpose, admission schema and signing-key version. Ambiguous
  commit is resolved by exact read-back; it
  never creates a second admission or claim set. Canonical envelope bytes/MAC are either persisted
  with the admission or reconstructed byte-identically from its canonical claims using retained
  versioned signing material; restart and key rotation cannot change or invalidate them while the
  execution remains non-terminal. Storage enforces at most one admission per logical execution,
  regardless of which lease generation creates that first admission.
- [ ] Durable admission is the dispatch authorization linearization point and the logical start of
  the provider write. It commits immediately before the gateway call, with no intervening mutable
  authority decision or caller-visible seam. For each authority,
  selector and reference-key mutation class, mutation-first causes denial and zero admission;
  admission-first records the exact prior epoch and the later mutation does not retroactively cancel
  that already-admitted dispatch. Lease/reference expiry blocks a new admission, while proposal
  expiry blocks acquisition; none cancels delivery, provider completion or provider-first
  reconciliation of an existing admission. Material fields
  never retarget: the admitted capability version, binding, policy/reference digests, logical ID and
  fingerprint remain exact and immutable.
- [ ] `DispatchAdmissionEnvelope` is opaque, integrity-protected, domain-separated
  `m4-dispatch-admission-v1`, privately constructed from the durable admission and is the only
  request accepted by `SupportToolGateway.create_ticket`. The reference provider verifies envelope
  integrity, admission/request equality and the immutable fingerprint before any SQLite mutation.
  It does not re-authorize from human approval, trust caller fields, compare provider/process clocks
  or depend on a live PostgreSQL lock/session at receipt. Exact historical verification-key material
  remains available by bound key version for admitted executions; key rotation never upgrades or
  silently retargets an existing envelope.
- [ ] The SQLite reference provider atomically commits its externally visible ticket or one closed
  definitive rejection together with the authoritative logical-ID/fingerprint/outcome ledger in one
  `BEGIN IMMEDIATE` transaction. Same logical ID/same fingerprint replays the one outcome; same ID
  with another fingerprint conflicts; faults before commit roll back both rows; faults after commit
  but before acknowledgement leave one replayable durable outcome. Provider state remains
  independently queryable across Knora/PostgreSQL or provider-process restart.
- [ ] Any crash, timeout, acknowledgement loss, transport uncertainty or PostgreSQL-session loss
  after durable admission but before Knora durably finalizes a closed provider result is
  receipt-possible `indeterminate_external_outcome`, never proof-no-write or definitive failure.
  Knora remains `executing`, preserves the same admission/logical ID/fingerprint and performs no
  blind retry in #77. Issue #78 must observe the provider ledger first; provider `not found` is
  non-terminal, does not retire the admission and does not prove that a delayed envelope cannot
  arrive. The admission remains receipt-possible until the provider ledger has a terminal outcome;
  M4 defines no provider-side atomic cancellation result. After current Workspace/resource and
  execution authorization, full `m4r1` side-effect verification and exact capability/binding/policy
  compatibility succeed, any #78 retry re-dispatches the byte-identical existing admission envelope
  rather than creating a second admission. A delayed original delivery and recovery delivery race
  only through SQLite's same logical-ID/same-fingerprint idempotency rule.
- [ ] An orphaned `executing` record with no durable admission has proof that this workflow never
  invoked the gateway, because the gateway accepts only a committed admission envelope. Issue #78
  still observes provider truth before recovery. After stale takeover and full current
  Workspace/resource/execution authorization, `m4r1` side-effect verification and exact
  compatibility, it may atomically create the first and only admission bound to the current
  generation and dispatch it with the original logical ID/fingerprint. If those checks fail it
  creates no admission. This #78 compatibility rule does not add takeover or generation 2+ to #77.
- [ ] `record_execution_observation` and `finalize_execution` lock the execution row and sample fresh
  PostgreSQL `clock_timestamp()` after the lock. They require current owner, exact generation and an
  unexpired generation-1 lease. A provider result delayed across lease expiry cannot be finalized by
  the stale generation-1 owner; lifecycle remains `executing`/recovery-required and authoritative
  provider truth is not rewritten. Issue #78 owns provider-first reconciliation, stale-lease
  takeover, generation 2+ and stale-owner fencing.
- [ ] Only direct provider success finalizes `succeeded`. Closed terminal failures are exactly
  `target_not_found`, `validation_rejected` or `policy_rejected` and finalize `failed` with sanitized
  audit and `502/TOOL_PROVIDER_FAILURE`. Receipt-possible outcomes return HTTP 202
  `indeterminate_external_outcome`. Same-logical-ID/different-fingerprint remains non-terminal
  `ProviderIdempotencyConflict`, HTTP 409, with no retry authority. Read/observation authority never
  grants write authority.
- [ ] One canonical audit projection reconstructed solely from append-only PostgreSQL records after
  restart exactly matches: proposal actor, approval actor, execution actor, authenticated Workspace
  principal provenance, both current authorization decisions, exact compatibility decision,
  authority epoch/witness, admission identity/digest, database lease/admission times, provider
  identity alias, immutable capability/binding/policy/reference/intent/logical-ID/fingerprint,
  observations and final/non-terminal outcome. It separately proves that raw provider IDs, routing
  handles, admission MAC/key bytes, credentials and authority secrets are absent.
- [ ] Existing M1–M3 authorization, provenance and regression behavior remains green.

## Deterministic test seams

- A public-workflow pre-acquisition matrix independently denies Workspace access, resource access,
  execution authority, capability compatibility, binding compatibility, policy compatibility,
  reference integrity, trusted-store equality and reference-key validity. Every case asserts no
  execution/admission/audit-start row and zero gateway/provider calls.
- A barrier after `AcquireApplied` but before `authorize_and_admit_dispatch` independently changes
  every Workspace/resource/execution authority, capability/binding/policy selector and reference-key
  state. The final transaction observes each change, persists no admission, makes zero gateway calls
  and remains `executing` with sanitized `before_provider_receive` evidence.
- A parameterized issuance race covers every mutation class governed by
  `DispatchAuthorityEpochVector`, using each real typed mutation Adapter rather than a generic epoch
  increment. For each class the only outcomes are mutation-first denial or admission-first with the
  exact witnessed prior vector followed by the mutation. Concurrent
  same-generation issuers persist one byte-identical admission/audit record.
- Separate temporal barriers prove each boundary with independently skewed application/provider
  clocks: acquisition blocks on the proposal row across proposal expiry and creates no execution;
  admission blocks on its canonical locks across `m4r1` expiry or generation-1 lease expiry and
  creates no admission. Every decision uses fresh post-lock PostgreSQL `clock_timestamp()`; a
  transaction-start timestamp would fail each oracle. Proposal expiry after successful acquisition
  alone does not cancel the in-progress execution.
- Fault barriers after durable admission cover process/session loss before gateway invocation,
  provider receipt before SQLite commit and SQLite commit before acknowledgement. Durable admission
  always survives. Knora reports receipt-possible indeterminate unless it durably records a direct
  closed result; the independent provider ledger contains either no outcome or exactly one outcome,
  never a duplicate and never a fabricated failure.
- Concurrent `execute` calls for the same proposal prove one generation-1 acquisition, one immutable
  admission/logical identity/fingerprint and at most one logical external side effect. Replayed
  envelopes return the same provider outcome; mismatched fingerprints conflict before a second
  effect.
- Parameterized observation/finalization barriers delay a direct success and each closed failure
  while lock acquisition crosses lease expiry. For `record_execution_observation`, fresh post-lock
  PostgreSQL time returns `ExecutionFenced`, appends no observation/audit row and leaves lifecycle
  `executing`. For `finalize_execution`, it returns `ExecutionFenced` with no terminal rewrite.
  Provider truth remains independently observable, and no generation-2 or takeover fixture is used
  in #77.
- Forge, corrupt, cross-bind and replay `m4-dispatch-admission-v1`, and attempt client logical-ID,
  fingerprint, authority, epoch or digest overrides. Only the private exact envelope is accepted;
  invalid input causes zero SQLite mutation and exposes no secret/raw provider identifier.
- Exercise success, every closed failure, provider rejection, timeout/unavailability/malformed
  receipt-possible response, pre/post-admission crash and fingerprint conflict through application
  and HTTP seams. Assert the exact lifecycle, HTTP code, sanitized audit and retry-prohibition
  matrix.
- Restart/reload PostgreSQL and SQLite independently. Reconstruct the complete canonical audit
  projection field-for-field from append-only records and compare it with immutable
  proposal/admission/provider evidence; separately assert the provider ledger survives Knora loss
  and excluded secret/raw fields never appear. Rotate the admission signing key after persistence
  and prove restart/read-back reconstructs the byte-identical admitted envelope and same provider
  replay without creating a new admission.
- Run focused M4.3 tests, full pytest, Ruff, Compose and clean Alembic verification on the exact
  candidate SHA.

## Boundary and ordering constraints

- `WriteProposalWorkflow.handle` remains the only application-facing write workflow Interface.
  `authorize_and_admit_dispatch`, authority epochs and admission encoding are internal seams; HTTP
  callers and tests cannot construct their capabilities.
- Admission locks the execution row, then the global reference-key epoch, then the Workspace epoch.
  Every operation needing more than one of those rows follows that order; global/Workspace mutation
  Adapters lock only their owned epoch or the global-then-Workspace suffix. Admission and its audit
  commit in PostgreSQL before gateway invocation. No PostgreSQL lock or session is held across
  provider I/O or SQLite durability.
- Later authority mutation, expiry or future takeover must treat a durable admission as
  receipt-possible until a terminal provider-ledger outcome. A point-in-time provider `not found`
  does not close it. Current denial may prevent recovery re-dispatch authorization but cannot turn
  an existing admission into proof-no-write.
- An `executing` record without an admission is a distinct durable branch: the #77 gateway could not
  have been invoked. #78 may create its first admission only after provider-first observation,
  takeover and full current checks. Once any admission exists, no later generation may supersede or
  replace it.
- The reference provider is the deterministic M4 release boundary. It owns SQLite external state
  and its idempotency ledger independently from `ToolActionStore`; PostgreSQL owns admission and
  audit provenance but cannot invent, overwrite or finalize provider truth without an observed
  closed outcome.
- A future arbitrary vendor may implement the same immutable logical identity/idempotency contract,
  but M4 neither claims distributed rollback nor introduces a plugin/provider framework.
- For #77 execution operations, fresh `clock_timestamp()` sampled once after all blocking locks is
  the normative database-time rule. This explicitly refines the shared design's earlier
  `transaction_timestamp()` wording, which cannot prove post-lock freshness after lock waiting. The
  Interface and PostgreSQL ownership remain unchanged; #78 must use the same corrected time rule.

## Blocked by

- #75 — M4.1 — Read-only ticket lookup with pre-gateway authorization
- #76 — M4.2 — Immutable write proposal and human approval boundary

## Revision provenance

- Supersedes `.agents/review/m4-issue-77-revision-v6.md` for Issue #77 delivery and is exceptional
  ticket-contract revision 5 authorized by the repository owner on 2026-08-23.
- Replaces the unimplementable live PostgreSQL receipt-guard claim with a durable PostgreSQL
  `DispatchAdmission` that survives session loss. Post-admission uncertainty is receipt-possible;
  SQLite remains the independent at-most-one-effect authority.
- Defines admission commit as the logical start of the provider write and therefore the exact
  meaning of current authorization "immediately before" the side effect. Later revocation blocks
  new admission/retry authorization but cannot retroactively cancel the admitted in-flight write.
- Adds parameterized linearization races for every authority/selector/reference-key mutation class,
  a post-lock admission-expiry oracle, an expired generation-1 finalization oracle, the full
  pre-acquisition denial matrix and exact canonical audit reconstruction.
- Removes every generation-change/takeover fixture from #77 while preserving #78 ownership of
  provider-first reconciliation, stale-lease takeover, generation 2+, retry authorization and
  stale-owner recovery, including creation of the first admission for an orphan that has none.
- External review of this exact revision is required before guide creation. Final M4 code review
  remains forbidden until Issues #75–#79 are accepted, integrated and closed.
