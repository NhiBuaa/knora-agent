# Manual Test Guide: M4.1 ticket lookup v1

## Metadata

- Feature: Milestone 4 — Tools and human approval
- Slice: Issue #75 — read-only ticket lookup with pre-gateway authorization
- Authoritative specification: GitHub Issue #75 and
  `docs/design/milestone-4-tools-human-approval.md` reviewed at
  `01d329e1e9aa8c0f2f667ab9df318c62ba47d047`
- Guide revision: `m4-75-ticket-lookup-v1`
- External review evidence: `.agents/review/m4-issue-75-guide-external-review-v1.json`
- Human approval evidence: `.agents/review/m4-issue-75-guide-approval-v1.json`
- Lock rule: this exact guide digest becomes immutable only when both evidence records approve it;
  absence of either record means implementation remains blocked

## Prerequisites

- Execute only on the exact candidate commit recorded in the Evaluation; the worktree is clean.
- Docker Compose dependencies are healthy and the Knora PostgreSQL database is freshly recreated and
  migrated to Alembic head before full verification.
- Use deterministic trusted fixtures: two Workspace principals, a key ring, trusted reference store,
  counting fake gateway and a temporary SQLite reference-provider path. Fixtures contain no secrets.
- The implementation supplies the dedicated tests under `backend/test/tools`,
  `backend/test/adapters/http` and `backend/test/adapters/support`; no production provider is needed.
- Record commands, exit codes, sanitized responses, call counts, SQLite path identity, exact subject
  SHA and clean status. Never record keys, MAC material, raw provider IDs or credentials.

## Locked Test Cases

### M4-75-TC-01: Static capability and allowlisted result

- Purpose: prove `ticket_lookup` is static/typed and cannot expose provider internals.
- Steps:
  1. Run the focused registry/read-contract tests for known and unknown capability IDs.
  2. Execute an authorized lookup through `ReadTool` with the counting fake gateway.
  3. Serialize the application and HTTP success projection and inventory its fields.
- Expected results:
  - Exactly one versioned static descriptor resolves; unknown IDs fail with the typed unsupported
    capability outcome and no dynamic loading occurs.
  - The result contains only opaque ticket reference, title, status and summary.
  - No raw provider ID, scope identifier, persistence field or SDK object is visible.
- Evidence to capture: focused pytest summary, descriptor projection and sanitized field inventory.

### M4-75-TC-02: Authorization denial matrix has zero gateway calls

- Purpose: prove authorization precedes external lookup and prevents existence leakage.
- Steps:
  1. Reset the fake gateway call counter.
  2. Exercise missing authentication, path-Workspace mismatch, unauthorized Workspace,
     missing binding and binding-scope mismatch.
  3. After each request, capture the safe public error and counter value.
- Expected results:
  - Authentication returns 401; authorized-context failures return non-leaking 403 outcomes.
  - No case reveals whether the external ticket exists.
  - Gateway invocation count remains zero for the complete matrix.
- Evidence to capture: named request/outcome matrix and per-case zero-call assertion.

### M4-75-TC-03: m4r1 integrity and key lifecycle fail closed

- Purpose: reject forged, stale or untrusted resource references before provider identity is resolved.
- Steps:
  1. Verify an exact reference under the active key and a still-valid retiring key.
  2. Mutate MAC, Workspace, capability version, binding digest and resource claims independently.
  3. Exercise malformed payload, expired token, unknown/revoked key and missing/mismatched trusted
     reference-store record.
  4. Capture gateway and authorizer call counts for every rejected case.
- Expected results:
  - Only exact, unexpired active/retiring references reach current resource authorization.
  - Syntax errors use the safe invalid-reference response; integrity/scope failures use non-leaking
    access denial.
  - Every rejected case has zero gateway calls and exposes no provider routing/resource identity.
- Evidence to capture: complete named mutation matrix, safe codes and call-count assertions.

### M4-75-TC-04: HTTP success, validation and authorized not-found

- Purpose: verify the locked Workspace-scoped request/response surface.
- Steps:
  1. Call `POST /v1/workspaces/{workspace_id}/tools/ticket-lookup` with one valid authorized reference.
  2. Repeat with an extra request field, a non-string/malformed reference and an authorized reference
     whose ticket is absent.
  3. Capture sanitized bodies and status codes.
- Expected results:
  - Success is 200 with the allowlisted result from TC-01.
  - Extra/schema-invalid input is 422; malformed reference is 400.
  - An authorized absent ticket is 404 and remains distinct from authorization denial.
- Evidence to capture: request/status/error-code matrix and serialized success projection.

### M4-75-TC-05: Closed provider outcomes remain distinct

- Purpose: prevent provider denial, unavailability or invalid contracts from becoming false results.
- Steps:
  1. Configure the fake gateway to return scope denial, authorized not-found, unavailability and a
     contract-invalid payload one at a time.
  2. Execute the same otherwise-authorized request for each outcome.
- Expected results:
  - Each boundary outcome maps to its declared typed/public response.
  - No internal exception, vendor body, raw provider ID or SDK object is returned.
  - None of the error outcomes is presented as a successful ticket.
- Evidence to capture: provider-outcome/public-response mapping and redaction assertions.

### M4-75-TC-06: SQLite provider read evidence survives restart

- Purpose: prove external-boundary semantics with provider state independent of Knora.
- Steps:
  1. Create a temporary SQLite provider database and seed one ticket under one external scope.
  2. Perform an authorized scoped lookup and capture the allowlisted result.
  3. Destroy/recreate the adapter with the same SQLite path and repeat the lookup.
  4. Attempt the same provider resource under another scope and inspect dependency boundaries.
- Expected results:
  - The authorized result is stable before and after adapter restart.
  - The cross-scope lookup is denied by the provider boundary.
  - The adapter does not read or write PostgreSQL `ToolActionStore` state.
- Evidence to capture: temporary provider identity, before/after results, scope denial and call-path
  assertion.

### M4-75-TC-07: Full verification and slice boundary

- Purpose: prove regression safety and that the read slice grants no write authority.
- Steps:
  1. Run all dedicated M4.1 tests, then the full repository pytest suite.
  2. Run Ruff, `docker compose config --quiet` and `alembic upgrade head` on a freshly recreated
     database.
  3. Inspect the exact candidate diff and final worktree status.
- Expected results:
  - All commands are green and the worktree is clean.
  - Changed production scope contains no external write, proposal decision, execution or approval
    authority.
  - M1–M3 authorization, retrieval, citation/refusal and ingestion behavior remains green.
- Evidence to capture: command/exit summaries, migration head, changed-scope inventory and clean
  status.

Observations append to
`.agents/manual-tests/milestone-4/75-ticket-lookup-v1.evaluations.jsonl`. The guide content becomes
immutable when the exact digest is externally reviewed and explicitly approved by the human.
