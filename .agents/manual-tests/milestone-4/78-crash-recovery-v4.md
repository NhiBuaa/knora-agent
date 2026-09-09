# Manual Test Guide: M4.4 crash recovery and provider reconciliation v4

## Metadata

- Feature: Milestone 4 — Tools and human approval
- Slice: Issue #78 — crash recovery and provider reconciliation
- Authoritative specification: GitHub Issue #78 and
  `.agents/review/m4-issue-78-revision-v5.md` pending external review
- Guide revision: `m4-78-crash-recovery-v4`
- Test-case source: `.agents/review/m4-issue-78-test-cases-v4.json`
- Prior guide review: `.agents/review/m4-issue-78-guide-external-review-v3.json`, `APPROVE`
- External guide review evidence: pending `.agents/review/m4-issue-78-guide-external-review-v4.json`
- Human approval evidence: pending `.agents/review/m4-issue-78-guide-approval-v4.json`
- Revision scope: v4 changes only the TC-09/TC-10 evidence-provenance model. It distinguishes the
  clean tested subject from a subsequent evidence-publication/delivery commit, eliminating an
  impossible self-reference while preserving all recovery, authorization, concurrency, matrix and
  static-registry assertions.
- Lock rule: this exact guide digest becomes immutable only after external `APPROVE` and explicit
  repository-owner approval; implementation remains blocked until both records exist

## Prerequisites

- Create a clean detached test worktree at the exact `tested_subject_commit` recorded in the
  Evaluation. This is the only commit supplied to focused/full/Ruff/Compose/Alembic verification.
  The worktree starts clean; after a successful release-harness run, the only permitted dirty path
  is `.agents/review/m4-issue-78-release-evidence-v1.json`.
- Resolve Python as `D:\Developer\Projects\knora-agent\.venv\Scripts\python.exe` and set
  `$env:KNORA_DATABASE_URL = "postgresql+psycopg://knora:knora@127.0.0.1:5432/knora"` and
  `$env:PYTHONPATH = "D:\Developer\Projects\knora-agent-worktree\issue-78-m4.4;D:\Developer\Projects\knora-agent-worktree\issue-78-m4.4\backend\src"`.
- Docker project `m4-integration` supplies PostgreSQL. Run all PostgreSQL suites serially. Recreate
  the database through `docker compose -p m4-integration exec -T postgres psql -U knora -d postgres
  -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='knora'
  AND pid <> pg_backend_pid()" -c "DROP DATABASE IF EXISTS knora" -c "CREATE DATABASE knora OWNER
  knora"`.
- Use a unique temporary SQLite provider file. Its provider ticket/idempotency ledger must survive
  Adapter recreation independently from PostgreSQL `ToolActionStore`; never use a developer's
  non-test provider database.
- Seed `executing` proposals in both `NoAdmission` and `AdmissionOutstanding` recovery variants.
  Each seed has independently captured proposal ID, logical execution ID, request fingerprint,
  immutable `AuthorizedExecutionBindingSnapshot`, generation, owner, lease deadline, admission
  identity/digest when present, and provider scope/routing alias. Expected identities come from the
  fixture and direct durable reload, never from the returned application projection.
- Seed provider observations for not-found, unavailable, timeout, malformed/unknown, success and
  each closed rejection: `target_not_found`, `validation_rejected`, `policy_rejected`.
- Install independent ordered/counting sentinels for authentication, path-Workspace binding,
  observation `WorkspaceResourceAuthorizer`, trusted-snapshot resolution, provider observation,
  current `m4r1` verification, write `WorkspaceResourceAuthorizer`, `ExecutionAuthorizer`, exact
  compatibility, retry decision, admission creation/reuse, dispatch, `create_ticket`, target lookup,
  provider-observation lookup, provider-ledger read, provider-ledger mutation and external ticket
  effects. Observation/read counters are distinct from provider write/effect counters; a sentinel
  for one authority or operation kind cannot stand in for another.
