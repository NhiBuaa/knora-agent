# Manual Test Guide: M4.3 authorized execution v7

## Metadata

- Feature: Milestone 4 — Tools and human approval
- Slice: Issue #77 — authorized `create_ticket` execution
- Authoritative specification: GitHub Issue #77 and
  `.agents/review/m4-issue-77-revision-v9.md` at contract commit
  `67858a056d14319525ca7bf7152e08f10bd7c012`
- Ticket external review: `.agents/review/m4-issue-77-ticket-external-review-v10.json`, `APPROVE`
  with zero findings against packet correction subject `d4064c4d8afcc9c552d01489f3ae400063382049`
  (ticket contract digest `sha256:bce76ae5dd7c7a7668c7675c8df2e3251dbfe41424ac7687ea3e83fd1fa875b5`,
  packet digest `sha256:5c51d81118c1f43a7972268657e99d5f2bdbb1bec248ce96af4d7e9db1c985e9`).
- Guide revision: `m4-77-authorized-execution-v7`
- Test-case source: `.agents/review/m4-issue-77-test-cases-v7.json`
- Supersedes: `.agents/manual-tests/milestone-4/77-authorized-execution-v6.md` and
  `.agents/review/m4-issue-77-test-cases-v6.json`
- Prior guide adjudication: `.agents/review/m4-issue-77-guide-v6-adjudication-v1.json`.
  The ticket-contract v9 correction resolves the stale-reference ambiguity without changing the
  CompatibilityCheckerV1 abstraction; the v7 guide preserves the closed capability/binding/policy
  mismatch taxonomy and treats protected-scope/reference-validity failures as fail-closed denials.
- External guide review evidence: pending `.agents/review/m4-issue-77-guide-external-review-v7.json`
- Human approval evidence: pending `.agents/review/m4-issue-77-guide-approval-v7.json`
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
  execution authority, exact and mismatched capability/binding/policy identity/version/digest
  selectors, immutable target/reference-substitution attempts, a non-default proposal lifetime,
  and PostgreSQL-controlled proposal/reference/lease expiry boundaries. Reference validity failures
  are not CompatibilityCheckerV1 mismatch reasons.
- Use test-only ephemeral `m4r1` and dispatch-envelope signing keys, a trusted reference store and
  explicit active, retiring, revoked, unknown, unavailable and active-to-retiring/
  retiring-to-revoked transition fixtures. Each fixture exposes only sanitized key ID/version,
  lifecycle and typed epoch; raw key/MAC/envelope bytes, credentials and raw provider routing
  identifiers never enter public or audit evidence.
- Install explicit per-contender counting `SupportToolGateway`, target-lookup, SQLite-ledger and
  provider-effect sentinels. A zero-call assertion is valid only when the exact sentinel identity
  and per-row/per-contender count appear in release evidence.
- TC-01 loads one literal pre-acquisition fixture with one physical row for every named variant
  below. The fixture imports or calls no production result type, error mapper, serializer or HTTP
  mapper. It seals its own digest, exact application/transport oracle, durable before/after state,
  and named workflow, proposal-lookup, acquisition, admission, execution-start/terminal-audit,
  gateway, target-lookup and provider sentinel identities/counts. Each row has its own release-
  evidence record; authentication, path-Workspace and HTTP-validation rows additionally require
  zero proposal lookup and zero `WriteProposalWorkflow.handle` calls.
- Compose deterministic non-runtime barriers/fault adapters for acquisition writes, admission
  locks, PostgreSQL commit acknowledgement, post-admission/pre-gateway, SQLite pre-commit,
  SQLite-commit/pre-ack, provider observation and generation-1 lease expiry. Add distinct
  execution-row lock barriers for `record_execution_observation` and `finalize_execution`. Each
  exposes operation start, PostgreSQL transaction timestamp, skewed application/non-database
  clocks, independent lease-boundary crossing while blocked, lock acquisition order and the
  operation's fresh `clock_timestamp()` sampled after acquiring the governing row lock. Test
  mutation and trusted-signing adapters are never registered with production application/HTTP
  dependency injection; TC-03, TC-07 and TC-12 inventory production composition, reject
  request-controlled provider/signer/adapter selection and probe every resolution surface to prove
  private-only reachability. Every supported Workspace/key mutation also emits a same-transaction
  epoch witness; the static registry emits immutable identity/version/digest across restart.
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
- The production composition exposes only the closed static typed capability registry and fixed
  production ReferenceProvider binding. The release harness compares its exact capability
  ID/version/operation projection and registry identity/version/digest to the locked allowlist,
  probes runtime capability/provider registration, discovery and plugin loading without relying on
  source-file or file-name inspection, and proves mutable authorization sources are ineligible.
- TC-03 loads its expected denial matrix from a test fixture that imports no production admission
  result type or mapper. Before invoking the application/HTTP seam, that fixture establishes each
  scenario's expected `proposal_id` from independent seed authority plus direct durable proposal
  reload, and expected `logical_execution_id` from direct durable generation-1 acquisition reload.
  It may not copy or derive either expected identity from a returned projection or any production
  result class, mapper, serializer or HTTP mapper. TC-10 loads both immutable matrices below from a
  release-harness fixture that imports or calls no production result class, enum, serializer or
  HTTP mapper and uses the same independent identity authority.
