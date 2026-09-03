# Manual Test Guide: M4.4 crash recovery and provider reconciliation v1

## Metadata

- Feature: Milestone 4 — Tools and human approval
- Slice: Issue #78 — crash recovery and provider reconciliation
- Authoritative specification: GitHub Issue #78 and
  `.agents/review/m4-issue-78-revision-v4.md` at contract commit
  `37f1ef03c4667def8db23f1c0f5c09a725f4fd54`
- Ticket external review: `.agents/review/m4-issue-78-ticket-external-review-v2.json`, `APPROVE`
  with zero findings against packet subject `37f1ef03c4667def8db23f1c0f5c09a725f4fd54`
  (ticket digest `sha256:54ccbdce1c9bda869fa480961095db7de56df5cf5e67ef2e45d5d8fc8248d930`,
  packet digest `sha256:075dc8a13a781808a126b622859d877ba23219564c72a8abe1039d07fd30bada`).
- Guide revision: `m4-78-crash-recovery-v1`
- Test-case source: `.agents/review/m4-issue-78-test-cases-v1.json`
- External guide review evidence: pending `.agents/review/m4-issue-78-guide-external-review-v1.json`
- Human approval evidence: pending `.agents/review/m4-issue-78-guide-approval-v1.json`
- Lock rule: this exact guide digest becomes immutable only after external `APPROVE` and explicit
  repository-owner approval; implementation remains blocked until both records exist

## Prerequisites

- Execute only on the exact candidate SHA recorded in the Evaluation and from the clean Issue #78
  worktree `D:\Developer\Projects\knora-agent-worktree\issue-78-m4.4`.
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
  each closed rejection: `target_not_found`, `validation_rejected`, `policy_rejected`. Install
  separate counting sentinels for observation, `create_ticket`, target lookup, admission, retry,
  provider ledger rows and external ticket effects.
- Provide deterministic PostgreSQL execution-row barriers for takeover, observation and
  finalization. Each records operation start, transaction timestamp, lock acquisition, fresh
  post-lock PostgreSQL time, lease deadline and skewed application/non-database clocks. Host clocks
  never decide staleness.
- Provide deterministic crash barriers for provider-commit-before-Knora-persist and
  executing-persist-before-provider-receipt, plus a delayed original dispatch barrier. Fault and
  mutation adapters are test-only and cannot be selected through production application/HTTP
  composition or request input.
- Provide current observation authorization, denied observation authorization, temporary write
  authority revocation, all nine material capability/binding/policy identity/version/digest
  mismatches, proposal/reference expiry, reference-key revocation and missing/mismatched trusted
  routing fixtures. Observation authority never confers write authority.
- Load expected result, authority and audit matrices from immutable fixtures that import no
  production result type, enum, serializer, HTTP mapper or error mapper. Every row includes expected
  complete recursive key sets, value domains, status, durable before/after state and named sentinel
  counts.
- The deterministic release harness writes one sanitized
  `.agents/review/m4-issue-78-release-evidence-v1.json` bound to the exact candidate SHA, source base
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
- The candidate Evaluation uses a unique run ID, this guide revision/digest, exact subject SHA,
  environment revision, all ten case results/evidence references, overall verdict and
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
| `ProviderOutcomeNotFound` | `executing` | 202 | `provider_outcome_not_found` | `reason_code=provider_outcome_not_found` |
| `ReconciliationIndeterminate` | `executing` | 202 | `reconciliation_indeterminate` | `reason_code=provider_observation_unavailable` |
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

### M4-78-TC-01: Provider-first terminal reconciliation across lease states

- Purpose: prove terminal provider truth is finalized once without stale persistence or retry.
- Steps:
  1. For provider success and each closed rejection, seed `AdmissionOutstanding` with no PostgreSQL
     observation under current-owner, current-foreign and strictly expired lease variants.
  2. Reconcile after current Workspace/resource observation authorization and capture ordered calls.
  3. For expired variants, race two recovery owners and a delayed stale owner, then restart both
     stores independently.
- Expected results:
  - Provider observation is first and uses the stored logical execution ID.
  - Current owner finalizes; current foreign lease returns `ExecutionInProgress` without writes.
  - No write occurs under an expired lease. Exactly one takeover increments generation once and
    records/finalizes the exact immutable outcome under its new lease; all other owners are fenced.
  - Provider lookup occurs once, `create_ticket`/retry count is zero and each public result matches
    the immutable matrix.
- Evidence to capture: call-order trace; lease/generation rows; contender counters; application/HTTP
  projections; SQLite/PostgreSQL restart snapshots.

### M4-78-TC-02: NoAdmission not-found to first authorized admission

- Purpose: prove not-found is non-terminal and cannot authorize an early or unauthorized write.
- Steps:
  1. Reconcile a `NoAdmission` not-found seed before lease expiry.
  2. Cross strict expiry using PostgreSQL time, race contenders and allow full current write checks.
  3. Inspect the winning takeover, admission, envelope, provider ledger/effect and loser counters.