- Provide unauthenticated, path-Workspace mismatch and resource-observation-denied fixtures. For the
  differential write case, keep one valid `AuthorizedExecutionBindingSnapshot` and current
  observation authorization while independently making each current write authority absent,
  expired, revoked or denied. Snapshot fields and provenance must never be injected into or accepted
  by a write authorizer.
- Provide deterministic PostgreSQL execution-row barriers for takeover, observation and
  finalization. Each records operation start, transaction timestamp, lock acquisition, fresh
  post-lock PostgreSQL time, lease deadline and skewed application/non-database clocks. Host clocks
  never decide staleness.
- Provide deterministic crash barriers for provider-commit-before-Knora-persist and
  executing-persist-before-provider-receipt, plus a delayed original dispatch barrier. Fault and
  mutation adapters are test-only and cannot be selected through production application/HTTP
  composition or request input.
- Provide proposal/reference expiry, reference-key revocation, missing/mismatched trusted routing
  and all nine material capability/binding/policy identity/version/digest mismatches. Observation
  routing authority never confers write authority.
- Load expected result, authority and audit matrices from immutable fixtures that import no
  production result type, enum, serializer, HTTP mapper or error mapper. Every row includes expected
  complete recursive key sets, value domains, status, durable before/after state and named sentinel
  counts.
- The deterministic release harness writes one sanitized
  `.agents/review/m4-issue-78-release-evidence-v1.json` bound to the exact `tested_subject_commit`, source base
  `1cbf7d5f64bc94bd4d9313c2cf0fef46237b59e1`, PostgreSQL revision, SQLite file/schema identity,
  every Test Case ID and all sentinel/barrier identities. It contains no raw routing, provider ID,
  envelope bytes, key material, credentials, authority secrets or raw command output.
- The focused release command runs from `backend` and is exactly:
  `& $python -m pytest test/tools/test_reconciliation_workflow.py
  test/tools/test_reconciliation_postgres.py test/tools/test_reference_provider.py
  test/tools/test_proposal_http.py ../evals/test/test_m4_78_release_acceptance.py -q`.
- The authoritative full-suite command runs from `backend` and is exactly
  `& $python -m pytest test ../evals/test -q`. Record invocations, exits and totals. Run
  `& $python -m ruff check .` from the repository root and `docker compose config --quiet`.
- Before focused/full suites, recreate the database and run
  `Push-Location backend; & $python -m alembic upgrade head; & $python -m alembic current;
  Pop-Location`. After the full suite, recreate, upgrade, downgrade one revision, re-upgrade and
  confirm current head.
- Commit the sole generated evidence path as `evidence_publication_commit`. It must have
  `tested_subject_commit` as an ancestor and its diff from that subject must contain no production,
  test, dependency, configuration or entry-point path. Record both commits and the release-evidence
  digest in the worker result; the final `ticket_commit`/delivery head is a separate provenance
  field and never overwrites the evidence `subject_sha`.
- The candidate Evaluation uses a unique run ID, this guide revision/digest, exact tested subject SHA,
  delivery-head SHA, environment revision, all ten case results/evidence references, overall verdict and
  `human_approval: pending`. Append through `record_evaluation.py`; explicit result approval appends
  a separate record and never rewrites history.

## Immutable public reconciliation matrix

Every successful or non-terminal application projection has exactly `proposal_id`,
`logical_execution_id`, `lifecycle`, `outcome_type` and the one variant field named below. Both IDs
are canonical lowercase RFC 4122 UUIDs loaded from durable fixture authority. The decoded HTTP body
is field-for-field equal to the application projection. Status is transport metadata and is absent
from the body.

