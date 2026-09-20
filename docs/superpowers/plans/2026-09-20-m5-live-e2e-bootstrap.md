# M5 Live E2E Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provision the isolated live M5 E2E Workspaces through the existing application control-plane seam and complete the blocked public user-flow proof without changing product authorization or outcomes.

**Architecture:** A test-only CLI module composes `PostgresEvaluationWorkspaceGateway` with the configured `SessionFactory` and provisions exactly the two Keycloak fixture Workspaces. The existing readiness script runs that command before browser tests. A least-privilege Keycloak identity supplies the existing deletion-request UI path; Playwright continues to use real OIDC login and public UI only.

**Tech Stack:** Python 3.12, SQLAlchemy/PostgreSQL, PowerShell Compose readiness, Keycloak realm JSON, Next.js, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-20-m5-live-e2e-bootstrap-design.md`

## Global Constraints

- Use only `PostgresEvaluationWorkspaceGateway.provision_or_reuse`; Playwright and frontend code never write internal tables.
- Provision only `m5-workspace` and `m5-other-workspace`; output only sanitized identifiers and outcomes.
- Keep Keycloak authorization-code + PKCE as the only browser login path; never fabricate a session or JWT.
- Backend remains authoritative for Workspace lookup, capabilities, ingestion, deletion, and answering.
- Preserve all existing identities; `m5-delete-user` receives only the existing document capabilities plus `documents:delete`.
- Do not add a provider mock, an operator workspace selector, or a production Workspace HTTP endpoint.
- Every behavior change follows RED → GREEN → REFACTOR, with a coherent commit per task.

---

### Task 1: Add the idempotent test control-plane bootstrap

**Files:**
- Create: `backend/src/knora/adapters/cli/m5_e2e_bootstrap.py`
- Create: `backend/test/adapters/cli/test_m5_e2e_bootstrap.py`
- Modify: `test/fixtures/keycloak/test_m5_e2e_compose.ps1`
- Test: `backend/test/adapters/cli/test_m5_e2e_bootstrap.py`

**Interfaces:**
- Consumes: `PostgresEvaluationWorkspaceGateway(session_factory).provision_or_reuse(workspace_id, name) -> str`.
- Produces: `main() -> None`, which provisions both fixed IDs and prints one JSON object with `workspaces: ["m5-other-workspace", "m5-workspace"]` and `outcome: "provisioned"`.
- The readiness script invokes `docker compose ... exec -T api python -m knora.adapters.cli.m5_e2e_bootstrap` after API readiness and fails if the command fails or emits an unexpected sanitized result.

- [ ] **Step 1: Write RED unit tests.**

```python
def test_main_provisions_exact_fixture_workspaces_idempotently(monkeypatch, capsys):
    gateway = FakeGateway()
    monkeypatch.setattr(module, "PostgresEvaluationWorkspaceGateway", lambda _: gateway)
    module.main()
    assert gateway.calls == [
        ("m5-workspace", "M5 E2E Workspace"),
        ("m5-other-workspace", "M5 E2E Other Workspace"),
    ]
    assert json.loads(capsys.readouterr().out) == {
        "outcome": "provisioned",
        "workspaces": ["m5-other-workspace", "m5-workspace"],
    }
```

- [ ] **Step 2: Run RED.**

Run: `C:\Developer\Projects\knora-agent\.venv\Scripts\python -m pytest backend/test/adapters/cli/test_m5_e2e_bootstrap.py -q`

Expected: FAIL because `knora.adapters.cli.m5_e2e_bootstrap` does not exist.

- [ ] **Step 3: Implement the smallest bootstrap.**

```python
FIXTURE_WORKSPACES = (
    ("m5-workspace", "M5 E2E Workspace"),
    ("m5-other-workspace", "M5 E2E Other Workspace"),
)

def main() -> None:
    gateway = PostgresEvaluationWorkspaceGateway(SessionFactory)
    for workspace_id, name in FIXTURE_WORKSPACES:
        gateway.provision_or_reuse(workspace_id=workspace_id, name=name)
    print(json.dumps({"outcome": "provisioned", "workspaces": sorted(id for id, _ in FIXTURE_WORKSPACES)}))
