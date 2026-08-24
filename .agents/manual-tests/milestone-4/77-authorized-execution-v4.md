# Manual Test Guide: M4.3 authorized execution v4

## Metadata

- Feature: Milestone 4 — Tools and human approval
- Slice: Issue #77 — authorized `create_ticket` execution
- Authoritative specification: GitHub Issue #77 and
  `.agents/review/m4-issue-77-revision-v8.md` at contract commit
  `478992d3a18ae85832cb3c355c772a8cea08a03c`
- Ticket external review: `.agents/review/m4-issue-77-ticket-external-review-v8.json`, `APPROVE`
  with zero findings against subject `fc4c9e7431f19da31bf99e4be4b72c09213c0a75`
- Guide revision: `m4-77-authorized-execution-v4`
- Test-case source: `.agents/review/m4-issue-77-test-cases-v4.json`
- Prior guide review: `.agents/review/m4-issue-77-guide-external-review-v3.json`,
  `REQUEST_CHANGES` with 1 Major finding and no Critical or Minor findings; it confirmed the exact
  denial, provider cross-binding and production test-adapter-isolation corrections closed
- External guide review evidence: pending `.agents/review/m4-issue-77-guide-external-review-v4.json`
- Human approval evidence: pending `.agents/review/m4-issue-77-guide-approval-v4.json`
- Lock rule: this exact guide digest becomes immutable only after external `APPROVE` and explicit
  repository-owner approval; implementation remains blocked until both records exist

## Prerequisites

- Execute only on the exact candidate SHA recorded in the Evaluation and from the clean Issue #77
  worktree `D:\Developer\Projects\knora-agent-worktree\issue-77-m4.3`.
- Resolve Python as `D:\Developer\Projects\knora-agent\.venv\Scripts\python.exe` and set:
  `$env:KNORA_DATABASE_URL = "postgresql+psycopg://knora:knora@127.0.0.1:5432/knora"` and
  `$env:PYTHONPATH = "D:\Developer\Projects\knora-agent-worktree\issue-77-m4.3;D:\Developer\Projects\knora-agent-worktree\issue-77-m4.3\backend\src"`.
- Docker project `m4-integration` supplies PostgreSQL. Run PostgreSQL suites serially. The exact
  clean-database command is `docker compose -p m4-integration exec -T postgres psql -U knora -d
  postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE
  datname='knora' AND pid <> pg_backend_pid()" -c "DROP DATABASE IF EXISTS knora" -c "CREATE
  DATABASE knora OWNER knora"`.
- Use a unique temporary SQLite reference-provider file per run. Its external state/idempotency
  ledger must survive provider Adapter recreation and remain independent from PostgreSQL
  `ToolActionStore`; never reuse a developer's non-test provider database.
- Seed two Workspaces, approved proposals and authenticated principals with independent read,
  observation and execution grants. Use authorized human approval actors, current and revoked
  execution authority, exact and mismatched capability/binding/policy/reference versions, a
  non-default proposal lifetime, and PostgreSQL-controlled expiry boundaries.
- Use test-only ephemeral `m4r1` and dispatch-envelope signing keys, a trusted reference store and
  explicit active, retiring, revoked, unknown, unavailable and active-to-retiring/
  retiring-to-revoked transition fixtures. Each fixture exposes only sanitized key ID/version,
  lifecycle and typed epoch; raw key/MAC/envelope bytes, credentials and raw provider routing
  identifiers never enter public or audit evidence.
- Install explicit per-contender counting `SupportToolGateway`, target-lookup, SQLite-ledger and
  provider-effect sentinels. A zero-call assertion is valid only when the exact sentinel identity
  and per-row/per-contender count appear in release evidence.
- Compose deterministic non-runtime barriers/fault adapters for acquisition writes, admission
  locks, PostgreSQL commit acknowledgement, post-admission/pre-gateway, SQLite pre-commit,
  SQLite-commit/pre-ack, provider observation and generation-1 lease expiry. Test mutation and
  trusted-signing adapters are never registered with production application/HTTP dependency
  injection; TC-12 inventories and probes every production resolution surface to prove this.