| Result | `lifecycle` | HTTP | `outcome_type` | Sole variant field |
| --- | --- | ---: | --- | --- |
| `ReconciledSucceeded` | `succeeded` | 200 | `reconciled_succeeded` | `external_resource_reference`: non-empty opaque integrity-protected reference |
| `ReconciledFailed(target_not_found)` | `failed` | 502 | `reconciled_failed` | `rejection_code=target_not_found` |
| `ReconciledFailed(validation_rejected)` | `failed` | 502 | `reconciled_failed` | `rejection_code=validation_rejected` |
| `ReconciledFailed(policy_rejected)` | `failed` | 502 | `reconciled_failed` | `rejection_code=policy_rejected` |
| Provider observation unavailable | `executing` | 202 | `reconciliation_indeterminate` | `reason_code=provider_observation_unavailable` |
| Provider observation timeout | `executing` | 202 | `reconciliation_indeterminate` | `reason_code=provider_observation_timeout` |
| Provider observation malformed/unknown | `executing` | 202 | `reconciliation_indeterminate` | `reason_code=provider_observation_malformed` |
| `ProviderOutcomeNotFound` | `executing` | 202 | `provider_outcome_not_found` | `reason_code=provider_outcome_not_found` |
| `ExecutionInProgress` | `executing` | 409 | `execution_in_progress` | `reason_code=execution_in_progress` |
| `ExecutionFenced` | `executing` | 409 | `execution_fenced` | `reason_code=execution_fenced` |

`RetryAuthorizationDenied` is a closed application denial and never a provider outcome. HTTP uses
only `{"error":{"code":"<PUBLIC_CODE>"}}`: current Workspace/resource/execution authority denial
uses the corresponding existing 403 code, invalid/missing/revoked/expired reference trust uses the
existing 400/403 code, and material capability/binding/policy mismatch uses
`409/TOOL_PROPOSAL_STALE`. Every denial has zero provider write and preserves or invalidates approval
exactly as specified by contract v4. A terminal closed provider failure uses the terminal result row
above and the release evidence additionally records the public category `TOOL_PROVIDER_FAILURE`;
it is not reclassified as an authorization error.

## Locked Test Cases

### M4-78-TC-01: Authorized observation order and terminal reconciliation across lease states

- Purpose: prove current path-Workspace/resource authorization precedes trusted routing and provider
  observation on every successful path, every authorization denial has zero provider observation,
  and terminal provider truth is finalized once without stale persistence or retry.
- Steps:
  1. For provider success and each closed rejection, seed `AdmissionOutstanding` with no PostgreSQL
     observation under current-owner, current-foreign and strictly expired lease variants.
  2. For each authorized call, capture the exact sequence: authentication and current path-Workspace
     binding succeed; observation `WorkspaceResourceAuthorizer` succeeds; the trusted
     `AuthorizedExecutionBindingSnapshot` is validated and resolves only its opaque routing handle;
     then and only then `get_execution_outcome` observes with the stored logical execution ID.
  3. Run unauthenticated, path-Workspace mismatch and resource-observation-denied variants. Attempt
     reconciliation and capture resolver/provider sentinels for each denial.
  4. For expired variants, race two recovery owners and a delayed stale owner, then restart both
     stores independently.
- Expected results:
  - Every authorized trace is exactly `path-Workspace/resource observation authorization succeeds
    -> trusted snapshot routing -> provider observation`; provider observation is the first external
    call and uses the stored logical execution ID.
  - Every authorization failure returns before trusted routing/provider access and records exactly
    zero trusted-resolver, provider-observation, `create_ticket`, dispatch and provider-effect calls.
  - Current owner finalizes; current foreign lease returns `ExecutionInProgress` without writes.
  - No write occurs under an expired lease. Exactly one takeover increments generation once and
    records/finalizes the exact immutable outcome under its new lease; all other owners are fenced.
  - Provider lookup occurs once on each authorized path, `create_ticket`/retry count is zero and
    every public result matches the immutable matrix.
- Evidence to capture: per-authorized ordered path-Workspace/resource-authorization, trusted-routing
  and provider-observation trace; per-denial trace and zero resolver/provider-observation/write/effect
  counters; lease/generation rows; contender counters; application/HTTP projections; independent
  SQLite/PostgreSQL restart snapshots.

### M4-78-TC-02: NoAdmission not-found to first freshly authorized admission