- The candidate Evaluation uses a unique run ID, this guide revision/digest, exact subject SHA,
  environment revision, all twelve case results/evidence references, overall verdict and
  `human_approval: pending`. Append through `record_evaluation.py`; after explicit result approval,
  append a separate approved record and never rewrite history.

## Immutable M4.3 public-result and denial matrices

These independently sourced tables exhaust every pre-acquisition Execute denial, post-acquisition
denial or repeated-execute result that Issue #77 may publish. Every application projection and HTTP
body has only the fields declared for its row; all other fields at every depth are forbidden. The
material target/reference substitution fixture is a separate immutable command/persistence-boundary
rejection: its exact typed rejection is taken from that boundary's contract, it creates no execution
state or provider call, and it must not be assigned a new `reference_*_mismatch` compatibility reason
or an invented Execute HTTP code.

### Pre-acquisition closed-denial rows

Every HTTP row has exactly `{"error":{"code":"<PUBLIC_CODE>"}}`: the outer object contains only
`error`, the nested object contains only `code`, and status is transport metadata absent from the
body. Raw-transport authentication and validation rows do not enter the workflow; where the same
denial is directly representable at the application seam, its exact oracle is the named
`KnoraError.code` below.

| TC-01 pre-acquisition fixture row | Exact application/transport oracle | HTTP | Exact public `error.code` |
| --- | --- | ---: | --- |
| missing authentication | direct null-principal `KnoraError.code=UNAUTHENTICATED`; HTTP workflow calls `0` | 401 | `UNAUTHENTICATED` |
| invalid authentication | authentication rejects before principal creation and workflow calls `0` | 401 | `UNAUTHENTICATED` |
| malformed JSON | transport validation rejects before command construction and workflow calls `0` | 422 | `TOOL_REQUEST_INVALID` |
| non-object JSON | transport validation rejects before command construction and workflow calls `0` | 422 | `TOOL_REQUEST_INVALID` |
| missing `expected_revision` | typed-command/transport validation uses `KnoraError.code=TOOL_REQUEST_INVALID` and workflow calls `0` | 422 | `TOOL_REQUEST_INVALID` |
| non-integer or boolean `expected_revision` | typed-command/transport validation uses `KnoraError.code=TOOL_REQUEST_INVALID` and workflow calls `0` | 422 | `TOOL_REQUEST_INVALID` |
| extra `logical_execution_id` | unknown-field validation uses `KnoraError.code=TOOL_REQUEST_INVALID` and workflow calls `0` | 422 | `TOOL_REQUEST_INVALID` |
| extra `request_fingerprint` | unknown-field validation uses `KnoraError.code=TOOL_REQUEST_INVALID` and workflow calls `0` | 422 | `TOOL_REQUEST_INVALID` |
| path Workspace mismatch | path authorization rejects before proposal lookup and workflow calls `0` | 403 | `WORKSPACE_ACCESS_DENIED` |
| current Workspace authorization denied | `KnoraError.code=WORKSPACE_ACCESS_DENIED` | 403 | `WORKSPACE_ACCESS_DENIED` |
| resource authorization denied | `KnoraError.code=TOOL_RESOURCE_ACCESS_DENIED` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| no execution grant | `KnoraError.code=TOOL_EXECUTION_NOT_AUTHORIZED` | 403 | `TOOL_EXECUTION_NOT_AUTHORIZED` |
| read-only grant | `KnoraError.code=TOOL_EXECUTION_NOT_AUTHORIZED` | 403 | `TOOL_EXECUTION_NOT_AUTHORIZED` |
| observation-only grant | `KnoraError.code=TOOL_EXECUTION_NOT_AUTHORIZED` | 403 | `TOOL_EXECUTION_NOT_AUTHORIZED` |
| read plus observation grants only | `KnoraError.code=TOOL_EXECUTION_NOT_AUTHORIZED` | 403 | `TOOL_EXECUTION_NOT_AUTHORIZED` |
| capability identity mismatch | `KnoraError.code=TOOL_PROPOSAL_STALE` | 409 | `TOOL_PROPOSAL_STALE` |
| capability version mismatch | `KnoraError.code=TOOL_PROPOSAL_STALE` | 409 | `TOOL_PROPOSAL_STALE` |
| capability digest mismatch | `KnoraError.code=TOOL_PROPOSAL_STALE` | 409 | `TOOL_PROPOSAL_STALE` |
| binding identity mismatch | `KnoraError.code=TOOL_PROPOSAL_STALE` | 409 | `TOOL_PROPOSAL_STALE` |
| binding version mismatch | `KnoraError.code=TOOL_PROPOSAL_STALE` | 409 | `TOOL_PROPOSAL_STALE` |
| binding digest mismatch | `KnoraError.code=TOOL_PROPOSAL_STALE` | 409 | `TOOL_PROPOSAL_STALE` |
| policy identity mismatch | `KnoraError.code=TOOL_PROPOSAL_STALE` | 409 | `TOOL_PROPOSAL_STALE` |
| policy version mismatch | `KnoraError.code=TOOL_PROPOSAL_STALE` | 409 | `TOOL_PROPOSAL_STALE` |
| policy digest mismatch | `KnoraError.code=TOOL_PROPOSAL_STALE` | 409 | `TOOL_PROPOSAL_STALE` |
| malformed `m4r1` syntax | `KnoraError.code=INVALID_TOOL_RESOURCE_REFERENCE` | 400 | `INVALID_TOOL_RESOURCE_REFERENCE` |
| non-canonical `m4r1` bytes | `KnoraError.code=INVALID_TOOL_RESOURCE_REFERENCE` | 400 | `INVALID_TOOL_RESOURCE_REFERENCE` |
| `m4r1` MAC corruption | `KnoraError.code=TOOL_RESOURCE_ACCESS_DENIED` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| `m4r1` protected-claim corruption | `KnoraError.code=TOOL_RESOURCE_ACCESS_DENIED` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| `m4r1` protected-scope corruption | `KnoraError.code=TOOL_RESOURCE_ACCESS_DENIED` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| trusted-store record deleted | `KnoraError.code=TOOL_RESOURCE_ACCESS_DENIED` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| trusted-store record replaced | `KnoraError.code=TOOL_RESOURCE_ACCESS_DENIED` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| trusted-store claims mismatch | `KnoraError.code=TOOL_RESOURCE_ACCESS_DENIED` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| trusted key store unavailable | `KnoraError.code=TOOL_RESOURCE_ACCESS_DENIED` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| reference key revoked | `KnoraError.code=TOOL_RESOURCE_ACCESS_DENIED` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| reference key unknown | `KnoraError.code=TOOL_RESOURCE_ACCESS_DENIED` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| expired resource reference | `KnoraError.code=TOOL_RESOURCE_ACCESS_DENIED` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| proposal expired before new execution | `KnoraError.code=TOOL_PROPOSAL_EXPIRED` | 409 | `TOOL_PROPOSAL_EXPIRED` |

