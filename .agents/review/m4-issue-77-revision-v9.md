## Parent

#74 — Milestone 4 — Tools and human approval

## What to build

Deliver the approved `create_ticket` generation-1 execution path end to end behind the existing deep
`WriteProposalWorkflow.handle(ExecuteApprovedProposal, principal, actor_context)` Interface.
Execution requires current Workspace/resource authorization, `ExecutionAuthorizer` approval,
exact capability/binding/policy compatibility and complete resource-reference validity
independently of human approval.

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
  authority is denied identically and cannot escalate to a write. A durable proposal/approval
  before/after oracle distinguishes denial classes. Temporary execution-authority denial leaves the
  immutable proposal in exact `approved` state with its approval identity/version/digest unchanged.
  Every material capability, external-scope binding or policy incompatibility atomically projects
  `proposal_state=stale` plus `approval_validity=invalidated` and one of the approved closed
  `CompatibilityCheckerV1` reasons: `capability_identity|version|digest_mismatch`,
  `binding_identity|version|digest_mismatch` or `policy_identity|version|digest_mismatch`, so the
  old approval cannot later become executable. Material
  target/reference fields remain immutable: replacing the approved reference is rejected rather
  than interpreted as compatibility, and only a new proposal identity plus new authorized-human
  approval may select another target. Malformed/non-canonical, integrity/scope, trusted-store,
  key-status or expiry reference denial fails closed, leaves the exact immutable approved proposal
  and approval provenance unchanged, and never makes that approval executable with a changed,
  revoked, invalid or expired reference. A usable replacement still requires a new proposal and
  approval, but no unapproved `reference_*_mismatch` compatibility reason is invented.
- [ ] `request_fingerprint` is the stored server-computed `canonical-json-v1` digest of operation,
  exact capability, exact external-scope binding, target reference/resource claims and normalized
  `{title, description}`. It and the logical execution ID are immutable and absent from every
  writable application/HTTP command schema; unknown-field injection is rejected before proposal or
  execution state exists. A required independent oracle recomputes the exact fingerprint from
  authoritative server-normalized inputs and compares it at proposal, acquisition, admission,
  persisted envelope and provider verification boundaries. Neither identity is caller-selectable or
  caller-influenceable, and both remain byte-identical through the complete generation-1 path.
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
  authority/selector class while admission is blocked. The independent denial matrix contains a
  distinct row for non-canonical bytes, MAC corruption, protected-claim corruption,
  protected-scope corruption, trusted-store delete/replacement/claims mismatch, revoked/unknown/
  unavailable key and reference expiry. Lock-time reload/reverification denies each case with its
  exact private/application/HTTP result: non-canonical bytes use
  `ProposalNotExecutable(invalid_tool_resource_reference)` and
  `400/INVALID_TOOL_RESOURCE_REFERENCE`; every authenticated integrity/scope/store/key/expiry row
  uses `ProposalNotExecutable(resource_access_denied)` and
  `403/TOOL_RESOURCE_ACCESS_DENIED`. Each row binds independently reloaded durable proposal/
  logical-execution identities, no admission/admission-audit row and zero gateway/provider calls.
  Reference expiry is decided by fresh post-lock PostgreSQL `clock_timestamp()` and is not
  collapsed into the generic mutation race.
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
  execution regardless of generation. A deterministic commit/ack-ambiguity fixture captures the
  exact intended complete tuple and envelope bytes before the injected acknowledgement loss, then
  performs authoritative readback by logical execution ID. If PostgreSQL committed, readback must
  return the one complete tuple byte-for-byte equal to that intended witness and the Module must use
  those persisted bytes without a second insert, claim set, signing operation or envelope
  regeneration. If PostgreSQL rolled back, the complete admission tuple and linked audit must both
  be absent; #77 makes no gateway call and exposes the existing no-admission indeterminate/recovery
  seed without retrying or inventing commit state.
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
  with its logical-ID/fingerprint/outcome ledger in one `BEGIN IMMEDIATE` transaction. The provider
  contract harness independently parameterizes `target_not_found`, `validation_rejected` and
  `policy_rejected`: each commits exactly one closed ledger outcome containing the exact logical
  execution ID, request fingerprint, admission digest and rejection class, creates zero ticket/
  target effects, and reloads the identical outcome after closing and reopening the provider.
  Same ID/same fingerprint replays that exact durable rejection; faults before commit leave neither
  ledger row nor effect, while faults after commit before acknowledgement leave one replayable
  outcome. A private, non-runtime
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
  `executing` with the same admission/logical ID/fingerprint. Branch-specific provider-state oracles
  require exactly zero provider ledger rows and zero effects after both admission-before-gateway and
  pre-SQLite-commit faults. A post-SQLite-commit/pre-ack fault requires exactly one durable replayable
  provider outcome: either one ticket effect plus its success ledger row or one named closed-
  rejection ledger row plus zero ticket/target effects. Until Knora finalizes, every branch still
  exposes the exact typed `indeterminate_external_outcome` with the unchanged identities. A read-only
  provider Adapter contract-harness lookup before provider receipt returns typed
  `provider_outcome_not_found`; a store-level oracle proves the admission remains outstanding and
  non-terminal. This direct Adapter check is not a `ReconcileExecution` application flow and grants
  no retry. It differs from each direct closed provider rejection — `target_not_found`,
  `validation_rejected` or `policy_rejected` — which is a terminal business outcome with its own
  authoritative SQLite ledger row. #77 performs no recovery retry, replay or takeover.