- Purpose: prove not-found is non-terminal and neither it nor observation-routing authority can
  authorize an early or unauthorized write.
- Steps:
  1. Reconcile a `NoAdmission` not-found seed before lease expiry.
  2. Cross strict expiry using PostgreSQL time, race contenders and allow full current write checks
     independently of the valid observation snapshot.
  3. Inspect the winning takeover, admission, envelope, provider ledger/effect and loser counters.
- Expected results:
  - Not-found is `ProviderOutcomeNotFound` HTTP 202 and remains `executing`; pre-expiry takeover is
    `ExecutionNotStale` at the store seam.
  - One post-expiry contender changes owner/generation/deadline, reruns current `m4r1`, write
    Workspace/resource, `ExecutionAuthorizer` and exact compatibility checks, creates one first
    admission and dispatches once with the original logical ID/fingerprint.
  - The snapshot supplies only trusted routing. No snapshot field or provenance satisfies a write
    check; losers make zero provider calls and not-found is never stored as failed.
- Evidence to capture: public projection; PostgreSQL clock/CAS trace; fresh write-authority decisions
  distinct from snapshot fields; admission/envelope digests; provider counters.

### M4-78-TC-03: AdmissionOutstanding replay versus delayed original

- Purpose: prove recovery replays one persisted admission and cannot duplicate an external effect.
- Steps:
  1. Seed `AdmissionOutstanding` with provider not-found and expire the lease.
  2. Race takeover contenders, authorized replay and the delayed original dispatch.
  3. Restart SQLite and compare admission/envelope/outcome/effect identities.
- Expected results:
  - One takeover wins; no admission is created or replaced.
  - Replay is byte-identical and retains logical ID/fingerprint.
  - Same-ID/same-fingerprint provider idempotency yields at most one logical effect; stale owners
    cannot observe or finalize.
- Evidence to capture: admission/envelope digests; contender counters; provider ledger/effect rows;
  stale-owner fencing trace.

### M4-78-TC-04: Observation snapshot is never write authority

- Purpose: prove observation/finalization authority is structurally separate from retry/write
  authority while preserving allowed finalization after expiry or key revocation.
- Steps:
  1. With current observation authorization, reconcile success and every closed rejection after
     proposal/reference expiry and separately after reference-key revocation.
  2. Deny each observation-authorization variant and prove denial before trusted routing and provider
     lookup.
  3. For a provider-not-found execution, retain a valid trusted snapshot and keep observation
     authorization valid. Independently make current write authority absent, expired, revoked or
     denied at each of: `m4r1`, write Workspace/resource authorization, `ExecutionAuthorizer` and
     exact capability/binding/policy compatibility.
  4. After each authorized observation returns not-found, record exactly one provider-observation
     lookup and its provider-ledger read, then attempt every retry/write seam: retry decision,
     admission creation or reuse, dispatch and gateway `create_ticket`. Separately capture target
     lookup, provider-ledger mutation and provider-effect counts. Prove no snapshot field/provenance
     is accepted as write-authorizer input or result.
  5. Repeat with missing/mismatched trusted routing and all nine material mismatches; reload
     proposal/approval/execution/audit state.
- Expected results:
  - Every expiry/key-revocation terminal case finalizes with exact matrix fields and zero provider
    write.
  - Every observation denial occurs before trusted routing/provider lookup and has zero provider
    observation and write/effect calls.
  - In every valid-snapshot/current-write-denied row, observation routing remains usable and returns
    not-found through exactly one authorized provider-observation lookup and provider-ledger read.
    Retry is denied and new/reused admission, dispatch, `create_ticket`, target lookup,
    provider-ledger mutation and provider-effect counts are each exactly zero.
  - Only fresh current `m4r1`, write Workspace/resource authorization, `ExecutionAuthorizer` and
    exact compatibility can authorize retry. No identity, digest, field or provenance from
    `AuthorizedExecutionBindingSnapshot` is accepted as write authority.
  - Temporary write denial preserves approved provenance; material mismatch is stale/non-executable
    and requires new proposal/approval. Missing/mismatched routing is sanitized typed non-terminal
    and never `failed`.
