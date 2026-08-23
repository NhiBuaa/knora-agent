## Parent

#74 — Milestone 4 — Tools and human approval

## What to build

Deliver the approved `create_ticket` generation-1 execution path end to end behind the existing deep
`WriteProposalWorkflow.handle(ExecuteApprovedProposal, principal, actor_context)` Interface.
Execution requires current Workspace/resource authorization, `ExecutionAuthorizer` approval and
exact capability/binding/policy/reference compatibility independently of human approval.

PostgreSQL owns atomic acquisition, the immutable authorized binding snapshot, one durable
`DispatchAdmission` per logical execution and append-only audit. The admission commit is the
authorization/dispatch linearization point and logical start of the provider write. The SQLite
reference-provider Adapter independently owns the authoritative external effect and idempotency
outcome. No PostgreSQL session/lock crosses provider I/O or SQLite durability, and no cross-store
rollback claim is made.

No caller orchestrates `check -> acquire -> admit -> dispatch -> observe -> finalize`. The Module
hides the protocol, fixed authority epochs, envelope fields, ordering and crash classification. The
capability registry remains static and typed. This ticket adds no plugin framework,
`ReconcileExecution`, stale takeover or generation 2+ implementation.

## Acceptance criteria

- [ ] `ExecuteApprovedProposal` is reachable only through
  `WriteProposalWorkflow.handle(command, principal, actor_context)`. Its pre-acquisition matrix
  independently checks Workspace access, resource access, execution/write authority, exact
  capability/binding/policy compatibility, complete `m4r1` integrity/trusted-store/key validity and
  proposal expiry. Every denial creates no execution, acquisition/admission/audit-start artifact and
  makes zero gateway/provider calls. A read-only or observation-only principal without execution
  authority is denied identically and cannot escalate to a write. Temporary execution-authority
  denial leaves the immutable proposal `approved`; material incompatibility is stale and requires a
  new proposal and human approval.
- [ ] `request_fingerprint` is the stored server-computed `canonical-json-v1` digest of operation,
  exact capability, exact external-scope binding, target reference/resource claims and normalized
  `{title, description}`. It and the logical execution ID are immutable, never request input and are
  reused at acquisition, admission and every provider/recovery boundary.
- [ ] `ToolActionStore.acquire_execution` locks the approved proposal/execution row and samples fresh
  PostgreSQL `clock_timestamp()` after every potentially blocking lock. It requires database time
  before proposal expiry, then atomically commits exactly one generation-1 `AcquireWitness` whose
  tuple contains: lifecycle `executing`, revision, owner, generation, `lease_started_at`,
  `lease_expires_at`, immutable `AuthorizedExecutionBindingSnapshot`, proposal/logical execution ID,
  request fingerprint and the append-only acquisition-audit identity/digest. A read-after-commit
  witness and database restart reconstruct that entire tuple from the same transaction. In a
  concurrent public-workflow race, exactly one contender obtains `AcquireApplied`; every identified
  loser returns the typed current projection before admission and makes exactly zero gateway calls.
- [ ] PostgreSQL owns a fixed typed `DispatchAuthorityEpochVector`: global
  `reference_key_epoch` plus Workspace-scoped `workspace_dispatch_epoch`. Workspace/resource/
  execution authority and current typed capability/binding/policy selectors are Workspace-owned and
  advance the Workspace epoch in their mutation transaction. Reference-key mutation advances the
  global epoch; a mutation needing both follows global-then-Workspace order. The compiled static
  registry is immutable and supplies an exact version/digest, never a plugin epoch. Any mutable
  source outside this protocol is ineligible to authorize M4 dispatch.
- [ ] After `AcquireApplied`, private `authorize_and_admit_dispatch` locks execution, global key
  epoch and Workspace epoch in canonical order. Inside that transaction it reloads current
  Workspace/resource/execution authority and exact capability/binding/policy selectors, then fully
  re-verifies the approved `m4r1` canonical bytes, MAC, all protected claims,
  Workspace/capability/binding equality, trusted-store record/equality, key identity/status and
  expiry. It accepts no caller assertion. Deterministic post-acquisition mutation adapters
  independently corrupt/tamper the stored immutable-token test fixture, delete/replace/mismatch the
  trusted-store record, revoke/unknown/rotate the key, alter protected claims and change every
  authority/selector class while admission is blocked; lock-time reload/reverification denies each
  case with zero admission and zero gateway calls.