- [ ] `record_execution_observation` and `finalize_execution` lock the execution row, sample fresh
  post-lock PostgreSQL time and require current owner/generation plus unexpired generation-1 lease.
  For delayed success and each of `target_not_found`, `validation_rejected` and `policy_rejected`,
  deterministic fixtures begin with the closed outcome committed only in SQLite, no PostgreSQL
  observation, and lifecycle `executing`. After the lease boundary, each observation and
  finalization attempt locks the row and must reject from a fresh post-lock PostgreSQL-time sample.
  A before/after PostgreSQL snapshot must remain field-for-field equal: no observation record, no
  observation/audit append, and no terminal lifecycle or outcome rewrite. The authoritative SQLite
  outcome remains readable after provider restart. Only the same operations before expiry may
  record/finalize: direct success becomes `succeeded`; only the three named closed rejections become
  `failed`. Receipt-possible outcomes remain executing/202; provider fingerprint conflict remains
  executing/409 with no retry authority.
- [ ] Public application results and decoded HTTP bodies use one closed discriminated allowlist with
  no additional recursive fields. Common fields are exactly `proposal_id`, `logical_execution_id`,
  `lifecycle` and `outcome_type`. Direct success alone may add opaque
  `external_resource_reference`; named closed rejections alone may add `rejection_code`; receipt-
  possible indeterminate, provider-fingerprint conflict and generation-1 fencing alone may add their
  typed `reason_code`. HTTP transport adds only the status code outside this projection. Required
  schema tests cover success, every closed rejection, indeterminate, conflict and fenced results and
  fail on any raw provider ID/routing handle, admission/envelope bytes or digest, MAC, request
  fingerprint, authority epoch/decision/witness, key/signing material, credential/secret or other
  private admission field.
- [ ] A canonical audit projection reconstructed solely from append-only PostgreSQL records after
  restart exactly matches caller/proposal/approval/execution actors, both current authorization
  decisions, exact compatibility, complete acquisition and admission witnesses, authority epochs,
  database times, provider alias, immutable intent/logical ID/fingerprint, observations and outcome.
  Raw provider IDs/routing handles, envelope bytes/MAC, keys, credentials and authority secrets are
  absent. Existing M1–M3 authorization, provenance and regression behavior remains green.

## Deterministic test seams and release evidence

- `M4-77-TC-01 — pre-acquisition, stale-state and non-escalation matrix`: through the sole
  application/HTTP Interface, deny every pre-acquisition class plus principals that have only read
  or observation authority. Capture proposal and approval before/after every denial. Temporary
  execution-authority denial must preserve exact `approved` state and approval identity/version/
  digest. Independently force material capability, binding and policy incompatibility; each must
  persist exact `stale`/`invalidated` state with its approved closed typed reason, permanently reject
  old-approval reuse and require a new proposal identity plus new human approval. Separately prove
  every reference syntax/integrity/scope/trusted-store/key/expiry denial fails closed while the exact
  immutable approved proposal and approval provenance remain unchanged; substituting a material
  target/reference is rejected by the immutable command/persistence Interface and a usable new
  target requires a new proposal and human approval. Every branch creates no execution/acquisition/
  admission/audit-start artifact and makes zero provider calls.
- `M4-77-TC-02 — server-owned identity, atomic acquisition and loser isolation`: at application and
  HTTP seams, prove writable command schemas contain neither logical execution ID nor request
  fingerprint and reject attempts to inject either before state creation. Independently recompute
  the expected `canonical-json-v1` fingerprint from authoritative server-normalized operation,
  capability, scope, protected reference/resource and `{title, description}` inputs; compare it and
  the server-minted logical ID byte-for-byte across proposal, `AcquireWitness`, admission, persisted
  envelope and provider verification evidence. Then race identified public-workflow contenders.
  Read the committed `AcquireWitness` after commit and restart, compare every required acquisition
  field as one tuple, map the sole `AcquireApplied` contender to the sole possible provider call and
  prove every loser made zero gateway/provider calls. Before commit, another database session sees
  none of the tuple. Fault after each acquisition write but before commit and prove rollback leaves
  the original approved state with no execution/snapshot/audit fragment or caller-influenced ID.