For every row, the fixture captures a direct durable proposal/approval snapshot before and after the
request without using the request path for authority. The two snapshots are field-for-field equal
unless the row is one of the nine material capability/binding/policy identity/version/digest
mismatches. Temporary Workspace/resource/execution-authority denial and every `m4r1`
syntax/integrity/scope/trusted-store/key/expiry denial preserve the exact immutable `approved`
proposal and approval identity/version/digest. Each capability/binding/policy mismatch persists its
exact typed `proposal_state=stale` and `approval_validity=invalidated` reason; restoring the old
current selector still denies reuse of that approval. A material target/reference replacement is
rejected at the immutable command/persistence boundary, is not classified as a compatibility reason,
and a different target requires a new proposal plus authorized-human approval. Proposal expiry
preserves the durable proposal and approval identity/version/digest while projecting `approved`,
non-stale, non-executable and `expired`; Issue #77 introduces no separate approval-expiry
abstraction. Preserving approval provenance is not write authority: malformed, scope-mismatched,
revoked or expired references remain non-executable and cannot be revived by restoring the old
reference state.

Every row creates zero execution, acquisition, admission, execution-start audit or terminal-audit
artifact and makes zero gateway, target-lookup or provider calls against its named sentinels.
Authentication, path-Workspace and raw HTTP-validation rows also make zero proposal-lookup and zero
workflow calls. Release evidence contains one row with the independent fixture digest, exact
application/transport result, exact HTTP status/decoded key sets and code, durable before/after
snapshot digests, all named sentinel identities/counts and old-approval retry where applicable.

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
body. `provider_outcome_not_found` is intentionally absent from this table: it is available only as
the private read-only provider Adapter observation in TC-08, is not a #77 application result or HTTP
body, and must not be added to the public matrix.

### Post-acquisition denial rows

Every row below has application result `ProposalNotExecutable`. Its application projection has
exactly `proposal_id`, `logical_execution_id`, `lifecycle=executing`,
`outcome_type=proposal_not_executable` and the named `reason_code`. Its HTTP body has exactly
`{"error":{"code":"<PUBLIC_CODE>"}}`: the outer object has only `error`, and the nested
object has only `code`. The status code is absent from both bodies.