- [ ] Only after every admission lock and evaluation, fresh PostgreSQL `clock_timestamp()` requires
  current owner/generation plus unexpired lease and `m4r1`, then atomically persists one immutable
  `DispatchAdmissionWitness` and sanitized audit. Its complete one-row canonical tuple binds:
  admission schema/identity/digest, purpose, Workspace, proposal, logical execution ID, fingerprint,
  exact capability/binding/policy/reference identities/versions/digests, reference claims/resource
  identity digest, canonical target/parameter/complete-intent digests, both authority epochs and
  decision/witness digests, owner/generation, database issue time, lease deadline, envelope
  signing-key identity/version and canonical envelope digest.
  It also privately persists the exact canonical envelope bytes and opaque routing-snapshot digest;
  the raw routing snapshot/provider ID and envelope bytes never enter audit or public projection.
  A store-level read-after-commit oracle compares every field to the exact acquisition/proposal/
  authorization inputs as one atomic record and repeats after restart. Uniqueness is per logical
  execution regardless of generation; ambiguous commit reads back byte-identical evidence and never
  mints a second claim set.
- [ ] The opaque, domain-separated `m4-dispatch-admission-v1` envelope is persisted byte-for-byte in
  the private admission row, with retained versioned verification material for its full non-terminal
  retention. It is the only value accepted by `SupportToolGateway.create_ticket`. Immediately after
  admission commit, a deterministic barrier independently changes/revokes every current authority,
  selector/reference-key state and crosses proposal/reference/lease expiry before dispatch resumes.
  Because admission-first is an already-started write, the Module neither reauthorizes, cancels nor
  retargets it: it sends the original byte-identical envelope and material fields exactly once.
  Active-key rotation cannot invalidate or upgrade it. Mutation-first remains denied by the
  admission transaction.
- [ ] The reference-provider Adapter verifies envelope integrity and exact request equality before
  SQLite mutation, then atomically commits one externally visible ticket or one closed rejection
  with its logical-ID/fingerprint/outcome ledger in one `BEGIN IMMEDIATE` transaction. Same ID/same
  fingerprint replays; faults before commit roll back effect and ledger; faults after commit before
  acknowledgement leave one replayable outcome. A private, non-runtime
  `ReferenceProviderContractHarness` configures a test-only trusted signing Adapter to produce two
  independently valid, integrity-protected envelopes with the same logical ID and different exact
  fingerprints/intents. The first commits one effect; the second reaches the provider-owned ledger
  conflict path before target lookup/mutation and creates no second effect. Before the ledger check,
  the Adapter recomputes each canonical provider-intent fingerprint from signed claims and requires
  equality with its signed fingerprint. Tampering one envelope instead fails integrity/fingerprint
  equality before SQLite. Neither harness nor signing Adapter is reachable through HTTP/application
  composition or production dependency injection.
- [ ] Any crash, timeout, acknowledgement loss, transport uncertainty or PostgreSQL-session loss
  after durable admission and before Knora durably finalizes a closed result is receipt-possible
  `indeterminate_external_outcome`, never proof-no-write or definitive failure. Lifecycle remains
  `executing` with the same admission/logical ID/fingerprint. A read-only provider Adapter contract
  harness lookup after durable admission but before provider receipt returns typed
  `provider_outcome_not_found`; a store-level oracle proves the admission remains outstanding and
  non-terminal. This direct Adapter check is not a `ReconcileExecution` application flow and grants
  no retry. It differs from a direct, closed provider `target_not_found` rejection, which is a
  terminal business outcome. #77 performs no recovery retry or takeover.
- [ ] `record_execution_observation` and `finalize_execution` lock the execution row, sample fresh
  post-lock PostgreSQL time and require current owner/generation plus unexpired generation-1 lease.
  Parameterized success/closed-failure tests blocked across expiry return `ExecutionFenced`; expired
  observation appends no observation/audit and expired finalization makes no terminal rewrite.
  Provider truth remains independently observable. Only direct success finalizes `succeeded`; only
  `target_not_found`, `validation_rejected` or `policy_rejected` finalize `failed`. Receipt-possible
  outcomes remain executing/202; provider fingerprint conflict remains executing/409 with no retry
  authority.