- The focused release command is executed from `backend` and is exactly:
  `& $python -m pytest test/tools/test_execution_workflow.py test/tools/test_execution_postgres.py
  test/tools/test_reference_provider.py test/adapters/http/test_tools.py
  ../evals/test/test_m4_77_release_acceptance.py -q`.
- The authoritative full-suite command is executed from `backend` and is exactly
  `& $python -m pytest test ../evals/test -q`. Record exact invocations, exits and totals. Also run
  `& $python -m ruff check .` from the repository root and `docker compose config --quiet`.
- Before focused/full suites, recreate the database and run
  `Push-Location backend; & $python -m alembic upgrade head; & $python -m alembic current;
  Pop-Location`. Recreate/migrate once more after the full suite to prove clean migration.
- The deterministic release harness writes one sanitized
  `.agents/review/m4-issue-77-release-evidence-v1.json` bound to the exact subject SHA, PostgreSQL
  instance/revision, SQLite file identity/schema, Test Case IDs and sentinel/fault-adapter
  identities. It contains no raw prompt, command output, key/MAC/envelope bytes, credentials,
  authority secrets or raw provider IDs/routing handles.
- Issue #77 is generation 1 only. `ReconcileExecution`, provider-first application observation,
  write retry/replay authorization, stale takeover and generation 2+ remain absent; direct read-only
  provider contract observation in TC-08 is not reconciliation.
- The production composition exposes only the closed static typed capability registry. The release
  harness compares its exact capability ID/version/operation projection to the locked allowlist and
  probes runtime capability/provider registration, discovery and plugin loading without relying on
  source-file or file-name inspection.
- TC-03 loads its expected denial matrix from a test fixture that imports no production admission
  result type or mapper. TC-10 loads both immutable matrices below from a release-harness fixture
  that imports or calls no production result class, enum, serializer or HTTP mapper.
- The candidate Evaluation uses a unique run ID, this guide revision/digest, exact subject SHA,
  environment revision, all twelve case results/evidence references, overall verdict and
  `human_approval: pending`. Append through `record_evaluation.py`; after explicit result approval,
  append a separate approved record and never rewrite history.

## Immutable M4.3 public-result and denial matrices

These independently sourced tables exhaust every post-acquisition or repeated-execute result that
Issue #77 may publish. Pre-acquisition authentication, authorization, stale, expiry and validation
failures remain the existing closed `{"error":{"code":"..."}}` envelope tested by TC-01.
Post-acquisition denial rows use the exact `ProposalNotExecutable` application projection and HTTP
error mapping in the second table. Every application projection and HTTP body has only the fields
declared for its row; all other fields at every depth are forbidden.

### Execution outcome rows

| Application result / row | `outcome_type` | `lifecycle` | HTTP | Sole variant field and allowed value/domain |
| --- | --- | --- | ---: | --- |
| `ExecutionSucceeded` | `execution_succeeded` | `succeeded` | 200 | `external_resource_reference`: non-empty opaque integrity-protected reference minted by the trusted provider-to-reference boundary; never a raw provider ID |
| `ExecutionFailed(target_not_found)` | `execution_failed` | `failed` | 502 | `rejection_code`: exactly `target_not_found` |
| `ExecutionFailed(validation_rejected)` | `execution_failed` | `failed` | 502 | `rejection_code`: exactly `validation_rejected` |
| `ExecutionFailed(policy_rejected)` | `execution_failed` | `failed` | 502 | `rejection_code`: exactly `policy_rejected` |
| `ExecutionIndeterminate` | `execution_indeterminate` | `executing` | 202 | `reason_code`: exactly `indeterminate_external_outcome` |
| `ExecutionInProgress` — current execution | `execution_in_progress` | `executing` | 409 | `reason_code`: exactly `execution_in_progress` |
| `ExecutionInProgress` — provider conflict | `execution_in_progress` | `executing` | 409 | `reason_code`: exactly `provider_idempotency_conflict` |
| `ExecutionFenced` | `execution_fenced` | `executing` | 409 | `reason_code`: exactly `execution_fenced` |

