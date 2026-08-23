# Manual Test Guide: M4.1 ticket lookup v2

## Metadata

- Feature: Milestone 4 — Tools and human approval
- Slice: Issue #75 — read-only ticket lookup with pre-gateway authorization
- Authoritative specification: GitHub Issue #75 and
  `docs/design/milestone-4-tools-human-approval.md` reviewed at
  `5ffb59d2bbc4175a40cda12e714851d6c1e83cb0`
- Guide revision: `m4-75-ticket-lookup-v2`
- Supersedes: unapproved `m4-75-ticket-lookup-v1` after external `REQUEST_CHANGES`
- External review evidence: `.agents/review/m4-issue-75-guide-external-review-v2.json`
- Human approval evidence: `.agents/review/m4-issue-75-guide-approval-v2.json`
- Lock rule: this exact guide digest becomes immutable only when both evidence records approve it;
  absence of either record keeps implementation blocked

## Prerequisites

- Execute only on the exact candidate commit recorded in the Evaluation and from a clean worktree.
- Use Windows-safe database binding
  `KNORA_DATABASE_URL=postgresql+psycopg://knora:knora@127.0.0.1:5432/knora`.
- Resolve Python as `D:\Developer\Projects\knora-agent\.venv\Scripts\python.exe` and record its
  version. Docker project `m4-integration` supplies PostgreSQL.
- The exact clean-database command is `docker compose -p m4-integration exec -T postgres psql -U
  knora -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
  WHERE datname='knora' AND pid <> pg_backend_pid()" -c "DROP DATABASE IF EXISTS knora" -c
  "CREATE DATABASE knora OWNER knora"`.
- Use deterministic trusted fixtures: Workspace `workspace-a`, a second Workspace, ephemeral
  test-only HMAC keys, trusted reference store, counting fake gateway and temporary SQLite file.
  Ephemeral key values/MAC bytes are never acceptance evidence.
- Seed ticket fixture `ticket-fixture-75` under the authorized external scope with exact allowlisted
  result: title `Cannot sign in`, status `open`, summary
  `Customer cannot complete SSO sign-in.`
- Record exact commands/exit codes, sanitized typed requests/responses, call counts, SQLite file
  identity, subject SHA and clean status. Never record HMAC material, credentials, raw provider IDs
  or SDK objects.
- The candidate Evaluation must include a unique run ID, guide revision, exact subject SHA,
  environment revision (Windows/Python/PostgreSQL/Alembic/SQLite schema), every case ID/outcome and
  evidence reference, overall verdict and `human_approval` status. Only the final explicitly approved
  schema-v1 record is appended with `record_evaluation.py`.

## Locked Test Cases

### M4-75-TC-01: Static capability performs one exact typed lookup

- Purpose: prove the authorized path calls the intended resource exactly once and returns no provider
  internals.
- Steps:
  1. Resolve known and unknown capability IDs from the static registry.
  2. Reset the counting fake and execute one authorized `ReadTool` lookup for `ticket-fixture-75`.
  3. Capture the sanitized `LookupTicketRequest` and serialized result.
- Expected results:
  - Exactly one versioned static descriptor resolves; unknown ID fails without dynamic loading.
  - Gateway call count is exactly one. The request carries the exact authorized scope-binding
    identity/version/digest and authorized resource claims/reference ID for `ticket-fixture-75`, with
    no raw provider ID.
  - The result is exactly `{title: Cannot sign in, status: open, summary: Customer cannot complete
    SSO sign-in.}` plus its opaque ticket reference and no other fields.
- Evidence to capture: registry outcome, one sanitized typed request, exact result and call count.

### M4-75-TC-02: Authorization denial matrix has zero gateway calls

- Purpose: prove authorization precedes external lookup and prevents existence leakage.
- Steps:
  1. Exercise missing authentication, path-Workspace mismatch, unauthorized Workspace, missing
     binding and binding-scope mismatch with a reset counter per case.
  2. Capture the public envelope and call count after every request.
- Expected results:
  - Missing authentication is `401/UNAUTHENTICATED`; path/current Workspace denial is
    `403/WORKSPACE_ACCESS_DENIED`; resource/scope denial is
    `403/TOOL_RESOURCE_ACCESS_DENIED`.
  - No response reveals ticket existence and every gateway call count is zero.
- Evidence to capture: named request/status/error-code matrix and zero-call assertions.

### M4-75-TC-03: m4r1 integrity and key lifecycle fail closed