For every denial row, `proposal_id` and `logical_execution_id` are canonical lowercase RFC 4122
UUID strings. `proposal_id` equals the independently seeded and directly reloaded durable proposal
identity for that scenario. `logical_execution_id` equals the generation-1 logical identity
directly reloaded from durable acquisition state before application/HTTP invocation. The
independent fixture may not copy or derive either expected value from the returned
`ProposalNotExecutable` projection or any production result class, mapper, serializer or HTTP
mapper. Release evidence records the durable source reference, expected value, actual value and
equality result for both identities on every row. Neither identity is added to the closed HTTP
error body.

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
| protected-scope corruption | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| trusted-store record deleted | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| trusted-store record replaced | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| trusted-store claims mismatch | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| key revoked | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| key unknown | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| trusted key store unavailable | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| reference expired at admission lock | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| retiring-to-revoked mutation-first | `resource_access_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |

The compatible control, active exact, retiring exact and active-to-retiring mutation-first rows are
admission-success controls, not denial rows. Admission-first transition rows use the prior bound
state and continue through the applicable execution-outcome row. The protected-scope and
reference-expired rows are independently exercised after acquisition: each uses fresh post-lock
PostgreSQL `clock_timestamp()`, the exact `ProposalNotExecutable(resource_access_denied)` /
`403 TOOL_RESOURCE_ACCESS_DENIED` mapping, independently reloaded proposal/logical-execution IDs,
zero admission/admission-audit/gateway/provider activity and restart-stable generation-1
non-finalization evidence. They are reference-validity denials, not stale/invalidated compatibility
rows.

## Locked Test Cases

### M4-77-TC-01: Pre-acquisition authorization, stale state and non-escalation

- Purpose: prove human approval never grants execution authority and old approval cannot silently
  become executable after a material incompatibility.
- Steps:
  1. Load the literal pre-acquisition matrix and its digest without importing any production result,
     error or HTTP mapper. Seed a separate approved proposal and named sentinel set for every row and
     capture its durable proposal/approval snapshot before invocation.
  2. Invoke every application-representable row and every exact HTTP row, including missing/invalid
     authentication, malformed/non-object JSON, missing/invalid revision, both forbidden identity
     fields, path/current Workspace denial, resource denial, all limited execution grants, every
     capability/binding/policy mismatch, every named `m4r1` syntax/trust/key/expiry failure and
     proposal expiry.
  3. Reload durable state directly, capture all named sentinel counts and compare exact application
     result plus decoded HTTP status/body/key sets with the literal row.
  4. Restore only conditions the approved design classifies as temporary and retry the exact old
     approval. Separately restore each material capability/binding/policy selector and retry each old
     invalidated approval. Attempt immutable target/reference substitution through the command and
     persistence boundary, then prove malformed, scope-mismatched, revoked or expired references do
     not make the old proposal executable or create a new compatibility reason.
- Expected results:
  - Every row returns the exact independently loaded application/transport result and exact closed
    HTTP status/body with no extra outer, nested or status field.
  - Every denial creates zero execution/acquisition/admission/execution-start or terminal-audit
    artifact and zero gateway/target-lookup/provider calls for that row's named sentinels;
    authentication/path/validation rows also have zero proposal lookups and workflow calls.
  - Temporary Workspace/resource/execution denial and every `m4r1` syntax/integrity/scope/trust/key/
    expiry denial preserve exact immutable `approved` state and approval identity/version/digest.
    Proposal expiry preserves that provenance while projecting approved, non-stale, non-executable
    and expired. Immutable target/reference substitution is rejected at the command/persistence
    boundary without a `reference_*_mismatch` reason; a different target requires a new proposal and
    authorized-human approval.
  - Each capability/binding/policy mismatch persists `proposal_state=stale`,
    `approval_validity=invalidated` and its exact typed reason; later restoration cannot reuse it,
    and only a new proposal plus authorized-human approval is executable.
- Evidence to capture: independent literal matrix source/digest and one release row per variant;
  exact application/HTTP comparisons; before/after durable projections; named workflow/proposal-
  lookup/acquisition/admission/audit/gateway/lookup/provider sentinel identities/counts; and old-
  approval retry results.

### M4-77-TC-02: Server-owned identity, atomic acquisition and loser isolation

- Purpose: prove callers cannot influence logical execution identity/fingerprint and concurrent
  workflows cannot hide loser provider calls behind idempotency.
- Steps:
  1. Inject logical execution ID and request fingerprint through writable application/HTTP inputs.
  2. Independently normalize the authoritative operation, exact capability, exact external scope,
     protected reference/resource claims and `{title, description}` intent, recompute
     `canonical-json-v1` and compare the server-owned logical ID/fingerprint at proposal,
     `AcquireWitness`, admission, persisted envelope and provider verification boundaries.
  3. Race identified contenders, inspect another PostgreSQL session before commit, read the complete
     committed acquisition tuple after commit and restart, and inject a fault after each acquisition
     write before commit.
- Expected results:
  - Both injected fields are absent from writable schemas or rejected before state creation.
  - Server-minted logical ID and independently recomputed fingerprint are not caller-selectable or
    caller-influenceable, are byte-identical and immutable through every generation-1 boundary and
    after restart.
  - Exactly one contender receives `AcquireApplied` and commits one complete tuple; it is the only
    possible gateway caller. Each loser makes zero gateway/provider calls. Pre-commit observers see
    no tuple, rollback leaves approved with no execution/snapshot/audit fragment, and restart
    reconstructs every acquisition field.
- Evidence to capture: input rejection matrix, canonical normalized input/digest records at every
  boundary, complete field-by-field acquisition tuple, contender/result/call correlation, rollback
  absence and restart snapshots.

### M4-77-TC-03: Complete current authorization and m4r1 recheck after acquisition

- Purpose: close every acquisition-to-admission TOCTOU window and lock every denial's application
  and HTTP projection.
- Steps:
  1. Acquire and block immediately before private admission authorization.
  2. Run every row in the post-acquisition denial matrix: Workspace/resource/execution authority;
     capability/binding/policy identity, version and digest; canonical bytes, MAC, protected claims
     and protected-scope corruption; trusted-store delete, replacement and claims mismatch; revoked,
     unknown and unavailable key state; reference expiry; and retiring-to-revoked mutation-first.
  3. For every supported Workspace-owned authority/selector mutation and reference-key mutation,
     capture the changed authoritative row and exactly one epoch increment under one transaction/
     commit marker, then run a rollback branch. Capture dual-scope mutation order (global
     reference-key epoch then Workspace) and admission order (execution row then global
     reference-key epoch then Workspace), rejecting inverse/alternate order.
  4. Reload the compiled static registry across process/restart and attempt registration/mutation,
     mutable-source, request-controlled provider/signer/adapter and provider-discovery paths; run
     compatible, active exact, retiring exact, active-to-retiring and admission-first controls.
  5. Before each denial invocation, capture expected proposal/acquisition identities from the
     independent seed authority and direct durable reload. Compare those expected identities,
     private admission result, application projection and decoded HTTP body with the independently
     loaded exact row before inspecting admission/audit and gateway/provider sentinels.
- Expected results:
  - Every denial happens after post-lock reload. It returns the exact
    `ProposalNotExecutable` projection and exact HTTP status/error envelope from the immutable
    denial matrix. Application and HTTP shapes contain no field outside that row.
  - For every denial row, both application IDs are canonical lowercase RFC 4122 UUIDs and equal the
    independently seeded/directly reloaded durable proposal and generation-1 acquisition identities;
    expected values are never derived from the returned projection or production mapper.
  - Every denial persists zero admission rows, zero admission-audit rows and makes zero gateway and
    provider calls for that row's named sentinels. Protected-scope corruption and reference expiry
    use fresh post-lock PostgreSQL time and the exact `resource_access_denied` / 403
    `TOOL_RESOURCE_ACCESS_DENIED` mapping.
  - Every capability/binding/policy mismatch also persists its matching typed stale/invalidation
    reason; authority/reference/key denials do not silently become a compatibility reason.
  - Each mutation witness binds its changed row and exactly one epoch increment to one commit marker;
    rollback leaves both unchanged. Static registry identity/version/digest is immutable and equal
    across reload, has no plugin epoch, and mutable sources cannot authorize dispatch. Production
    composition cannot resolve test-only adapters and request-controlled selections are rejected
    before state/provider activity.
  - Compatible, active exact and retiring exact controls admit exactly once when all other facts are
    compatible. Admission binds post-lock key ID/version and epoch and makes exactly one provider
    call.
  - Active-to-retiring mutation-first remains admissible under the retiring key.
    Retiring-to-revoked mutation-first uses the exact denial row. Admission-first binds the prior key
    state under the TC-04 epoch rule.
  - Only sanitized evidence is appended. No caller assertion or raw key/MAC/envelope is accepted.
  - Evidence to capture: independently sourced denial/result/HTTP matrix and its digest; per-row
    durable identity source references, expected/actual `proposal_id` and `logical_execution_id` and
    equality results; compatible and transition controls; post-lock key ID/version and epoch;
    same-transaction mutation row/epoch commit markers and rollback absence; global-to-Workspace
    dual-mutation and execution-to-global-to-Workspace admission lock traces; static-registry
    identity/version/digest reload and mutable-source ineligibility; production DI/resolver and
    request-selector negative probes; per-row admission/audit/gateway/provider counts; application/
    HTTP field-shape comparison; and sanitized-evidence scan.

### M4-77-TC-04: Mutation/admission linearization and PostgreSQL time

- Purpose: prove same-transaction epoch advancement, canonical lock order, one admission and fresh
  database-time expiry decisions.
- Steps:
  1. Race every real typed Workspace authority/resource/execution/capability/binding/policy mutation
     and reference-key mutation against admission and race same-generation issuers.
  2. For every mutation capture the changed authoritative row and exactly one corresponding epoch
     increment under one transaction/commit marker, then inject rollback and prove both remain
     unchanged.
  3. Exercise dual-scope mutation with global reference-key then Workspace locking and deliberately
     attempt inverse order; capture admission execution-row then global reference-key epoch then
     Workspace locking and reject alternate order.
  4. Block acquisition across proposal expiry and admission across reference and lease expiry under
     skewed application clocks; reload the static registry across process/restart and attempt mutable
     runtime/request/provider-discovery sources.
- Expected results:
  - Mutation-first denies; admission-first stores the exact prior global/Workspace epoch vector and
    one byte-identical admission/audit exists per logical execution.
  - Every Workspace-owned mutation advances `workspace_dispatch_epoch` exactly once with its row
    under one commit marker; every reference-key mutation advances `reference_key_epoch` exactly once;
    rollback leaves both unchanged.
  - Dual-scope mutation order is global reference-key epoch then Workspace and admission order is
    execution then global then Workspace; inverse/alternate order is rejected with no admission or
    provider call.
  - Static registry identity/version/digest is immutable and equal across reload with no plugin epoch;
    mutable sources are ineligible and cannot authorize dispatch.
  - Fresh post-lock PostgreSQL `clock_timestamp()` decides every proposal/reference/lease boundary;
    skewed or transaction-start clocks cannot revive an expired action. Admission-side reference
    expiry uses the exact TC-03 `resource_access_denied` / 403 `TOOL_RESOURCE_ACCESS_DENIED` row and
    zero-activity evidence.
- Evidence to capture: same-transaction row/epoch commit-marker traces and rollback absence;
  dual-mutation global-to-Workspace and admission execution-to-global-to-Workspace lock traces;
  static-registry reload/mutation and mutable-source ineligibility evidence; issuer results,
  admission uniqueness, post-lock time samples and skew comparison.

### M4-77-TC-05: Complete admission witness and commit/ack ambiguity

- Purpose: prevent partial admission, invented commit state or regenerated dispatch envelopes.
- Steps:
  1. Construct the expected canonical tuple from authoritative proposal/acquisition/authorization
     inputs and compare each field individually without grouped shorthand: `admission_schema_version`,
     `admission_identity`, `admission_digest`, `purpose`, `workspace_id`, `proposal_id`,
     `logical_execution_id`, `request_fingerprint`, `capability_identity`, `capability_version`,
     `capability_digest`, `binding_identity`, `binding_version`, `binding_digest`, `policy_identity`,
     `policy_version`, `policy_digest`, `reference_identity`, `reference_version`, `reference_digest`,
     `reference_claims_digest`, `resource_identity_digest`, `canonical_target_digest`,
     `canonical_parameter_digest`, `complete_intent_digest`, `reference_key_epoch`,
     `workspace_dispatch_epoch`, `authority_decision_digest`, `authority_witness_digest`, `owner`,
     `generation`, `database_issue_time`, `lease_started_at`, `lease_deadline`,
     `envelope_signing_key_identity`, `envelope_signing_key_version`, `routing_snapshot_digest`,
     `canonical_envelope_digest`, `admission_audit_identity` and `admission_audit_digest`.
  2. Restart PostgreSQL, rotate the active issuance key and reload exact stored envelope bytes.
  3. Capture the intended tuple and envelope bytes before the commit/ack fault; force committed-but-
     unacknowledged and rolled-back outcomes at the PostgreSQL commit/ack seam, then perform
     authoritative readback by logical execution ID after restart/key rotation.
- Expected results:
  - For `admission_schema_version`, `admission_identity`, `admission_digest`, `purpose`,
    `workspace_id`, `proposal_id`, `logical_execution_id`, `request_fingerprint`,
    `capability_identity`, `capability_version`, `capability_digest`, `binding_identity`,
    `binding_version`, `binding_digest`, `policy_identity`, `policy_version`, `policy_digest`,
    `reference_identity`, `reference_version`, `reference_digest`, `reference_claims_digest`,
    `resource_identity_digest`, `canonical_target_digest`, `canonical_parameter_digest`,
    `complete_intent_digest`, `reference_key_epoch`, `workspace_dispatch_epoch`,
    `authority_decision_digest`, `authority_witness_digest`, `owner`, `generation`,
    `database_issue_time`, `lease_started_at`, `lease_deadline`, `envelope_signing_key_identity`,
    `envelope_signing_key_version`, `routing_snapshot_digest`, `canonical_envelope_digest`,
    `admission_audit_identity` and `admission_audit_digest`, the persisted value is individually
    non-null and exactly equal to its authoritative expected value.
  - Committed readback returns exactly one complete tuple whose individual field values, canonical
    tuple bytes/digest and private envelope bytes are byte-identical to the intended values after
    restart/key rotation; there is no second insert, audit, claim set, signing operation or envelope
    regeneration.
  - Rolled-back readback has complete admission/audit absence, zero gateway calls and no #77 retry.
  - No grouped/lossy field, partial or third state exists; rollback has complete absence.
- Evidence to capture: intended/persisted non-null field table and linked-audit comparison, canonical
  tuple and envelope byte/digest comparison before/after restart and key rotation, both ambiguity
  branches and insert/sign/gateway counters.

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
  1. Before private provider cases, inventory production application/HTTP dependency registrations
     and resolver results, attempt request-controlled provider/signer/adapter/harness selections,
     and prove only the fixed production ReferenceProvider binding is reachable before state creation.
  2. Through the private harness, deliver same-ID/same-fingerprint replay and two independently valid
     same-ID/different-fingerprint envelopes.
  3. Separately deliver an ordinarily tampered envelope and an integrity-valid envelope bound to a
     different Workspace/external scope than the selected provider target.
  4. Capture ordered integrity, binding, target-lookup, SQLite-ledger and effect sentinels for both
     negative rows.
  5. Parameterize success, `target_not_found`, `validation_rejected` and `policy_rejected`; inject
     pre-commit and committed-before-ack faults, reopen SQLite and replay equal fingerprint.
  6. For the unequal-fingerprint conflict, close/reopen SQLite and seal one sanitized content-
     addressed correlation record containing logical execution ID, attempted fingerprint and
     admission digests, existing SQLite row-set digest, typed conflict result, target-lookup count,
     ticket-effect count and post-restart row-set digest.
- Expected results:
  - Production composition resolves no private `ReferenceProviderContractHarness`, trusted test
    signer or mutation adapter; request-controlled selector attempts are rejected before proposal/
    execution state and make zero provider calls. Equal fingerprint replays one effect/outcome.
    Both valid unequal fingerprints pass integrity and provider recomputation from signed
    authoritative intent, then the second conflicts before target lookup/mutation with no second
    effect.
  - Ordinary tampering rejects before SQLite mutation.
  - Cross-binding returns exact typed `provider_scope_denied` after integrity verification but
    before target lookup and before any SQLite idempotency-ledger or effect mutation. Target lookup,
    ledger-row and target/ticket-effect counts are each exactly zero; the result is sanitized and
    includes no target or routing detail.
  - Each closed rejection atomically owns one exact logical-ID/fingerprint/admission-digest ledger
    row, zero ticket/target effects, pre-commit rollback absence and restart-stable replay.
  - The conflict correlation record proves one original durable ledger/effect, no second effect and
    stable provider truth after restart; TC-07 does not infer or assert Knora finalization from
    provider state.
- Evidence to capture: production DI/resolver manifest and request-selector rejection evidence, SQLite
  effect/ledger rows before/after restart, provider fingerprint recomputation, separate tamper trace,
  cross-binding verification-order trace and zero counters, conflict trace and content-addressed
  correlation record, and one record per closed rejection.

### M4-77-TC-08: Branch-specific crash and provider-not-found semantics

- Purpose: prevent false proof-no-write and unsafe retry authority after durable admission.
- Steps:
  1. Fault after admission before gateway, before SQLite commit and after SQLite commit before
     acknowledgement as three separately named branches.
  2. Inspect SQLite ledger/effect counts before and after provider restart; parameterize success and
     every closed rejection in the committed branch.
  3. Inspect Knora lifecycle/identity/result, then invoke only the private read-only provider Adapter
     observer in no-receipt branches. Label its `provider_outcome_not_found` result as provider-
     boundary-only evidence; do not invoke reconciliation or an application/HTTP workflow for it.
- Expected results:
  - Admission-before-gateway and pre-SQLite-commit each have exactly zero provider rows/effects.
  - Committed-before-ack has exactly one durable replayable success row/effect or one named closed-
    rejection row with zero effects.
  - Every branch not yet Knora-finalized remains `executing` with unchanged admission/logical ID/
    fingerprint and exact `indeterminate_external_outcome`. No #77 retry/replay/takeover authority
    appears; no-receipt observation is `provider_outcome_not_found`.
  - `provider_outcome_not_found` is not a #77 application result or HTTP body and creates no public
    execution-outcome matrix row.
- Evidence to capture: three branch records, provider rows/effects before/after restart, Knora
  application/HTTP projection, separately labeled provider-boundary-only
  `provider_outcome_not_found` record and absence-of-recovery counters.

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

- Purpose: prevent expired-owner finalization, stale-clock fencing decisions, implementation-derived
  public expectations and private admission leakage.
- Steps:
  1. For provider-only success and each closed rejection, prepare separate generation-1 fixtures for
     observation and finalization. The observation fixture has provider truth with no PostgreSQL
     observation; the finalization fixture has a durable authorized observation ready to finalize.
     Begin each operation before `lease_expires_at`, capture operation start plus PostgreSQL
     transaction timestamp and skew application/non-database clocks, then block it behind the
     governing execution-row lock before the expiry decision.
  2. While each operation is blocked, use an independent PostgreSQL session to prove
     `clock_timestamp() > lease_expires_at`, then release the lock. Capture the operation's own fresh
     `clock_timestamp()` immediately after lock acquisition and invoke observation or finalization.
     Recapture execution row, ordered observation/audit IDs and counts, stable row-set digest and
     owner/operation-correlated write trace.
  3. Repeat the same observation and finalization paths as before-expiry controls, releasing while
     both the independent sample and operation's own post-lock `clock_timestamp()` remain before the
     deadline. Link, without republishing, the provider-boundary-only read-only
     `provider_outcome_not_found` evidence from TC-08; do not invoke or add an application/HTTP
     projection for it. Then exercise the public indeterminate, current execution-in-progress,
     provider-idempotency-conflict and fenced rows.
  4. For `ExecutionIndeterminate`, current `ExecutionInProgress`, provider-conflict
     `ExecutionInProgress`, `ExecutionFenced` and every post-acquisition `ProposalNotExecutable`
     row, capture operation-correlated before-result, after-result and post-PostgreSQL-restart
     execution/finalization/terminal-audit snapshots. Link provider conflict to the exact TC-07
     correlation record without treating provider state as Knora finalization authority.
  5. Exercise every TC-03 post-acquisition denial row through application and HTTP seams. Before
     invocation, capture the independently seeded/directly reloaded expected proposal and
     generation-1 logical execution identities for that scenario.
  6. Load both immutable expected matrices without importing/calling production result classes,
     enums, serializers or HTTP mappers. For every row compare exact application result,
     `outcome_type`, lifecycle, HTTP status, complete application/HTTP key sets and value domains,
     including exact denial identity equality. Recursively inject every forbidden field into both
     projection families.
- Expected results:
  - For observation and finalization independently, each expired branch starts and establishes its
    transaction timestamp before the deadline, samples fresh PostgreSQL time after lock acquisition
    later than the deadline, returns `ExecutionFenced` and appends zero operation-correlated
    execution/observation/audit or other PostgreSQL writes. Ordered IDs/counts and stable row-set
    digest remain exact; provider truth remains readable after restart.
  - Each valid-lease before-expiry control samples fresh post-lock PostgreSQL time before the deadline:
    success records one durable observation/audit and finalizes to `succeeded` with the exact success
    outcome; `target_not_found`, `validation_rejected` and `policy_rejected` each record one durable
    observation/audit and finalize to `failed` with its exact rejection code and zero target effects.
    Skewed application/non-database and transaction-start clocks decide neither branch.
  - `provider_outcome_not_found` exists only as the linked TC-08 private provider-boundary read-only
    observation; it has no #77 application/HTTP projection or public matrix row and grants no retry
    authority. `indeterminate_external_outcome` and provider fingerprint conflict never terminalize.
  - Every admitted non-terminal fixture remains generation 1 and lifecycle `executing` after
    PostgreSQL restart with unchanged `proposal_id`, `logical_execution_id`, `request_fingerprint`
    and `admission_identity`. This applies to `indeterminate_external_outcome`, the admitted current-
    execution fixture, provider fingerprint conflict and the post-admission fenced fixture.
  - Protected-scope corruption and reference expiry are post-acquisition but pre-admission denials.
    After PostgreSQL restart each retains unchanged `proposal_id`, `logical_execution_id`,
    `request_fingerprint`, generation and acquisition witness/audit identity, while
    `DispatchAdmissionWitness` row count and admission-audit row count remain `0`. No
    `admission_identity` exists or is asserted for either denial.
  - For every non-finalizing application/HTTP row and the separately linked provider-boundary-only
    observation, terminal outcome/finalization row count, terminal-audit append delta and operation-
    correlated finalization-write count are `0`, and the terminal-column/row-set digest is unchanged.
    A typed non-terminal observation/audit append is counted separately and is permitted.
  - Provider conflict returns the exact application projection containing only `proposal_id`,
    `logical_execution_id`, `lifecycle=executing`, `outcome_type=execution_in_progress` and
    `reason_code=provider_idempotency_conflict`; the decoded HTTP 409 body is field-for-field equal.
    Its post-restart generation remains 1 and TC-07 still proves exactly one original provider
    ledger/effect and no second effect.
  - Every execution-outcome application result and decoded HTTP body is field-for-field equal to one
    exact execution-outcome matrix row.
  - Every post-acquisition denial returns exact `ProposalNotExecutable` fields and exact closed HTTP
    error status/body from one denial-matrix row. Its IDs are canonical lowercase RFC 4122 UUIDs and
    exactly equal the pre-invocation durable scenario identities. No TC-03 denial is unclassified.
  - The expected matrices come from the independent fixture and cover every named row exactly once.
  - No additional recursive field, raw provider/routing, admission/envelope/MAC/fingerprint,
    authority, key/signing, credential, secret or other private material is accepted or emitted.
- Evidence to capture: separate observation/finalization clock tuples containing lease deadline,
  operation start, transaction timestamp, skewed application clock values, blocker/release/lock-
  acquisition ordering, independent boundary sample and deciding post-lock `clock_timestamp()`;
  expired and before-expiry execution/observation/audit snapshots and operation-correlated write
  counts; per-admitted-non-terminal-row before/after/post-restart generation, lifecycle,
  proposal/logical/fingerprint/admission identity, terminal-row, terminal-audit, finalization-write
  and terminal-digest comparisons; protected-scope and reference-expiry pre-admission acquisition-
  identity equality plus exact zero admission/admission-audit counts; TC-08 provider-boundary-only
  `provider_outcome_not_found` linkage with explicit absence from application/HTTP matrices; stable
  PostgreSQL row-set digests; TC-07 conflict-correlation/provider restart record; independent
  execution and denial matrix source/digest including protected-scope and reference-expiry rows;
  per-row denial durable identity source plus expected/actual ID equality; complete per-row
  application/HTTP comparisons; and forbidden-field failures.

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
  4. Attempt request-controlled provider/signer/adapter/harness selection, then probe every production
     application/HTTP composition surface for runtime capability/provider
     registration, capability/provider discovery and plugin loading. Structural/typed runtime
     probes are required; source-text or file-name assertions are invalid.
  5. Record subject SHA/clean status, recreate/migrate PostgreSQL and run the exact focused command.
     Recreate/migrate PostgreSQL, run full suite serially, Ruff and Compose; recreate/migrate once
     more, record Alembic head, validate release evidence covers TC-01 through TC-11 and inspect
     final clean status.
- Expected results:
  - Production registry exactly equals the closed typed allowlist and exposes no runtime
    registration, discovery or plugin-loading operation; the production provider binding is fixed
    and request-controlled selections are rejected before state/provider activity.
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
`.agents/manual-tests/milestone-4/77-authorized-execution-v7.evaluations.jsonl`. Append a candidate
record with `human_approval: pending`; after explicit result approval append a separate approved
record. This guide becomes immutable only after its externally reviewed digest receives explicit
human lock approval.