Each execution-outcome row has exactly `proposal_id`, `logical_execution_id`, `lifecycle`,
`outcome_type` and the named variant field. Both IDs are canonical lowercase RFC 4122 UUID
strings read from durable proposal/execution identity. The decoded HTTP body is field-for-field
equal to the application projection. The status code is transport metadata and is absent from the
body.

### Post-acquisition denial rows

Every row below has application result `ProposalNotExecutable`. Its application projection has
exactly `proposal_id`, `logical_execution_id`, `lifecycle=executing`,
`outcome_type=proposal_not_executable` and the named `reason_code`. Its HTTP body has exactly
`{"error":{"code":"<PUBLIC_CODE>"}}`: the outer object has only `error`, and the nested
object has only `code`. The status code is absent from both bodies.

| TC-03 post-acquisition row | Application `reason_code` | HTTP | Exact public `error.code` |
| --- | --- | ---: | --- |
| Workspace authority denied | `workspace_access_denied` | 403 | `WORKSPACE_ACCESS_DENIED` |
| resource authority denied | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| execution authority denied | `execution_not_authorized` | 403 | `TOOL_EXECUTION_NOT_AUTHORIZED` |
| capability identity mismatch | `capability_identity_mismatch` | 409 | `TOOL_PROPOSAL_STALE` |
| capability version mismatch | `capability_version_mismatch` | 409 | `TOOL_PROPOSAL_STALE` |
| capability digest mismatch | `capability_digest_mismatch` | 409 | `TOOL_PROPOSAL_STALE` |
| binding identity mismatch | `binding_identity_mismatch` | 409 | `TOOL_PROPOSAL_STALE` |
| binding version mismatch | `binding_version_mismatch` | 409 | `TOOL_PROPOSAL_STALE` |
| binding digest mismatch | `binding_digest_mismatch` | 409 | `TOOL_PROPOSAL_STALE` |
| policy identity mismatch | `policy_identity_mismatch` | 409 | `TOOL_PROPOSAL_STALE` |
| policy version mismatch | `policy_version_mismatch` | 409 | `TOOL_PROPOSAL_STALE` |
| policy digest mismatch | `policy_digest_mismatch` | 409 | `TOOL_PROPOSAL_STALE` |
| non-canonical reference bytes | `invalid_tool_resource_reference` | 400 | `INVALID_TOOL_RESOURCE_REFERENCE` |
| MAC corruption | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| protected-claim corruption | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| trusted-store record deleted | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| trusted-store record replaced | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| trusted-store claims mismatch | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| key revoked | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| key unknown | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| trusted key store unavailable | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| retiring-to-revoked mutation-first | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |

The compatible control, active exact, retiring exact and active-to-retiring mutation-first rows are
admission-success controls, not denial rows. Admission-first transition rows use the prior bound
state and continue through the applicable execution-outcome row.

## Locked Test Cases

### M4-77-TC-01: Pre-acquisition authorization, stale state and non-escalation

- Purpose: prove human approval never grants execution authority and old approval cannot silently
  become executable after a material incompatibility.
- Steps:
  1. Through the sole application/HTTP workflow, exercise missing Workspace/resource/execution
     authority and principals with only read, only observation or both limited grants.
  2. Capture proposal and approval before/after temporary execution-authority denial.
  3. Independently force capability, external-scope binding, policy and reference mismatch; reload
     and attempt to reuse each old approval.
- Expected results:
  - Every denial creates no execution/acquisition/admission/audit-start artifact and zero provider
    calls.
  - Temporary authority denial preserves exact `approved` state and approval identity/version/digest.
  - Each material mismatch persists `proposal_state=stale`, `approval_validity=invalidated` and its
    typed reason; later restoration cannot reuse it, and only a new proposal plus authorized-human
    approval is executable.
