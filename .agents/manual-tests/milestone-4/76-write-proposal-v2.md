# Manual Test Guide: M4.2 write proposal v2

## Metadata

- Feature: Milestone 4 — Tools and human approval
- Slice: Issue #76 — immutable write proposal and human approval boundary
- Authoritative specification: GitHub Issue #76 and
  `docs/design/milestone-4-tools-human-approval.md` reviewed at
  `5ffb59d2bbc4175a40cda12e714851d6c1e83cb0`
- Guide revision: `m4-76-write-proposal-v2`
- Supersedes: unapproved `m4-76-write-proposal-v1` after external `REQUEST_CHANGES`
- External review evidence: `.agents/review/m4-issue-76-guide-external-review-v2.json`
- Human approval evidence: `.agents/review/m4-issue-76-guide-approval-v2.json`
- Lock rule: this exact guide digest becomes immutable only when both evidence records approve it;
  absence of either record keeps implementation blocked

## Prerequisites

- Execute only on the exact candidate commit recorded in the Evaluation and from a clean worktree.
- Use Windows-safe database binding
  `KNORA_DATABASE_URL=postgresql+psycopg://knora:knora@127.0.0.1:5432/knora`.
- Resolve Python as `D:\Developer\Projects\knora-agent\.venv\Scripts\python.exe`; Docker project
  `m4-integration` supplies PostgreSQL.
- The exact clean-database command is `docker compose -p m4-integration exec -T postgres psql -U
  knora -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
  WHERE datname='knora' AND pid <> pg_backend_pid()" -c "DROP DATABASE IF EXISTS knora" -c
  "CREATE DATABASE knora OWNER knora"`.
- Use deterministic trusted fixtures for two Workspace principals, human/model/system contexts,
  approval policy, clock, active/retiring/revoked ephemeral test keys, trusted reference store and
  narrow fake `CapabilityResolver`. Ephemeral key/MAC bytes are never acceptance evidence.
- Use a counting provider-write sentinel that fails a case if any external write is attempted.
- Record exact commands/exit codes, sanitized responses, database projection/audit row counts, exact
  subject SHA and clean status. Never record key/MAC material, credentials or raw provider IDs.
- The candidate Evaluation must include unique run ID, guide revision, exact subject SHA, environment
  revision (Windows/Python/PostgreSQL/Alembic), every case ID/outcome/evidence reference, overall
  verdict and `human_approval` status. Only the final explicitly approved schema-v1 record is appended
  with `record_evaluation.py`.

## Locked Test Cases

### M4-76-TC-01: Canonical immutable proposal derives trusted provenance

- Purpose: prove the server owns identity, provenance and approved intent.
- Steps:
  1. Create one authorized proposal using an exact valid target reference and valid title/description.
  2. Reload and inspect application/HTTP projections, resolver interaction and provider sentinel.
- Expected results:
  - Caller and proposal actor derive from trusted context and remain distinct.
  - Server stores normalized parameters, exact capability/binding/policy/reference provenance, new
    proposal/logical IDs, canonical digest and policy expiry.
  - Projection exposes no raw provider ID, routing handle, key/MAC material or internal persistence
    field; provider-write count is zero.
- Evidence to capture: sanitized create/read projections, provenance/digest comparison, resolver
  request/result and zero-write assertion.

### M4-76-TC-02: Input and m4r1 target-reference matrices fail before persistence

- Purpose: prevent spoofed authority, ambiguous parameters and unverified targets from becoming a
  proposal.
- Steps:
  1. Exercise absent/non-string/empty/over-limit/NUL/leading-trailing-whitespace title/description,
     canonical Unicode/LF equivalents and every forbidden actor/authority/digest/provider/logical-ID
     extra field.
  2. Exercise malformed reference syntax, tampered MAC, expired reference, unknown/revoked key,
     Workspace/capability/binding/resource claim mismatch and missing/mismatched trusted-store record.
  3. Inspect response, proposal/decision/audit counts, resolver/gateway counters and projection fields.
- Expected results:
  - Schema/parameter/extra-field/invalid reject-reason input is `422/TOOL_REQUEST_INVALID` before
    persistence; canonical valid values yield the server-computed digest.
  - Malformed reference syntax is `400/INVALID_TOOL_RESOURCE_REFERENCE`; every authenticated
    integrity/scope/store mismatch is `403/TOOL_RESOURCE_ACCESS_DENIED` without existence leakage.
  - Every rejected target has zero proposal/decision/audit rows, zero gateway calls and no raw
    provider/key/MAC/internal reference data in any response.
- Evidence to capture: complete named input/reference matrix, safe envelopes, digest recomputation and
  zero persistence/write counters.

### M4-76-TC-03: Workspace authorization precedes proposal lookup

- Purpose: prevent cross-Workspace existence leakage or mutation.
- Steps:
  1. Exercise create/read/approve/reject without authentication and under wrong/unauthorized Workspace.
  2. As an authorized principal, read and decide an absent proposal.