```

Do not import `WorkspaceTable`, open a SQLAlchemy session directly, read environment secrets, or add an HTTP route.

- [ ] **Step 4: Run GREEN and readiness.**

Run:

```powershell
C:\Developer\Projects\knora-agent\.venv\Scripts\python -m pytest backend/test/adapters/cli/test_m5_e2e_bootstrap.py -q
powershell -ExecutionPolicy Bypass -File test\fixtures\keycloak\test_m5_e2e_compose.ps1
```

Expected: unit tests pass; readiness reports the existing sanitized Keycloak/API proof plus the two provisioned fixture IDs.

- [ ] **Step 5: Refactor, inspect, commit.**

Run `git diff --check`, inspect only these files for secret-like output, then commit:

```text
test(m5): bootstrap isolated e2e workspaces
```

### Task 2: Add the delete-capable fixture and public browser cases

**Files:**
- Modify: `test/fixtures/keycloak/m5-realm.json`
- Modify: `test/fixtures/keycloak/test_m5_e2e_compose.ps1`
- Modify: `frontend/tests/e2e/support/auth.ts`
- Modify: `frontend/tests/e2e/m5-user-flows.spec.ts`
- Test: `frontend/tests/e2e/m5-user-flows.spec.ts`

**Interfaces:**
- Consumes: the Task 1-provisioned `m5-workspace` and the public `/app` document/question screens.
- Produces: `M5E2EIdentity` value `"delete-user"`; its credentials are read only from `M5_E2E_DELETE_USERNAME` and `M5_E2E_DELETE_PASSWORD`.
- The realm validation checks the fixture access-token claims for `documents:delete` without writing tokens to output.

- [ ] **Step 1: Write RED browser scenarios.**

Add two focused scenarios:

```ts
test("a delete-capable user requests deletion through document UI", async ({ browser }) => {
  // Real login, upload through the public UI, open the document, click Request deletion.
  // Assert the public requested state, never an immediate hard-delete.
});

test("a failed question remains failure rather than a completed answer", async ({ browser }) => {
  // Real login and question UI; assert the existing safe failure/unavailable public state,
  // and assert no completed answer/citation is rendered.
});
```

The pre-existing refusal test remains a native no-evidence assertion and must not inject a provider outcome.

- [ ] **Step 2: Run RED.**

Run (with only sanctioned `M5_E2E_*` URLs and fixture credentials):

```powershell
Set-Location frontend
npx playwright test tests/e2e/m5-user-flows.spec.ts --project=chromium --reporter=list
```

Expected: deletion scenario fails because the fixture identity and helper are absent; upload/refusal stays blocked until Task 1 readiness has provisioned the Workspace.

- [ ] **Step 3: Implement the narrow fixture/test changes.**

Add `m5-delete-user` only to the isolated realm with `workspace_id` and `workspace_ids` equal to `m5-workspace`, and capabilities `documents:read`, `documents:write`, `documents:delete`, `questions:ask`. Extend the helper's identity union, environment mapping, and expected session capability list. Extend readiness to validate the delete capability without printing its token.

Keep each test in a distinct browser context. Use public controls and public status/alert text only. Do not add product selectors, mock fetch, decode cookies, or add database setup to the browser tests.

- [ ] **Step 4: Run GREEN focused verification.**

Run:

```powershell
Set-Location frontend
npx playwright test tests/e2e/m5-user-flows.spec.ts tests/e2e/m5-operator-flows.spec.ts --project=chromium --reporter=list
npm run typecheck
npm test
git diff --check
```

Expected: user upload/serving, archive/unarchive, native refusal, deletion request, safe failure presentation, authorized operator unavailable state, and non-operator denial all pass. Cross-workspace remains covered by the existing live BFF/API auth test; no new operator selector is introduced.

- [ ] **Step 5: Refactor, inspect, commit.**

Remove duplicated browser setup only after GREEN. Inspect all changed evidence strings for credentials, cookies, token fragments, database URLs, raw exceptions, and provider payloads. Commit:

```text
test(m5): verify provisioned live user journeys
```

### Task 3: Review and resume the M5.4 release gate

**Files:**
- Modify: `.superpowers/sdd/2026-09-19-m5-live-e2e-infrastructure/progress.md`
- Modify: `.superpowers/sdd/2026-09-19-m5-live-e2e-infrastructure/task-4-report.md`
- Test: original M5.4 Task 5 command sequence (not evidence files yet)

**Interfaces:**
- Consumes: Task 1 and Task 2 commit evidence, live browser output, and the existing Task 4 report.
- Produces: a ledger record that Task 4 is complete only after focused review has no load-bearing finding; otherwise preserves the failed command and returns to its owning task.

- [ ] **Step 1: Request focused Task 1/2 review.**

Review against this spec, the original M5 live E2E spec, and the M5 workflow. Verify no direct Playwright table writes, no production endpoint, no authorization bypass, and no secret-bearing output.

- [ ] **Step 2: Resolve any review finding in its owning task.**

For each material finding, first reproduce and identify root cause, then apply one minimal fix with RED → GREEN evidence and a focused re-review. Do not self-fix in the controller session.

- [ ] **Step 3: Record Task 4 outcome.**

Append only sanitized command/result counts to `task-4-report.md` and the SDD ledger. Mark Task 4 complete only if the focused live suite and review pass; do not record Task 5 live evidence until the full release gate runs.

- [ ] **Step 4: Commit execution metadata only if it changed.**

Run `git diff --check`; commit any changed report/ledger separately:

```text
docs(m5): record live e2e bootstrap verification
```

## Stop conditions

- Stop if the named control-plane gateway cannot run against the migrated Compose database.
- Stop if the bootstrap would require raw SQL, a public Workspace creation endpoint, a fabricated token/session, or any production authorization change.
- Stop if native no-evidence answering does not produce a refusal after Workspace provisioning; record the backend failure rather than mocking it.
- Stop if a load-bearing focused review finding or test failure remains unresolved.
- Do not push, merge, delete a branch, or remove a worktree without the user's explicit integration choice.