- Evidence to capture: named denial/mismatch matrix, before/after durable projections, row counts,
  per-contender sentinel identity/count and old-approval retry result.

### M4-77-TC-02: Server-owned identity, atomic acquisition and loser isolation

- Purpose: prove callers cannot influence logical execution identity/fingerprint and concurrent
  workflows cannot hide loser provider calls behind idempotency.
- Steps:
  1. Inject logical execution ID and request fingerprint through writable application/HTTP inputs.
  2. Independently normalize the authoritative operation/capability/scope/reference/resource/
     `{title, description}` intent, recompute `canonical-json-v1` and compare proposal,
     `AcquireWitness`, admission, persisted envelope and provider values.
  3. Race identified contenders, inspect another PostgreSQL session before commit, inject a fault
     after each acquisition write before commit, then restart and reload.
- Expected results:
  - Both injected fields are absent from writable schemas or rejected before state creation.
  - Server-minted logical ID and independently recomputed fingerprint are byte-identical and
    immutable through every generation-1 boundary.
  - Exactly one contender receives `AcquireApplied` and is the only possible gateway caller; each
    loser makes zero calls. Pre-commit observers see no tuple, rollback leaves approved with no
    fragment, and restart reconstructs the complete tuple.
- Evidence to capture: input rejection matrix, canonical normalized input/digest record, complete
  acquisition tuple, contender/result/call correlation, rollback and restart snapshots.

### M4-77-TC-03: Complete current authorization and m4r1 recheck after acquisition

- Purpose: close every acquisition-to-admission TOCTOU window and lock every denial's application
  and HTTP projection.
- Steps:
  1. Acquire and block immediately before private admission authorization.
  2. Run every row in the post-acquisition denial matrix: Workspace/resource/execution authority;
     capability/binding/policy identity, version and digest; canonical bytes, MAC and protected
     claims; trusted-store delete, replacement and claims mismatch; revoked, unknown and unavailable
     key state; and retiring-to-revoked mutation-first.
  3. Run compatible, active exact, retiring exact and active-to-retiring controls plus the
     admission-first transition rows. Capture post-lock key ID/version and typed epoch for each row.
  4. Compare private admission result, application projection and decoded HTTP body with the
     independently loaded exact row before inspecting admission/audit and gateway/provider sentinels.
- Expected results:
  - Every denial happens after post-lock reload. It returns the exact
    `ProposalNotExecutable` projection and exact HTTP status/error envelope from the immutable
    denial matrix. Application and HTTP shapes contain no field outside that row.
  - Every denial persists zero admission rows, zero admission-audit rows and makes zero gateway and
    provider calls for that row's named sentinels.
  - Every capability/binding/policy mismatch also persists its matching typed stale/invalidation
    reason; authority/reference/key denials do not silently become a compatibility reason.
  - Compatible, active exact and retiring exact controls admit exactly once when all other facts are
    compatible. Admission binds post-lock key ID/version and epoch and makes exactly one provider
    call.
  - Active-to-retiring mutation-first remains admissible under the retiring key.
    Retiring-to-revoked mutation-first uses the exact denial row. Admission-first binds the prior key
    state under the TC-04 epoch rule.
  - Only sanitized evidence is appended. No caller assertion or raw key/MAC/envelope is accepted.
- Evidence to capture: independently sourced denial/result/HTTP matrix and its digest, compatible and
  transition controls, post-lock key ID/version and epoch, lock/reload order, per-row admission/
  audit/gateway/provider counts, application/HTTP field-shape comparison and sanitized-evidence scan.

### M4-77-TC-04: Mutation/admission linearization and PostgreSQL time

- Purpose: prove canonical lock order, one admission and fresh database-time expiry decisions.
- Steps:
  1. Race every real typed epoch mutation against admission and race same-generation issuers.
  2. Block acquisition across proposal expiry under skewed application clocks.
  3. Block admission across reference and lease expiry under the same skew.