- Evidence to capture: expiry/revocation terminal matrix; observation-denial order/zero counters;
  valid-snapshot/current-write-denial differential matrix proving one authorized provider-
  observation lookup/ledger read and zero admission/dispatch/create-ticket/target-lookup/provider-
  ledger-mutation/provider-effect counts; snapshot-field exclusion from write-authorizer inputs;
  proposal/approval before-after state; mismatch matrix; sanitized routing-fault results.

### M4-78-TC-05: PostgreSQL-time takeover and stale-owner fencing

- Purpose: prove lock waiting and host-clock skew cannot alter the atomic winner.
- Steps:
  1. Start takeover, observation and finalization operations before the lease boundary and block on
     the execution row.
  2. Use an independent PostgreSQL session to keep or cross the boundary, release the lock and
     capture the operation's fresh post-lock database time.
  3. Race current, stale, changed-generation, foreign-owner and already-terminal callers, including
     a stale-terminal provider outcome.
- Expected results:
  - Only fresh post-lock PostgreSQL time decides strict expiry.
  - Dispositions are only `ExecutionNotStale`, one Applied takeover, `ExecutionFenced`,
    `ExecutionInProgress` or persisted terminal outcome.
  - Generation increments once; winner alone records/finalizes and stale/losing writes are absent.
- Evidence to capture: clock tuples; lock order; lease/generation rows; operation-correlated writes.

### M4-78-TC-06: Closed provider observation and HTTP result matrix

- Purpose: prove all provider observations have exact safe public semantics.
- Steps:
  1. Inject unavailable, timeout, malformed/unknown, not-found, success and every closed rejection.
  2. Compare application and decoded HTTP result, status, complete recursive key sets and value
     domains to the independent matrix.
  3. Inject forbidden private fields and reload lifecycle/terminal state.
- Expected results:
  - The independent closed matrix has a separate row for unavailable, timeout, malformed/unknown
    and not-found. Unavailable is `ReconciliationIndeterminate` 202 with
    `reason_code=provider_observation_unavailable`; timeout uses
    `reason_code=provider_observation_timeout`; malformed/unknown uses
    `reason_code=provider_observation_malformed`; not-found is the distinct
    `ProviderOutcomeNotFound` 202 with `reason_code=provider_outcome_not_found`.
  - Each of those four rows keeps lifecycle `executing`, grants no retry authority, has the exact
    complete allowlisted key set and must compare recursively field-for-field so no row can collapse
    into another.
  - Success is `ReconciledSucceeded` 200. Each closed rejection is `ReconciledFailed` 502 with
    `TOOL_PROVIDER_FAILURE` category and exact rejection code.
  - No extra/private field appears and forbidden-field injection fails closed.
- Evidence to capture: independent closed matrix digest; separate unavailable, timeout,
  malformed/unknown and not-found application/HTTP bodies with exact reason codes and recursive key
  comparisons; lifecycle/retry/terminal deltas; forbidden-field results.

### M4-78-TC-07: Two crash windows, authority separation and independent restarts

- Purpose: prove crash recovery converges without duplicate effects and no-receipt retry cannot use
  observation snapshot provenance as write authority.
- Steps:
  1. Trigger provider-commit-before-Knora-persist for success and each closed rejection.
  2. Trigger executing-persist-before-provider-receipt with a valid observation snapshot.
  3. Restart Knora and SQLite independently, expire the original lease and repeatedly reconcile.
  4. For no-receipt, keep observation routing valid while denying current write authority and
     attempt every retry/write seam. Then separately grant all fresh current write checks and retry
     with the same logical identity.