- Expected results:
  - Missing auth is `401/UNAUTHENTICATED`; Workspace denial is
    `403/WORKSPACE_ACCESS_DENIED` before scoped lookup.
  - Authorized absence is `404/TOOL_PROPOSAL_NOT_FOUND`.
  - Denied calls add no decision/audit row and invoke no provider write.
- Evidence to capture: route/status/error matrix, store ordering and row/call counts.

### M4-76-TC-04: Only authorized humans decide and reject reasons are closed

- Purpose: separate actors/authority without inventing blanket separation of duties.
- Steps:
  1. Attempt approve/reject from model/system and an unauthorized human.
  2. Approve as an authorized human under no-SoD policy, including same proposal actor identity.
  3. Repeat same-actor approval under explicit SoD policy.
  4. Reject fresh proposals once per valid reason `not_approved`, `incorrect_target`,
     `incorrect_parameters`, `other`, then submit an unknown reason.
- Expected results:
  - Forbidden actors receive `403/TOOL_APPROVAL_FORBIDDEN` with no decision row.
  - Authorized human succeeds when policy permits; explicit SoD denies only configured same-actor
    case and approval never grants execution authority.
  - All four closed reject reasons persist exactly; unknown reason is
    `422/TOOL_REQUEST_INVALID` before decision/audit persistence.
- Evidence to capture: actor/policy/reason matrix, decision/audit rows and zero-write assertion.

### M4-76-TC-05: Concurrent approve/reject has one durable CAS winner

- Purpose: prove atomic decision semantics without scheduler precedence.
- Steps:
  1. Release concurrent approve/reject against the same proposed revision and reload durable state.
  2. Repeat without assuming which action wins.
  3. Retry the losing and winning command through HTTP after the decision.
- Expected results:
  - Exactly one CAS commits and revision increments once; one decision/audit row exists.
  - Every loser/repeat returns `409/TOOL_PROPOSAL_ALREADY_DECIDED` with the persisted winner/revision.
  - No provider write occurs.
- Evidence to capture: concurrent results, HTTP envelopes, revision, row counts and audit sequence.

### M4-76-TC-06: Material fields and audit are immutable

- Purpose: bind the human decision to exact reviewed intent and provenance.
- Steps:
  1. Reconstruct all caller/actor/capability/binding/policy/reference/parameter/logical-ID provenance.
  2. Attempt update of every material field and update/delete of audit rows.
  3. Submit materially changed title, target and policy snapshots as replacement proposals.
- Expected results:
  - Reconstruction matches canonical digest and decision; database guards reject every mutation.
  - Each replacement has new proposal/logical IDs and no inherited approval.
- Evidence to capture: reconstruction table, database rejection reasons, ordered audit and identities.

### M4-76-TC-07: Temporary denial, stale mismatch and expiry stay distinct

- Purpose: prevent approval reuse under changed authority/binding/policy semantics.
- Steps:
  1. Temporarily revoke execution authority for an approved proposal.
  2. Independently change current capability, binding and policy identity/version/digest.
  3. Advance clock beyond expiry and invoke the new-execution projection/route for each case.
- Expected results:
  - Temporary denial leaves approved/non-stale and returns
    `403/TOOL_EXECUTION_NOT_AUTHORIZED` for execution attempt.
  - Material mismatch is non-executable and `409/TOOL_PROPOSAL_STALE` with exact safe stale reason.
  - Expiry is `409/TOOL_PROPOSAL_EXPIRED`; no case mutates material fields or writes provider state.
- Evidence to capture: lifecycle/executable/status/error/reason matrix, unchanged digest and zero write.

### M4-76-TC-08: Governed verification, narrow resolver and no provider write

- Purpose: prove #76 remains independent from #75 and adds proposal/decision behavior only.
- Steps:
  1. Set the pinned database URL and resolve `$python` as declared above.
  2. Recreate database `knora` through `docker compose -p m4-integration exec -T postgres psql`, then
     run `Push-Location backend; & $python -m alembic upgrade head; Pop-Location`.
  3. Run focused M4.2 tests, then `& $python -m pytest`,
     `& D:\Developer\Projects\knora-agent\.venv\Scripts\ruff.exe check .` and
     `docker compose config --quiet` from repository root.
  4. Repeat clean database recreation/Alembic upgrade and inspect imports, exact diff and clean status.
- Expected results:
  - Every command exits 0, all tests pass and the worktree is clean.
  - Production consumes only `CapabilityResolver`; #76 tests use its fake and do not import #75
    concrete registry/provider code.
  - Provider-write sentinel remains zero and M1–M3 behavior stays green.
- Evidence to capture: exact invocations/exits, test totals, migration head, dependency/diff inventory,
  write counter and clean status.

Observations belong to
`.agents/manual-tests/milestone-4/76-write-proposal-v2.evaluations.jsonl`. Build the candidate
Evaluation with `human_approval: pending`; after explicit approval, append one final approved record
through the manual-acceptance recorder. This guide is otherwise immutable.