- Expected results:
  - Mutation-first denies; admission-first stores the exact prior global/Workspace epoch vector.
  - One byte-identical admission/audit exists per logical execution.
  - Fresh post-lock PostgreSQL `clock_timestamp()` decides each boundary; transaction-start or
    application clocks cannot revive an expired action.
- Evidence to capture: canonical lock/epoch traces, issuer results, admission uniqueness, post-lock
  time samples and skew comparison.

### M4-77-TC-05: Complete admission witness and commit/ack ambiguity

- Purpose: prevent partial admission, invented commit state or regenerated dispatch envelopes.
- Steps:
  1. Capture the intended complete admission tuple/envelope before commit and compare each persisted
     row/audit field to proposal, acquisition and authorization inputs.
  2. Restart PostgreSQL, rotate the active issuance key and reload exact stored envelope bytes.
  3. Force committed-but-unacknowledged and rolled-back outcomes at the PostgreSQL commit/ack seam,
     then perform authoritative readback by logical execution ID.
- Expected results:
  - Committed readback equals the intended tuple and envelope byte-for-byte; there is no second
    insert, claim set, signing operation or regeneration.
  - Rolled-back readback has complete admission/audit absence, zero gateway calls and no #77 retry.
  - No partial or third state exists.
- Evidence to capture: intended/persisted field table, envelope digest before/after restart, both
  ambiguity branches and insert/sign/gateway counters.

### M4-77-TC-06: Admission-first non-cancellation and exact dispatch

- Purpose: prove an already-started provider write is not reauthorized, canceled or retargeted.
- Steps:
  1. Pause immediately after durable admission.
  2. Independently revoke/change every authority, selector and current key, rotate active signing
     material and cross proposal/reference/lease expiry.
  3. Resume dispatch and compare gateway input with persisted admission.
- Expected results:
  - Exactly one gateway call carries the original byte-identical envelope and intent.
  - No current fact is reread to cancel, replace, upgrade or retarget dispatch.
  - Later lease expiry may fence only Knora observation/finalization.
- Evidence to capture: original/sent envelope digest, mutation/expiry matrix, gateway input and exact
  call count.

### M4-77-TC-07: Provider-owned effect, rejection, cross-binding and idempotency ledger

- Purpose: prove real external-side-effect and defensive scope semantics at the independent SQLite
  provider boundary.
- Steps:
  1. Through the private harness, deliver same-ID/same-fingerprint replay and two independently valid
     same-ID/different-fingerprint envelopes.
  2. Separately deliver an ordinarily tampered envelope and an integrity-valid envelope bound to a
     different Workspace/external scope than the selected provider target.
  3. Capture ordered integrity, binding, target-lookup, SQLite-ledger and effect sentinels for both
     negative rows.
  4. Parameterize success, `target_not_found`, `validation_rejected` and `policy_rejected`; inject
     pre-commit and committed-before-ack faults, reopen SQLite and replay equal fingerprint.
- Expected results:
  - Equal fingerprint replays one effect/outcome. Both valid unequal fingerprints pass integrity
    and recomputation, then the second conflicts before target lookup/mutation with no second effect.
  - Ordinary tampering rejects before SQLite mutation.
  - Cross-binding returns exact typed `provider_scope_denied` after integrity verification but
    before target lookup and before any SQLite idempotency-ledger or effect mutation. Target lookup,
    ledger-row and target/ticket-effect counts are each exactly zero; the result is sanitized and
    includes no target or routing detail.
  - Each closed rejection atomically owns one exact logical-ID/fingerprint/admission-digest ledger
    row, zero ticket/target effects, pre-commit rollback absence and restart-stable replay.
- Evidence to capture: SQLite effect/ledger rows before/after restart, fingerprint recomputation,
  separate tamper trace, cross-binding verification-order trace and zero counters, conflict trace
  and one record per closed rejection.

### M4-77-TC-08: Branch-specific crash and provider-not-found semantics