- `M4-77-TC-03 — post-acquisition complete current recheck`: block admission after acquisition and
  independently exercise every authority/selector mutation plus distinct `m4r1` rows for
  non-canonical bytes, MAC corruption, protected-claim corruption, protected-scope corruption,
  trusted-store delete/replacement/claims mismatch, revoked/unknown/unavailable key and reference
  expiry using non-production mutation adapters. For every row compare the exact private
  `ProposalNotExecutable` reason, application projection and decoded HTTP status/error envelope to
  the independent closed mapping above, bind expected IDs to pre-invocation durable proposal/
  logical-execution identities and assert no admission/admission-audit row plus zero gateway/
  provider calls.
- `M4-77-TC-04 — mutation/admission linearization and time`: race each real typed mutation Adapter
  against admission and race concurrent issuers. Mutation-first denies; admission-first stores the
  exact prior vector; one byte-identical admission/audit exists. Separately block acquisition across
  proposal expiry and admission across reference/lease expiry under skewed non-database clocks;
  post-lock `clock_timestamp()` decides each boundary. The admission-side reference-expiry branch
  must produce the exact TC-03 reference-expiry result and zero-activity evidence rather than only a
  generic mutation-first denial.
- `M4-77-TC-05 — complete admission witness and ambiguous-commit readback`: read the committed
  admission row and canonical audit, compare every required admission field to proposal/
  acquisition/authority inputs, including the independently recomputed server-owned fingerprint and
  immutable logical ID, restart PostgreSQL, rotate the active issuance key and reload the exact
  persisted envelope bytes without a second admission. At the PostgreSQL commit/ack fault seam,
  capture the intended complete tuple/bytes and force both committed-but-unacknowledged and rolled-
  back outcomes. Authoritative readback must return exactly the intended committed tuple and reuse
  its bytes with no second insert/sign/regeneration, or return complete absence with no audit,
  gateway call or #77 retry; no partial or third state is valid.
- `M4-77-TC-06 — admission-first non-cancellation`: pause after admission commit; independently
  mutate/revoke every authority/selector/key class and cross proposal/reference/lease expiry. Resume
  and prove exactly one call carries the original byte-identical envelope/intent without
  reauthorization, cancellation or retargeting.
- `M4-77-TC-07 — provider ledger contract`: use the private trusted test-signing Adapter to deliver
  same-ID/same-fingerprint replay and two valid same-ID/different-fingerprint envelopes. Prove one
  atomic effect/outcome, replay for equal fingerprint and ledger conflict for the second valid
  fingerprint after both pass integrity and provider recomputation from signed authoritative intent;
  the normal generation-1 envelope value must equal the independent server-side recomputation from
  TC-02. Separately
  tamper/cross-bind an envelope and prove pre-SQLite integrity rejection. Parameterize all three
  closed rejections: each one transaction persists exactly one ledger outcome with the exact
  logical ID/fingerprint/admission digest, creates zero target/ticket effects, survives provider
  restart byte-for-byte and replays identically; every injected pre-commit fault leaves neither row
  nor effect.
- `M4-77-TC-08 — crash and provider-not-found semantics`: fault after admission before gateway,
  before SQLite commit and after SQLite commit before acknowledgement as three named branches. For
  the first two, assert exactly zero provider ledger rows and zero ticket/target effects. For the
  committed-before-ack branch, assert exactly one durable replayable ledger outcome and exactly one
  success effect or one named closed rejection with zero effects, unchanged after provider restart.
  In every branch not yet Knora-finalized, assert lifecycle `executing`, the same admission/logical
  ID/fingerprint and exact `indeterminate_external_outcome`; no branch grants #77 retry/replay/
  takeover authority. Direct provider lookup in either no-receipt branch returns
  `provider_outcome_not_found`, while direct `target_not_found`, `validation_rejected` and
  `policy_rejected` remain distinct closed ledger outcomes after provider restart.
- `M4-77-TC-09 — strict #77/#78 scope`: after restart, reload both `executing + no admission` and
  `executing + admission outstanding` as the two exact `ExecutionRecoverySeed` variants. A second
  Execute returns the current `ExecutionInProgress`; #77 performs no provider observation,
  admission creation/replacement, dispatch/replay, retry authorization, takeover or generation
  increment in either branch.