- [ ] A canonical audit projection reconstructed solely from append-only PostgreSQL records after
  restart exactly matches caller/proposal/approval/execution actors, both current authorization
  decisions, exact compatibility, complete acquisition and admission witnesses, authority epochs,
  database times, provider alias, immutable intent/logical ID/fingerprint, observations and outcome.
  Raw provider IDs/routing handles, envelope bytes/MAC, keys, credentials and authority secrets are
  absent. Existing M1–M3 authorization, provenance and regression behavior remains green.

## Deterministic test seams and release evidence

- `M4-77-TC-01 — pre-acquisition and non-escalation matrix`: through the sole application/HTTP
  Interface, deny every pre-acquisition class plus principals that have only read or observation
  authority. Assert no execution/acquisition/admission/audit-start artifact and zero provider calls.
- `M4-77-TC-02 — atomic acquisition and loser isolation`: race identified public-workflow
  contenders. Read the committed `AcquireWitness` after commit and restart, compare every required
  acquisition field as one tuple, map the sole `AcquireApplied` contender to the sole possible provider call and
  prove every loser made zero gateway/provider calls. Before commit, another database session sees
  none of the tuple. Fault after each acquisition write but before commit and prove rollback leaves
  the original approved state with no execution/snapshot/audit fragment.
- `M4-77-TC-03 — post-acquisition complete current recheck`: block admission after acquisition and
  independently exercise every authority/selector mutation plus every `m4r1` MAC/claims/
  trusted-store/key failure using non-production mutation adapters. Assert lock-time denial, no
  admission and zero gateway calls.
- `M4-77-TC-04 — mutation/admission linearization and time`: race each real typed mutation Adapter
  against admission and race concurrent issuers. Mutation-first denies; admission-first stores the
  exact prior vector; one byte-identical admission/audit exists. Separately block acquisition across
  proposal expiry and admission across reference/lease expiry under skewed non-database clocks;
  post-lock `clock_timestamp()` decides each boundary.
- `M4-77-TC-05 — complete admission witness`: read the committed admission row and canonical audit,
  compare every required admission field to proposal/acquisition/authority inputs, restart PostgreSQL, rotate the
  active issuance key and reload the exact persisted envelope bytes without a second admission.
- `M4-77-TC-06 — admission-first non-cancellation`: pause after admission commit; independently
  mutate/revoke every authority/selector/key class and cross proposal/reference/lease expiry. Resume
  and prove exactly one call carries the original byte-identical envelope/intent without
  reauthorization, cancellation or retargeting.
- `M4-77-TC-07 — provider ledger contract`: use the private trusted test-signing Adapter to deliver
  same-ID/same-fingerprint replay and two valid same-ID/different-fingerprint envelopes. Prove one
  atomic effect/outcome, replay for equal fingerprint and ledger conflict for the second valid
  fingerprint after both pass integrity and self-fingerprint recomputation. Separately
  tamper/cross-bind an envelope and prove pre-SQLite integrity rejection.
- `M4-77-TC-08 — crash and provider-not-found semantics`: fault after admission before gateway,
  before SQLite commit and after SQLite commit before acknowledgement. Admission survives; provider
  has zero or one outcome. Direct provider outcome lookup in the no-receipt window returns
  `provider_outcome_not_found`, while Knora retains an outstanding non-terminal admission. Direct
  `target_not_found` remains a distinct closed failure.
- `M4-77-TC-09 — strict #77/#78 scope`: after restart, reload both `executing + no admission` and
  `executing + admission outstanding` as the two exact `ExecutionRecoverySeed` variants. A second
  Execute returns the current `ExecutionInProgress`; #77 performs no provider observation,
  admission creation/replacement, dispatch/replay, retry authorization, takeover or generation
  increment in either branch.
- `M4-77-TC-10 — generation-1 observation/finalization and result matrix`: delay each direct closed
  outcome across lease expiry and prove observation/finalization fencing; cover success, every
  closed failure, receipt-possible response, proof-no-receipt pre-admission denial and provider
  conflict through application/HTTP result mapping.
- `M4-77-TC-11 — audit/restart`: restart PostgreSQL and SQLite independently; compare the full
  canonical audit projection field-for-field with proposal/acquisition/admission/provider evidence,
  prove provider ledger independence and assert every excluded raw/secret field is absent.