- Purpose: reject forged, stale or untrusted references before provider identity resolution.
- Steps:
  1. Verify exact active-key and still-valid retiring-key references.
  2. Independently mutate MAC, Workspace, capability version, binding digest and resource claims.
  3. Exercise malformed payload, expired token, unknown/revoked key and missing/mismatched trusted
     reference-store record.
- Expected results:
  - Only exact unexpired active/retiring references reach current resource authorization.
  - Malformed syntax is `400/INVALID_TOOL_RESOURCE_REFERENCE`; integrity/scope failures are
    `403/TOOL_RESOURCE_ACCESS_DENIED`.
  - Every rejected case has zero gateway calls and exposes no routing/provider identity or key data.
- Evidence to capture: complete named mutation matrix, safe envelopes and counters.

### M4-75-TC-04: HTTP success, validation and authorized not-found

- Purpose: verify the exact Workspace-scoped public contract.
- Steps:
  1. Call `POST /v1/workspaces/{workspace_id}/tools/ticket-lookup` for the fixed authorized fixture.
  2. Repeat with an extra field, a non-string/malformed reference and an authorized absent ticket.
- Expected results:
  - Success is 200 with the exact TC-01 result and exactly one gateway call.
  - Extra/schema-invalid input is `422/TOOL_REQUEST_INVALID`; malformed reference is
    `400/INVALID_TOOL_RESOURCE_REFERENCE`.
  - Authorized absence is `404/TOOL_TICKET_NOT_FOUND`, distinct from authorization denial.
- Evidence to capture: request/status/error matrix, exact success body and call counts.

### M4-75-TC-05: Closed read-provider outcomes use the locked mapping

- Purpose: prevent the evaluator from inventing error semantics.
- Steps:
  1. Return each typed provider outcome from an otherwise-authorized one-call lookup.
  2. Capture the sanitized public response and confirm no internal/vendor fields escape.
- Expected results:
  - `provider_scope_denied -> 403/TOOL_RESOURCE_ACCESS_DENIED`.
  - `provider_resource_not_found -> 404/TOOL_TICKET_NOT_FOUND`.
  - `provider_unavailable` or read timeout `-> 502/TOOL_PROVIDER_UNAVAILABLE`.
  - `provider_contract_invalid` or unknown/malformed read response
    `-> 502/TOOL_PROVIDER_CONTRACT_INVALID`.
  - Each attempt calls the gateway exactly once; no error is presented as a ticket.
- Evidence to capture: exact typed-outcome/status/error-code table, bodies and one-call assertions.

### M4-75-TC-06: SQLite provider lookup survives restart with exact oracle

- Purpose: prove external read semantics using provider state independent from Knora.
- Steps:
  1. Seed the fixed fixture in a temporary SQLite provider database.
  2. Perform one authorized lookup; capture sanitized typed request, exact result and call count.
  3. Recreate the adapter from the same file and repeat once.
  4. Attempt the same provider resource under another scope and inspect dependencies.
- Expected results:
  - Before and after restart, each lookup has exactly one call, the same sanitized scope/resource
    request and the exact TC-01 result.
  - Cross-scope lookup is denied and the adapter never accesses PostgreSQL `ToolActionStore`.
- Evidence to capture: SQLite identity, two exact requests/results/counters, scope denial and
  dependency assertion.

### M4-75-TC-07: Governed verification and no-write slice boundary

- Purpose: prove regression safety and that the read slice grants no write authority.
- Steps:
  1. Set the pinned database URL and resolve `$python` as declared above.
  2. Recreate database `knora` through `docker compose -p m4-integration exec -T postgres psql`, then
     run `Push-Location backend; & $python -m alembic upgrade head; Pop-Location`.
  3. Run focused M4.1 tests, then `& $python -m pytest` and
     `& D:\Developer\Projects\knora-agent\.venv\Scripts\ruff.exe check .` from repository root.
  4. Run `docker compose config --quiet` and repeat clean database recreation plus Alembic upgrade.
  5. Inspect exact candidate diff and final status.
- Expected results:
  - Every command exits 0, all tests pass and the worktree is clean.
  - Changed production scope has no external write, proposal, decision, execution or approval
    authority; M1–M3 behavior stays green.
- Evidence to capture: exact invocations/exit summaries, test totals, migration head, diff inventory
  and clean status.

Observations belong to
`.agents/manual-tests/milestone-4/75-ticket-lookup-v2.evaluations.jsonl`. Build the candidate
Evaluation with `human_approval: pending`; after explicit approval, append one final approved record
through the manual-acceptance recorder. This guide is otherwise immutable.
