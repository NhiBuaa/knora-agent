# Manual Test Guide: M4.3 authorized execution v2

## Metadata

- Feature: Milestone 4 — Tools and human approval
- Slice: Issue #77 — authorized `create_ticket` execution
- Authoritative specification: GitHub Issue #77 and
  `.agents/review/m4-issue-77-revision-v8.md` at contract commit
  `478992d3a18ae85832cb3c355c772a8cea08a03c`
- Ticket external review: `.agents/review/m4-issue-77-ticket-external-review-v8.json`, `APPROVE`
  with zero findings against subject `fc4c9e7431f19da31bf99e4be4b72c09213c0a75`
- Guide revision: `m4-77-authorized-execution-v2`
- Test-case source: `.agents/review/m4-issue-77-test-cases-v2.json`
- Prior guide review: `.agents/review/m4-issue-77-guide-external-review-v1.json`,
  `REQUEST_CHANGES` with 3 Major findings and no Critical or Minor findings
- External guide review evidence: pending `.agents/review/m4-issue-77-guide-external-review-v2.json`
- Human approval evidence: pending `.agents/review/m4-issue-77-guide-approval-v2.json`
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
  retiring-to-revoked transition fixtures. Each fixture must expose only its sanitized key
  ID/version, lifecycle and typed epoch; raw key/MAC/envelope bytes, credentials and raw provider
  routing identifiers must never enter public or audit evidence.
- Install explicit per-contender counting `SupportToolGateway` and provider sentinels. A zero-call
  assertion is valid only when the exact sentinel identity and per-contender count appear in the
  release evidence.
- Compose deterministic non-runtime barriers/fault adapters for acquisition writes, admission
  locks, PostgreSQL commit acknowledgement, post-admission/pre-gateway, SQLite pre-commit,
  SQLite-commit/pre-ack, provider observation and generation-1 lease expiry. Mutation and trusted
  signing adapters must be unreachable through production HTTP/application dependency injection.
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
  write retry/replay authorization, stale takeover and generation 2+ must remain absent from this
  composition; direct read-only provider contract observation in TC-08 is not reconciliation.
- The production composition must expose only the closed static typed capability registry. The
  release harness must compare its exact capability ID/version/operation projection to the locked
  allowlist and probe that runtime capability/provider registration, discovery and plugin loading
  are unavailable without relying on source-file or file-name inspection.
- The candidate Evaluation uses a unique run ID, this guide revision/digest, exact subject SHA,
  environment revision, all twelve case results/evidence references, overall verdict and
  `human_approval: pending`. Append through `record_evaluation.py`; after explicit result approval,
  append a separate approved record and never rewrite history.

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
  - Temporary authority denial preserves exact `approved` state and approval
    identity/version/digest.
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

- Purpose: close every acquisition-to-admission TOCTOU window.
- Steps:
  1. Acquire and block immediately before private admission authorization.
  2. Independently change Workspace/resource/execution authority and every capability/binding/
     policy selector using real typed epoch-advancing mutation adapters.
  3. Independently corrupt canonical bytes, MAC and protected claims; delete/replace/mismatch the
     trusted-store record.
  4. Run the complete key-lifecycle matrix after locking: active exact key, retiring exact key,
     revoked key, unknown key, unavailable trusted key store, active-to-retiring transition and
     retiring-to-revoked transition. Capture post-lock key ID/version and typed epoch for every row.
- Expected results:
  - Admission reloads each current fact after acquiring its locks and observes every lifecycle row.
  - Active exact and retiring exact rows admit exactly once when every other fact is compatible;
    the admission binds the post-lock key ID/version and epoch and makes exactly one provider call.
  - Revoked, unknown and unavailable rows persist no admission and make zero gateway/provider calls.
  - Active-to-retiring mutation-first remains admissible under the retiring key; retiring-to-revoked
    mutation-first denies. Admission-first binds the prior key state under the TC-04 epoch rule.
  - Only sanitized evidence is appended; no caller assertion or raw key/MAC/envelope is accepted.
- Evidence to capture: full authority/mutation/integrity/trust/key admit-or-deny matrix, post-lock
  key ID/version and epoch, lock/reload order, per-row admission/audit/provider counts and
  sanitized-evidence scan.

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
  2. Restart PostgreSQL, rotate the active issuance key and reload the exact stored envelope bytes.
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
  3. Resume dispatch and compare the gateway input with the persisted admission.
- Expected results:
  - Exactly one gateway call carries the original byte-identical envelope and intent.
  - No current fact is reread to cancel, replace, upgrade or retarget the dispatch.
  - Later lease expiry may fence only Knora observation/finalization.
- Evidence to capture: original/sent envelope digest, mutation/expiry matrix, gateway input and exact
  call count.

### M4-77-TC-07: Provider-owned atomic effect, rejection and idempotency ledger