- `M4-77-TC-10 — generation-1 observation/finalization and result matrix`: separately delay success,
  `target_not_found`, `validation_rejected` and `policy_rejected` after the SQLite commit but before
  any PostgreSQL observation. Cross lease expiry, then invoke observation and finalization under
  deterministic lock barriers. Each must use fresh post-lock PostgreSQL time, return
  `ExecutionFenced`, and leave before/after PostgreSQL state identical: no observation row, no
  observation/audit append and no terminal lifecycle/outcome rewrite. Read the still-authoritative
  outcome from SQLite after provider restart. Also cover the corresponding before-expiry terminal
  mappings, receipt-possible response, proof-no-receipt pre-admission denial and provider conflict
  through application/HTTP result mapping. For success, each closed rejection, indeterminate,
  conflict and fenced result, compare the complete application projection and decoded HTTP body to
  the exact discriminated allowlist and fail on every extra key or recursively nested private field,
  including raw provider/routing, admission/envelope/MAC/fingerprint, authority, key, credential and
  secret material. Exercise every TC-03 post-acquisition denial through the same independent
  application/HTTP matrix. In particular, link protected-scope corruption and reference expiry to
  their exact TC-03/TC-04 evidence and prove after PostgreSQL restart that each remains generation-1
  `executing` with unchanged proposal/logical-execution/fingerprint/acquisition identities, no
  admission, no terminal outcome/finalization row, no terminal-audit append and zero provider call.
- `M4-77-TC-11 — audit/restart`: restart PostgreSQL and SQLite independently; compare the full
  canonical audit projection field-for-field with proposal/acquisition/admission/provider evidence,
  prove provider ledger independence and assert every excluded raw/secret field is absent.
- `M4-77-TC-12 — governed verification`: run focused M4.3, full pytest, Ruff, Compose and clean
  Alembic verification on the exact candidate SHA.

Durable release evidence includes contender-correlated call counts, exact acquisition/admission row
witnesses, independent canonical fingerprint recomputation and non-caller-influence proof, durable
temporary-denial/reference-denial approved provenance versus capability/binding/policy material-
stale proposal snapshots, real mutation-adapter ordering traces,
PostgreSQL post-lock time samples, byte-identical envelope digest, both branches of the admission
commit/ack ambiguity fixture, three branch-specific post-admission provider/Knora state records,
atomic SQLite effect/ledger rows, provider contract-harness conflict evidence, separate restart-
stable evidence for all three closed rejection classes, provider-not-found versus closed-rejection
projections, the complete post-acquisition reference-denial matrix with protected-scope and
reference-expiry rows, post-restart non-finalization snapshots, complete expiry-fenced before/after
PostgreSQL snapshots, exact public projection allowlist/forbidden-field matrices, complete audit
reconstruction and the exact candidate verification totals.

`M4-77-EV-04` is the required provider-owned release-evidence set and binds separate named records
for `target_not_found`, `validation_rejected` and `policy_rejected`. Each record contains the exact
logical execution ID/fingerprint/admission digest, the single closed SQLite ledger outcome, zero
ticket/target-effect count, pre-commit rollback observation, equal-fingerprint replay and the same
authoritative outcome after a provider restart.

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

- Supersedes the revision-8 artifact at commit
  `478992d3a18ae85832cb3c355c772a8cea08a03c` for Issue #77 delivery and is exceptional
  ticket-contract correction 9 authorized by the repository owner's active multi-session
  continuation instruction on 2026-08-23.
- Preserves all prior corrections and closes all four external-review-v7 Major finding classes with
  direct required oracles: branch-specific post-admission provider/Knora state; independently
  recomputed server-owned logical-ID/fingerprint provenance and caller non-influence; temporary-
  authority approved preservation versus durable material-incompatibility stale invalidation; and
  exact allowlisted/forbidden-field public projections for every result variant.
- Preserves the durable-admission semantics that closed the v4 Critical. #77 remains generation 1
  only, with no reconciliation/takeover implementation or plugin framework.
- Reconciles guide-v6 external-review finding
  `material_reference_mismatch_stale_invalidation_not_exercised` with the authoritative M4 Design:
  the existing `CompatibilityCheckerV1` Interface and its capability/binding/policy reason taxonomy
  remain closed; immutable target/reference replacement creates a new proposal, while reference
  validity denial fails closed without inventing a new compatibility reason. It also closes
  `post_acquisition_reference_denial_matrix_incomplete` by naming protected-scope and reference-
  expiry rows plus their complete application/HTTP, zero-activity and restart-stable oracles.
- The next canonical external ticket review requires the recorded fresh action-time browser
  transport confirmation after its exact subject, packet digest and request ID exist. No guide or
  implementation may begin without external `APPROVE` and zero findings. Final M4 code review
  remains forbidden until Issues #75–#79 are accepted, integrated and closed.