- `M4-77-TC-12 — governed verification`: run focused M4.3, full pytest, Ruff, Compose and clean
  Alembic verification on the exact candidate SHA.

Durable release evidence includes contender-correlated call counts, exact acquisition/admission row
witnesses, real mutation-adapter ordering traces, PostgreSQL post-lock time samples, byte-identical
envelope digest, atomic SQLite effect/ledger rows, provider contract-harness conflict evidence,
provider-not-found versus target-not-found projections, complete audit reconstruction and the exact
candidate verification totals.

## Downstream dependency contract for Issue #78

This section constrains compatibility but is not Issue #77 acceptance behavior and creates no #78
runtime implementation or test requirement.

- #77 persists a typed read-only `ExecutionRecoverySeed` derivable from PostgreSQL with one of two
  disjoint states: `NoAdmission(logical_id, fingerprint, binding_snapshot)` or
  `AdmissionOutstanding(logical_id, fingerprint, admission_identity, envelope_digest,
  binding_snapshot)`. It contains no write authority.
- `AdmissionOutstanding` remains receipt-possible until the provider ledger has a terminal outcome;
  point-in-time `provider_outcome_not_found` cannot retire, replace or supersede it.
- #78 must observe provider outcome before takeover/retry. For `NoAdmission`, after stale takeover
  and full current Workspace/resource/execution authorization, `m4r1` side-effect verification and
  exact compatibility, #78 may create the first admission bound to its generation while retaining
  the same logical ID/fingerprint. For `AdmissionOutstanding`, any authorized retry re-dispatches
  the byte-identical existing envelope; no later generation creates another admission.
- Current read/observation authority permits outcome lookup only. Any #78 write path reruns current
  execution/write authority and exact compatibility. A delayed original and authorized replay race
  only through provider same-ID/same-fingerprint idempotency.

Actual provider-first reconciliation, stale takeover, generation 2+, retry execution and stale-owner
fencing remain wholly owned and accepted by Issue #78.

## Interface, adapters and ordering constraints

- The sole application Interface remains `WriteProposalWorkflow.handle`; `AcquireWitness`,
  `DispatchAdmissionWitness`, `ExecutionRecoverySeed`, epoch coordination, signing and fault
  barriers are hidden implementation/persistence evidence, not caller inputs or new HTTP surfaces.
- PostgreSQL and SQLite are local-substitutable Adapters exercised with real local databases for
  concurrency/restart evidence. `SupportToolGateway` is a real seam with deterministic fake and
  SQLite reference-provider Adapters. Test mutation/signing Adapters exist only in non-runtime
  contract harness composition and cannot be selected by request data.
- Admission locks execution, global key epoch, then Workspace epoch. Operations needing a suffix use
  the same order. Admission/audit commit before gateway invocation; no database lock crosses provider
  I/O. Fresh `clock_timestamp()` sampled once after all blocking locks is normative for #77 and
  refines the earlier shared `transaction_timestamp()` wording.
- Proposal expiry blocks acquisition; reference/lease expiry blocks admission; none cancels an
  admitted write. Material fields are immutable. Provider SQLite state remains authoritative and
  cannot be invented or overwritten by `ToolActionStore`.

## Blocked by

- #75 — M4.1 — Read-only ticket lookup with pre-gateway authorization
- #76 — M4.2 — Immutable write proposal and human approval boundary

## Revision provenance

- Supersedes `.agents/review/m4-issue-77-revision-v7.md` for Issue #77 delivery and is exceptional
  ticket-contract revision 6 authorized by the repository owner on 2026-08-23.
- Closes all eight external-review-v5 Major finding classes with direct, reachable oracles while
  preserving the deep application Interface: atomic acquisition tuple/loser zero calls; complete
  post-acquisition `m4r1` recheck; exact admission witness; admission-first non-cancellation;
  provider-owned valid fingerprint conflict; #77/#78 scope separation; provider-ledger not-found
  non-terminality; and read/observation-to-write non-escalation.
- Preserves the durable-admission semantics that closed the v4 Critical. #77 remains generation 1
  only, with no reconciliation/takeover implementation or plugin framework.
- The next canonical external ticket review is automatically sent under the recorded M4 transport
  authorization. No guide or implementation may begin without external `APPROVE` and zero findings.
  Final M4 code review remains forbidden until Issues #75–#79 are accepted, integrated and closed.