- Purpose: prevent false proof-no-write and unsafe retry authority after durable admission.
- Steps:
  1. Fault after admission before gateway, before SQLite commit and after SQLite commit before
     acknowledgement as three separately named branches.
  2. Inspect SQLite ledger/effect counts before and after provider restart; parameterize success and
     every closed rejection in the committed branch.
  3. Inspect Knora lifecycle/identity/result and invoke only the read-only provider contract observer
     in no-receipt branches.
- Expected results:
  - Admission-before-gateway and pre-SQLite-commit each have exactly zero provider rows/effects.
  - Committed-before-ack has exactly one durable replayable success row/effect or one named closed-
    rejection row with zero effects.
  - Every branch not yet Knora-finalized remains `executing` with unchanged admission/logical ID/
    fingerprint and exact `indeterminate_external_outcome`. No #77 retry/replay/takeover authority
    appears; no-receipt observation is `provider_outcome_not_found`.
- Evidence to capture: three branch records, provider rows/effects before/after restart, Knora
  projection and absence-of-recovery counters.

### M4-77-TC-09: Strict Issue #77/#78 recovery boundary

- Purpose: prove #77 stores recovery inputs without implementing reconciliation.
- Steps:
  1. Restart and reload `executing + NoAdmission` and `executing + AdmissionOutstanding` seeds.
  2. Call `ExecuteApprovedProposal` again for each seed.
  3. Inspect provider observer/dispatcher, admissions, generation and recovery-authority counters.
- Expected results:
  - Both calls return current `ExecutionInProgress` and preserve the exact seed.
  - #77 performs no provider observation, first/replacement admission, dispatch/replay, retry
    authorization, takeover or generation increment.
  - Public application/HTTP output matches the corresponding `execution_in_progress` row in the
    immutable result matrix.
- Evidence to capture: seed projection/reload table, typed repeated-execute result, public matrix
  comparison and every zero behavior counter.

### M4-77-TC-10: Generation-1 fencing and complete public-result/denial matrices

- Purpose: prevent expired-owner finalization, implementation-derived public expectations and
  private admission leakage.
- Steps:
  1. Start with provider-only success and each closed rejection, no PostgreSQL observation and
     lifecycle `executing`; cross lease expiry. Immediately before blocked finalization capture the
     execution row, ordered observation/audit IDs and counts, stable field/digest projection and
     owner-correlated PostgreSQL write trace.
  2. Invoke observation and finalization as expired generation-1 owner under lock barriers, then
     recapture the same projections and correlated writes.
  3. Repeat before expiry for success and all three closed rejections. Exercise indeterminate,
     current execution-in-progress, provider-idempotency conflict and fenced rows.
  4. Exercise every TC-03 post-acquisition denial row through application and HTTP seams.
  5. Load both immutable expected matrices without importing/calling production result classes,
     enums, serializers or HTTP mappers. For every row compare exact application result,
     `outcome_type`, lifecycle, HTTP status, complete application/HTTP key sets and value domains.
     Recursively inject every forbidden field into both projection families.
- Expected results:
  - Each expired operation uses fresh post-lock PostgreSQL time and returns `ExecutionFenced`.
    Execution row is unchanged; no observation row, audit row or other PostgreSQL write is appended
    by expired owner; ordered IDs/counts and stable row-set digest remain exact. Provider truth
    remains readable after restart.
  - Every execution-outcome application result and decoded HTTP body is field-for-field equal to one
    exact execution-outcome matrix row.
  - Every post-acquisition denial returns exact `ProposalNotExecutable` fields and exact closed HTTP
    error status/body from one denial-matrix row. No TC-03 denial is unclassified.
  - The expected matrices come from the independent fixture and cover every named row exactly once.
  - No additional recursive field, raw provider/routing, admission/envelope/MAC/fingerprint,
    authority, key/signing, credential, secret or other private material is accepted or emitted.