- Expected results:
  - Not-found is `ProviderOutcomeNotFound` HTTP 202 and remains `executing`; pre-expiry takeover is
    `ExecutionNotStale` at the store seam.
  - One post-expiry contender changes owner/generation/deadline, reruns every write check, creates
    one first admission and dispatches once with the original logical ID/fingerprint.
  - Losers make zero provider calls and not-found is never stored as failed.
- Evidence to capture: public projection; PostgreSQL clock/CAS trace; authority decisions; admission
  and envelope digests; provider counters.

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

### M4-78-TC-04: Observation authority, expiry, revocation and retry denial

- Purpose: prove observation/finalization authority is separate from write-retry authority.
- Steps:
  1. With current observation authorization, reconcile success and every closed rejection after
     proposal/reference expiry and separately after reference-key revocation.
  2. Deny observation authorization and repeat one provider lookup attempt.
  3. For not-found recovery, revoke write authority, remove/mismatch trusted routing and apply all
     nine material capability/binding/policy mismatches.
  4. Reload proposal/approval/execution/audit state.
- Expected results:
  - Every expiry/revocation terminal case finalizes with exact matrix fields and zero provider write.
  - Observation denial happens before provider lookup and grants no write authority.
  - Temporary write denial preserves approved provenance; material mismatch is stale/non-executable
    and requires a new proposal/approval.
  - Missing/mismatched trusted routing is sanitized typed non-terminal and never `failed`.
- Evidence to capture: expiry/revocation terminal matrix; zero-call counters; proposal/approval
  before-after state; mismatch matrix; sanitized routing-fault results.

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
  - Unavailable/timeout/malformed/unknown are `ReconciliationIndeterminate` 202; not-found is the
    distinct `ProviderOutcomeNotFound` 202; neither terminalizes or grants retry.
  - Success is `ReconciledSucceeded` 200. Each closed rejection is `ReconciledFailed` 502 with
    `TOOL_PROVIDER_FAILURE` category and exact rejection code.
  - No extra/private field appears and forbidden-field injection fails closed.
- Evidence to capture: independent matrix digest; per-row application/HTTP bodies; terminal deltas;
  forbidden-field results.

### M4-78-TC-07: Two crash windows and independent restarts

- Purpose: prove crash recovery converges without duplicate effects.
- Steps:
  1. Trigger provider-commit-before-Knora-persist for success and each closed rejection.
  2. Trigger executing-persist-before-provider-receipt.
  3. Restart Knora and SQLite independently, expire the original lease and repeatedly reconcile;
     allow no-receipt retry only after every current write check passes.
- Expected results:
  - Committed outcome uses provider-first lookup, one takeover when stale, exact-result finalization
    and zero retry/duplicate.
  - No-receipt stays non-terminal until safe takeover/retry and reuses one logical ID/fingerprint.
  - Repeated reconciliation returns the same durable terminal or non-terminal result.
- Evidence to capture: named crash records; restart snapshots; identity/admission lineage; provider
  ledger/effect/retry counters.

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

### M4-78-TC-09: Exact-candidate repository verification

- Purpose: prove M4.4 and all accepted regressions remain green on a clean schema lifecycle.
- Steps:
  1. Record subject SHA, recreate/migrate PostgreSQL and run the exact focused command.
  2. Recreate/migrate again and run the exact full suite serially.
  3. Run Ruff, Compose config, downgrade/re-upgrade/current and inspect Git status.
- Expected results:
  - Every command exits zero with exact totals recorded; M1-M3 and M4.1-M4.3 stay green.
  - Alembic returns to head and the worktree is clean.
- Evidence to capture: subject SHA; commands/exits/totals; migration revisions; clean status.

### M4-78-TC-10: Static registry and no-plugin/no-vendor exact-candidate scope

- Purpose: prove functional success did not expand the provider/capability scope.
- Steps:
  1. Resolve the production registry, compare exact identity/version/digest and the typed
     `ticket_lookup`/`create_ticket` descriptors before and after restart.
  2. Probe every production application/HTTP composition surface for runtime registration,
     discovery, plugin loading, request-controlled provider selection and vendor-specific adapters.
  3. Generate a content-addressed changed-path/dependency/entry-point/architecture manifest from
     source base `1cbf7d5f64bc94bd4d9313c2cf0fef46237b59e1` to the exact candidate.
- Expected results:
  - Registry is immutable and exactly allowlisted with no registration/discovery/plugin operation.
  - `SupportToolGateway` stays provider-generic; fake/SQLite are the only M4 provider adapters.
  - The manifest binds both SHAs and proves no marketplace, vendor SDK/configuration or
    vendor-specific integration was introduced.
- Evidence to capture: registry projection/restart digest; composition probe matrix; exact-candidate
  scope manifest; both SHAs.

This guide becomes immutable only after external review `APPROVE` and explicit human approval of
its exact digest. Any semantic change creates a new guide revision. Store every run separately in
`.agents/manual-tests/milestone-4/78-crash-recovery-v1.evaluations.jsonl`.