- Expected results:
  - Committed outcome follows the authorized observation order, one takeover when stale,
    exact-result finalization and zero retry/duplicate.
  - No-receipt stays non-terminal while write authority is denied despite its valid observation
    snapshot; new/reused admission, dispatch, `create_ticket` and provider-effect counts are zero.
  - Only after every fresh current write check passes does safe takeover/retry reuse one logical
    ID/fingerprint and produce at most one effect.
  - Repeated reconciliation returns the same durable terminal or non-terminal result.
- Evidence to capture: named crash records; restart snapshots; identity/admission lineage;
  valid-snapshot/write-denial differential trace; provider ledger/effect/retry counters.

### M4-78-TC-08: Audit reconstruction and secret exclusion

- Purpose: prove recovery remains reconstructable while external truth stays provider-owned.
- Steps:
  1. Restart both stores after the preceding cases.
  2. Reconstruct each recovery timeline from PostgreSQL append-only audit and compare sequence/fields.
  3. Read SQLite truth independently and recursively scan public/audit evidence for forbidden data.
- Expected results:
  - Audit reconstructs authority decisions, binding snapshot, generations, leases, observations,
    retry decisions, fencing and terminal result in order.
  - SQLite remains independently authoritative for provider outcome/idempotency.
  - No raw routing, envelope, key, credential, authority secret or internal exception appears.
- Evidence to capture: ordered audit timelines; comparison table; independent provider rows;
  forbidden-field scan.

### M4-78-TC-09: Tested-subject verification and evidence publication

- Purpose: prove M4.4 and all accepted regressions are green on the exact tested subject, then prove
  the generated evidence has a separately auditable non-self-referential publication commit.
- Steps:
  1. Record `tested_subject_commit`, recreate/migrate PostgreSQL and run the exact focused command.
  2. Recreate/migrate again and run the exact full suite serially, then run Ruff, Compose config and
     downgrade/re-upgrade/current against that same subject.
  3. Verify the sole generated dirty path is the release-evidence file, commit only it as
     `evidence_publication_commit`, and record the separate final delivery head.
- Expected results:
  - Every command exits zero with exact totals recorded; M1-M3 and M4.1-M4.3 stay green.
  - Alembic returns to head; the pre-publication worktree is clean except for the generated evidence,
    and the post-publication worktree is clean.
  - Evidence `subject_sha` and `scope_manifest.candidate` equal `tested_subject_commit`; the
    publication commit is a descendant with only the evidence-file diff and is separately bound to
    the result's final delivery head.
- Evidence to capture: tested subject, evidence-publication and delivery-head SHAs; commands/exits/totals;
  migration revisions; pre/post-publication status and exact diff paths.

### M4-78-TC-10: Static registry and no-plugin/no-vendor tested-subject scope

- Purpose: prove functional success did not expand the provider/capability scope.
- Steps:
  1. Resolve the production registry, compare exact identity/version/digest and the typed
     `ticket_lookup`/`create_ticket` descriptors before and after restart.
  2. Probe every production application/HTTP composition surface for runtime registration,
     discovery, plugin loading, request-controlled provider selection and vendor-specific adapters.
  3. Generate a content-addressed changed-path/dependency/entry-point/architecture manifest from
     source base `1cbf7d5f64bc94bd4d9313c2cf0fef46237b59e1` to the tested subject, then separately
     verify the evidence-publication commit changes only the release-evidence path.
- Expected results:
  - Registry is immutable and exactly allowlisted with no registration/discovery/plugin operation.
  - `SupportToolGateway` stays provider-generic; fake/SQLite are the only M4 provider adapters.
  - The subject manifest binds source base and tested subject and proves no marketplace, vendor
    SDK/configuration or vendor-specific integration was introduced; the publication diff proves
    the later evidence commit did not add executable scope.
- Evidence to capture: registry projection/restart digest; composition probe matrix; tested-subject
  scope manifest; source-base/tested-subject/publication/delivery SHAs and publication diff paths.

This guide becomes immutable only after external review `APPROVE` and explicit human approval of
its exact digest. Any semantic change creates a new guide revision. Store every run separately in
`.agents/manual-tests/milestone-4/78-crash-recovery-v2.evaluations.jsonl`.