- Evidence to capture: post-expiry execution-row snapshot, ordered observation/audit identities and
  counts, stable PostgreSQL row-set digest, owner-correlated zero-write trace, provider restart
  record, independent matrix source/digest, complete per-row application/HTTP comparisons and
  forbidden-field failures.

### M4-77-TC-11: Independent restart audit reconstruction

- Purpose: prove durable provenance without coupling PostgreSQL audit to provider state or secrets.
- Steps:
  1. Create direct success/failure, indeterminate, conflict and no-admission evidence.
  2. Restart PostgreSQL and SQLite independently; reconstruct audit solely from append-only
     PostgreSQL rows and read provider truth separately.
  3. Compare every required audit field and scan audit/public evidence for every forbidden value.
- Expected results:
  - Audit exactly reconstructs all actors, both current authorization decisions, compatibility,
    acquisition/admission witnesses, epochs, database times, provider alias, immutable intent/
    identity/fingerprint, observations and outcome.
  - SQLite remains independently authoritative.
  - Raw provider IDs/routing, envelope/MAC, keys, credentials and authority secrets are absent.
- Evidence to capture: full field-by-field audit table, ordered records, independent SQLite row and
  forbidden-field scan.

### M4-77-TC-12: Governed production isolation, regression and migration verification

- Purpose: prove the exact candidate and release evidence satisfy #77 without exposing test-only
  trusted adapters or regressing M1–M3.
- Steps:
  1. Instantiate every production application and HTTP composition entrypoint, project the registry
     through its public typed resolver/descriptors and compare exact ordered capability ID/version/
     operation entries with the locked closed allowlist.
  2. Inventory every production application factory/dependency provider and HTTP dependency,
     override and resolution surface. At each surface attempt resolution by dependency role and by
     concrete type for every test-only `m4r1` signer, dispatch-envelope signer, trusted-store
     mutator, Workspace/resource/execution-authority mutator, capability/binding/policy selector
     mutator, reference-key mutator and provider-contract-harness signer/mutator.
  3. Treat any returned callable/object as failure. If an object is unexpectedly returned, attempt
     invocation only through the production surface and record registry, PostgreSQL, SQLite-ledger,
     target-lookup, provider-call and effect state before/after.
  4. Probe every production application/HTTP composition surface for runtime capability/provider
     registration, capability/provider discovery and plugin loading. Structural/typed runtime
     probes are required; source-text or file-name assertions are invalid.
  5. Record subject SHA/clean status, recreate/migrate PostgreSQL and run the exact focused command.
     Recreate/migrate PostgreSQL, run full suite serially, Ruff and Compose; recreate/migrate once
     more, record Alembic head, validate release evidence covers TC-01 through TC-11 and inspect
     final clean status.
- Expected results:
  - Production registry exactly equals the closed typed allowlist and exposes no runtime
    registration, discovery or plugin-loading operation.
  - Every test-only signer/mutator resolution probe returns no object and no callable at every
    production application/HTTP surface; typed unsupported-dependency results are allowed only when
    they come from that production composition surface.
  - All probes make zero registry/dependency, PostgreSQL, SQLite-ledger, target-lookup, provider-call
    or effect changes. There is no production path capable of invoking a test-only signer/mutator.
  - Every verification command exits 0, focused cases and M1–M3 regressions pass, PostgreSQL reaches
    the single current Alembic head, sanitized release evidence is exact-candidate/environment-bound
    and the candidate worktree is clean.
- Evidence to capture: production registry projection/allowlist, complete DI-surface inventory,
  test-only adapter-type allowlist, per-surface resolution/invocation matrix, runtime-boundary probe
  results, before/after registry/dependency/database/provider counters, exact commands/exits/totals,
  release-evidence digest, migration head, subject SHA and clean status.

Observations belong to
`.agents/manual-tests/milestone-4/77-authorized-execution-v4.evaluations.jsonl`. Append a candidate
record with `human_approval: pending`; after explicit result approval append a separate approved
record. This guide becomes immutable only after its externally reviewed digest receives explicit
human lock approval.