- Purpose: prove real external-side-effect semantics at the independent SQLite provider boundary.
- Steps:
  1. Through the private harness, deliver same-ID/same-fingerprint replay and two independently valid
     same-ID/different-fingerprint envelopes; separately tamper and cross-bind an envelope.
  2. Parameterize success, `target_not_found`, `validation_rejected` and `policy_rejected`.
  3. For each outcome, inject pre-commit and committed-before-ack faults, close/reopen the SQLite
     provider and replay equal fingerprint.
- Expected results:
  - Equal fingerprint replays one effect/outcome. Both valid unequal fingerprints pass integrity
    and recomputation, then the second conflicts before target lookup/mutation with no second effect.
  - Tampering rejects before SQLite mutation.
  - Each closed rejection atomically owns one exact logical-ID/fingerprint/admission-digest ledger
    row, zero ticket/target effects, pre-commit rollback absence and restart-stable replay.
- Evidence to capture: SQLite effect/ledger rows before/after restart, fingerprint recomputation,
  lookup/mutation ordering, conflict/tamper results and one record per closed rejection.

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
  3. Inspect provider observer/dispatcher, admissions, generation and recovery authority counters.
- Expected results:
  - Both calls return current `ExecutionInProgress` and preserve the exact seed.
  - #77 performs no provider observation, first/replacement admission, dispatch/replay, retry
    authorization, takeover or generation increment.
- Evidence to capture: seed projection/reload table, typed repeated-execute result and every zero
  behavior counter.

### M4-77-TC-10: Generation-1 fencing and sanitized public result matrix

- Purpose: prevent expired-owner finalization and private admission leakage.
- Steps:
  1. Start with provider-only success and each closed rejection, no PostgreSQL observation and
     lifecycle `executing`; cross lease expiry. Immediately before blocked finalization capture the
     execution row, ordered observation/audit IDs and counts, their stable field/digest projection
     and the owner-correlated PostgreSQL write trace.
  2. Invoke observation and finalization as the expired generation-1 owner under lock barriers,
     then recapture the same projections and correlated writes.
  3. Repeat before expiry for allowed terminal mappings and exercise indeterminate, provider-
     fingerprint conflict and fenced application/HTTP results.
  4. Compare the complete application projection and decoded HTTP body to the discriminated
     allowlist; inject every forbidden private field recursively.
- Expected results:
  - Each expired operation uses fresh post-lock PostgreSQL time and returns `ExecutionFenced`.
    The execution row is unchanged; no observation row, audit row or other PostgreSQL write is
    appended by the expired owner; ordered IDs/counts and the stable row-set digest remain exact.
    Provider truth remains readable after restart.
  - Before-expiry success becomes `succeeded`; only the three named rejections become `failed`;
    indeterminate is executing/202 and conflict is executing/409 with no retry authority.
  - Common public fields are exactly `proposal_id`, `logical_execution_id`, `lifecycle` and
    `outcome_type`; only the contract-approved variant field is added. No extra recursive field,
    raw provider/routing, admission/envelope/MAC/fingerprint, authority, key/signing, credential or
    secret material is accepted or emitted.
- Evidence to capture: post-expiry execution-row snapshot, ordered observation/audit identities and
  counts, stable PostgreSQL row-set digest, owner-correlated zero-write trace, provider restart
  record, complete application/HTTP allowlist matrix and forbidden-field failures.

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

### M4-77-TC-12: Governed focused, regression and migration verification

- Purpose: prove the exact candidate and release evidence satisfy #77 without M1–M3 regression.
- Steps:
  1. Instantiate the production application composition, project the registry through its public
     typed resolver/descriptors and compare exact ordered capability ID/version/operation entries
     with the locked closed allowlist.
  2. Probe every production application/HTTP composition surface for runtime capability/provider
     registration, capability/provider discovery and plugin loading. Record structural absence or
     typed unsupported results plus unchanged registry/state/provider counters; generic source-text
     or file-name assertions are invalid evidence.
  3. Record subject SHA/clean status, recreate/migrate PostgreSQL and run the exact focused command.
  4. Recreate/migrate PostgreSQL, run the exact full suite serially, Ruff and Compose.
  5. Recreate/migrate once more, record Alembic head, validate the release-evidence JSON covers
     TC-01 through TC-11 and inspect final clean status.
- Expected results:
  - The production registry exactly equals the closed typed allowlist and exposes no runtime
    registration, discovery or plugin-loading operation; probes make zero state/provider changes.
  - Every command exits 0, all focused cases and M1–M3 regressions pass, and PostgreSQL reaches the
    single current Alembic head.
  - The sanitized release evidence is bound to the exact candidate/environment and all required
    case IDs; the candidate worktree is clean.
- Evidence to capture: production registry projection/allowlist comparison, runtime boundary probe
  results, before/after registry/state/provider counters, exact commands/exits/totals,
  release-evidence digest, migration head, subject SHA and clean status.

Observations belong to
`.agents/manual-tests/milestone-4/77-authorized-execution-v2.evaluations.jsonl`. Append a candidate
record with `human_approval: pending`; after explicit result approval append a separate approved
record. This guide becomes immutable only after its externally reviewed digest receives explicit
human lock approval.
