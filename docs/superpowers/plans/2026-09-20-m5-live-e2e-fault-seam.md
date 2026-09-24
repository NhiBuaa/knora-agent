# M5.4 Live E2E Fault Seam Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make provider-failure and abruptly interrupted SSE outcomes observable through the real M5 E2E stack, then rerun the complete M5.4 release gate from an isolated worktree environment.

**Architecture:** An in-memory, one-shot controller is constructed and routed only when `KNORA_M5_E2E_FAULTS_ENABLED=true`. It binds a fixed fault scenario to one authenticated principal and Workspace; the existing stream flow consumes it only after normal authorization. Playwright configures the controller, then uses the unchanged browser UI and observes the backend-owned public state.

**Tech Stack:** FastAPI, existing `AnswerQuestion` SSE stream, Pydantic settings, pytest, Docker Compose, Next.js 15, Playwright Chromium, PowerShell virtual-environment tooling.

**Spec:** `docs/superpowers/specs/2026-09-20-m5-live-e2e-fault-seam-design.md`

## Global Constraints

- Create no production fault-injection endpoint or user-selectable question trigger.
- Mount the controller/router only when `KNORA_M5_E2E_FAULTS_ENABLED=true`; ordinary `create_app()` must not expose it.
- Authorize control setup before controller lookup or mutation, and preserve ordinary question authorization before fault consumption.
- Permit only `provider_failure` and `stream_interruption`; a script is bound to one principal/Workspace and consumed once.
- Do not add a database write, browser response interception, fabricated session/token, arbitrary provider payload, or arbitrary error code.
- Preserve public failure/refusal/citation semantics: provider failure is terminal `failure`; interruption ends after `started`, with no terminal answer/citation event.
- Create and use only `C:/Developer/Projects/knora-agent-worktree/m5-e2e-verification/.venv`; never modify the shared primary-checkout virtual environment.
- Do not push, merge, delete a branch, or remove a worktree without explicit user approval.

## File map

- Create `backend/src/knora/api/m5_e2e_faults.py`: closed scenario type, principal/Workspace-bound one-shot controller, and M5-E2E-only API router.
- Modify `backend/src/knora/infrastructure/settings.py`: typed `m5_e2e_faults_enabled: bool = False` runtime flag.
- Modify `backend/src/knora/main.py`: construct controller and mount its router only under the enabled flag; expose the controller to the existing question-stream router through application state.
- Modify `backend/src/knora/api/routes.py`: consume a matching script after normal question authorization and emit the selected backend-owned stream outcome.
- Create `backend/test/api/test_m5_e2e_faults.py`: controller, authorization-order, composition, and stream-contract regression tests.
- Modify `docker-compose.m5-e2e.yml`: set the API's M5-E2E-only fault flag; do not alter normal `docker-compose.yml`.
- Modify `frontend/tests/e2e/support/auth.ts`: add a sanitized E2E control helper that uses the authenticated test context.
- Modify `frontend/tests/e2e/m5-user-flows.spec.ts`: add live provider-failure and stream-interruption UI scenarios.
- Modify `.agents/manual-tests/milestone-5/m5-e2e.evaluations.jsonl` and `.agents/review/m5-final-verification.json` only after fresh complete gate results.

---

### Task 1: Build the isolated M5.4 Python environment and prove the baseline

**Files:**
- Create locally only: `.venv/` (ignored environment directory)
- Test: `backend/test/api/test_question_stream.py`, `backend/test/api/test_m5_contracts.py`

**Interfaces:**
- Produces a worktree-local `./.venv/Scripts/python.exe` whose editable `knora` import resolves to `C:/Developer/Projects/knora-agent-worktree/m5-e2e-verification/backend/src`.
- Does not modify the primary checkout's `.venv` or any tracked source file.

- [ ] **Step 1: Prove the current binding problem before creating the local environment.**

  Run from the M5.4 worktree:

  ```powershell
  ..\..\knora-agent\.venv\Scripts\python -c "import knora; print(knora.__file__)"
  ```

  Expected: the printed path names the primary checkout, documenting why that environment is not a valid M5.4 gate runner.

- [ ] **Step 2: Create and install the isolated environment.**

  ```powershell
  py -3 -m venv .venv
  .\.venv\Scripts\python -m pip install --upgrade pip
  .\.venv\Scripts\python -m pip install -e ".\backend[dev]"
  ```

  Do not copy the shared environment and do not install the primary checkout.

- [ ] **Step 3: Verify the local import and focused baseline tests.**

  ```powershell
  .\.venv\Scripts\python -c "import knora; print(knora.__file__)"
  .\.venv\Scripts\python -m pytest backend/test/api/test_question_stream.py backend/test/api/test_m5_contracts.py -q
  ```

  Expected: the import path names this worktree and both existing focused suites pass. Stop if dependency installation or import binding fails; record the exact environment blocker without changing global tooling.

### Task 2: Add the one-shot fault controller with RED/GREEN unit coverage

**Files:**
- Create: `backend/src/knora/api/m5_e2e_faults.py`
- Create: `backend/test/api/test_m5_e2e_faults.py`

**Interfaces:**
- Produces `M5E2EFaultScenario = Literal["provider_failure", "stream_interruption"]`.
- Produces `M5E2EFaultController.arm(*, principal: WorkspacePrincipal, scenario: M5E2EFaultScenario) -> None` and `consume(*, principal: WorkspacePrincipal) -> M5E2EFaultScenario | None`.
- `arm` rejects an already armed script for the exact principal/Workspace; `consume` returns a scenario at most once and never matches a different principal/Workspace.

- [ ] **Step 1: Write failing controller tests.**

  In `backend/test/api/test_m5_e2e_faults.py`, create fixed `WorkspacePrincipal` values for the same user/workspace, a different user, and a different workspace. Add tests with these assertions:

  ```python
  controller.arm(principal=owner, scenario="provider_failure")
  assert controller.consume(principal=other_user) is None
  assert controller.consume(principal=owner) == "provider_failure"
  assert controller.consume(principal=owner) is None
  ```

  Also assert `stream_interruption` is accepted and a duplicate `arm` for the owner raises the closed controller error. Do not add an arbitrary-string scenario test that would widen the interface.

- [ ] **Step 2: Run RED.**

  ```powershell
  .\.venv\Scripts\python -m pytest backend/test/api/test_m5_e2e_faults.py -q
  ```

  Expected: collection fails because the controller module does not exist.

- [ ] **Step 3: Implement the smallest in-memory controller.**

  Use a frozen script record keyed by the authenticated principal's stable identity and Workspace. Store no token, request body, provider data, or persistence handle. Restrict scenarios with a `Literal`/enum and make `consume` atomically remove the matching record before returning it.

- [ ] **Step 4: Run GREEN and refactor.**

  Run the focused test again. Keep the controller independent of FastAPI, database sessions, and the frontend. Add no retry or TTL policy because a one-run M5 E2E process owns its in-memory lifecycle.

- [ ] **Step 5: Commit the unit.**

  ```powershell
  git add backend/src/knora/api/m5_e2e_faults.py backend/test/api/test_m5_e2e_faults.py
  git commit -m "test(m5): add one-shot e2e fault controller"
  ```

### Task 3: Mount the guarded control surface and preserve stream semantics

**Files:**
- Modify: `backend/src/knora/infrastructure/settings.py`
- Modify: `backend/src/knora/main.py`
- Modify: `backend/src/knora/api/routes.py`
- Modify: `backend/test/api/test_m5_e2e_faults.py`
- Test: `backend/test/api/test_question_stream.py`, `backend/test/api/test_m5_authorization_matrix.py`, `backend/test/api/test_m5_e2e_faults.py`

**Interfaces:**
- `Settings.m5_e2e_faults_enabled` defaults to `False` and reads `KNORA_M5_E2E_FAULTS_ENABLED`.
- When false, `create_app()` does not include the control router and ordinary question streams have no fault-controller dependency.
- When true, `POST /m5-e2e/faults` accepts only `{ "workspace_id": "…", "scenario": "provider_failure" | "stream_interruption" }` for an authenticated caller authorized for the matching workspace.
- A matching provider script produces `event: failure` with `error_code: "PROVIDER_REQUEST_FAILED"` and `terminal: true`; a matching interruption produces `event: started` then closes without `failure`, `final_validated`, or `refusal`.

- [ ] **Step 1: Write failing composition, authorization, and stream tests.**

  Add tests that build the app with the flag false and assert the control path is 404. Build it with the flag true and assert: unauthenticated setup is rejected; cross-workspace setup is rejected before `controller.arm` is called; a valid setup arms only the caller; provider failure serialization contains the safe code and no final event; interruption has `started` and no terminal event. Reuse the repository's existing API authentication test helpers rather than forging a session.

- [ ] **Step 2: Run RED.**

  ```powershell
  .\.venv\Scripts\python -m pytest backend/test/api/test_m5_e2e_faults.py backend/test/api/test_question_stream.py backend/test/api/test_m5_authorization_matrix.py -q
  ```

  Expected: failures show the absent setting/router and absent injected stream behavior.

- [ ] **Step 3: Implement the guarded router and composition.**

  Add the boolean setting, construct the controller only under that flag, and conditionally include the dedicated router in `create_app`. The router authenticates, compares requested Workspace with the principal, requires the existing question capability, then calls `arm`. It returns a minimal acknowledgement without echoing secrets or arbitrary details.

  In `stream_question`, retain existing principal Workspace/capability checks first. Only afterward ask the controller for a matching one-shot script. Serialize provider failure through the existing `QuestionEvent` format. For interruption, yield the existing `started` event and return immediately. Do not add the control route to normal OpenAPI composition.

- [ ] **Step 4: Run GREEN and regression tests.**

  Run the three focused suites, then:

  ```powershell
  .\.venv\Scripts\python -m pytest backend/test/api -q
  .\.venv\Scripts\ruff check backend/src backend/test
  ```

  Expected: authorization-before-lookup, ordinary streams, and M5 contracts remain green.

- [ ] **Step 5: Commit the protected integration.**

  ```powershell
  git add backend/src/knora/infrastructure/settings.py backend/src/knora/main.py backend/src/knora/api/routes.py backend/test/api/test_m5_e2e_faults.py
  git commit -m "test(m5): expose e2e faults only in isolated runtime"
  ```

### Task 4: Drive the two outcomes through the real browser stack

**Files:**
- Modify: `docker-compose.m5-e2e.yml`
- Modify: `frontend/tests/e2e/support/auth.ts`
- Modify: `frontend/tests/e2e/m5-user-flows.spec.ts`
- Test: `frontend/tests/e2e/m5-user-flows.spec.ts`

**Interfaces:**
- The M5-E2E Compose overlay enables `KNORA_M5_E2E_FAULTS_ENABLED=true` for the API only.
- `armM5E2EFault(page, scenario)` uses the authenticated local test context, discovers its Workspace through the existing public session/application state, and posts through the existing generic Next.js BFF path `/api/m5-e2e/faults`. The BFF supplies the server-held bearer token; the helper returns no credentials or raw response data to test output.
- Browser scenarios use normal `/app` question UI and assert public text/state only.

- [ ] **Step 1: Write failing live scenarios.**

  Add a user scenario for `provider_failure`: log in with real Keycloak, arm that scenario, ask a normal question through the UI, assert the safe provider-failure state is visible, and assert no final answer/citation is rendered.

  Add a user scenario for `stream_interruption`: log in separately, arm the interruption, ask normally, assert the interrupted state is visible, and assert no final answer/citation is rendered. Neither test may use `page.route`, synthetic SSE, direct SQL, or special question content.

- [ ] **Step 2: Run RED against the live stack.**

  ```powershell
  docker compose -f docker-compose.yml -f docker-compose.m5-e2e.yml up -d --build
  Set-Location frontend
  npm run test:e2e -- tests/e2e/m5-user-flows.spec.ts --project=chromium
  ```

  Expected: both new scenarios fail before the helper/overlay wiring exists. If Keycloak, API, or browser startup fails, stop and preserve that infrastructure failure rather than replacing it with a mock.

- [ ] **Step 3: Implement minimal test-only browser setup.**

  Enable only the overlay flag. Add the helper using `page.request.post("/api/m5-e2e/faults", { data: { workspace_id, scenario } })`, which exercises the existing catch-all Next.js BFF and its server-held bearer token. Keep user UI code unchanged; if a stable accessible assertion is missing, add only a presentational selector/text consistent with the existing server-provided UI state.

- [ ] **Step 4: Run GREEN plus frontend regression.**

  ```powershell
  npm run test:e2e -- tests/e2e/m5-user-flows.spec.ts --project=chromium
  npm test
  npm run typecheck
  npm run lint
  npm run build
  ```

  Expected: both fault scenarios and existing frontend tests pass. Retain Playwright artifacts only on failure and do not commit them.

- [ ] **Step 5: Commit browser coverage.**

  ```powershell
  git add docker-compose.m5-e2e.yml frontend/tests/e2e/support/auth.ts frontend/tests/e2e/m5-user-flows.spec.ts
  git commit -m "test(m5): cover live fault and interruption states"
  ```

### Task 5: Run the complete gate and append honest M5.4 evidence

**Files:**
- Modify: `.agents/manual-tests/milestone-5/m5-e2e.evaluations.jsonl`
- Modify: `.agents/review/m5-final-verification.json`
- Modify: `.superpowers/sdd/2026-09-19-m5-live-e2e-infrastructure/progress.md`
- Modify: `.superpowers/sdd/2026-09-19-m5-live-e2e-infrastructure/task-5-resume-report.md`

**Interfaces:**
- Each appended record uses the current tested product commit as `subject_commit`, exact `environment: "live-keycloak-playwright"`, sanitized command, identity class, public state, outcome, and sanitized artifact reference.
- The final ledger distinguishes 12 existing scenarios, the two newly live scenarios, unavailable deletion, and every command result. It never labels a failed gate as complete.

- [ ] **Step 1: Run the full verification sequence from the M5.4 worktree.**

  ```powershell
  .\.venv\Scripts\python -m pytest
  .\.venv\Scripts\ruff check .
  docker compose config --quiet
  git diff --check
  Set-Location frontend
  npm test
  npm run typecheck
  npm run lint
  npm run build
  npm audit
  npm run test:e2e
  ```

  Expected: every command exits zero. If one fails, use `systematic-debugging`, record the real failed outcome, and do not update the gate to complete.

- [ ] **Step 2: Append sanitized, per-scenario evidence only after a green run.**

  Add one append-only JSONL record for provider failure and one for interruption. Record server-observed public result, not internal exception output. Keep the latest deletion observation as `UNAVAILABLE`; do not rewrite historical records.

- [ ] **Step 3: Update the final ledger and durable report.**

  Record the tested commit range, isolated compose startup command, each gate command/result, live counts, review status, and any remaining non-blocking deferred item. Remove the provider/interruption `BLOCKED_LIVE_E2E` blocker only if both fresh live scenarios passed.

- [ ] **Step 4: Self-review evidence and commit.**

  ```powershell
  git diff --check
  .\.venv\Scripts\python -c "import json; [json.loads(line) for line in open('.agents/manual-tests/milestone-5/m5-e2e.evaluations.jsonl', encoding='utf-8')]; print('jsonl valid')"
  git add .agents/manual-tests/milestone-5/m5-e2e.evaluations.jsonl .agents/review/m5-final-verification.json .superpowers/sdd/2026-09-19-m5-live-e2e-infrastructure/progress.md .superpowers/sdd/2026-09-19-m5-live-e2e-infrastructure/task-5-resume-report.md
  git commit -m "test(m5): record complete live e2e gate"
  ```

  Before committing, scan the staged diff for password, token, cookie, database URL, and authorization values. Force-add ignored SDD artifacts only when their contents remain sanitized.

### Task 6: Whole-branch review and integration checkpoint

**Files:**
- Review only: full `codex/m5-e2e-verification` range against the M5 design, both M5.4 plans, and evidence ledgers.

**Interfaces:**
- Produces a review verdict with zero unresolved Critical/Major findings before the branch can be presented for integration.

- [ ] **Step 1: Verify the final Git state and command evidence.**

  ```powershell
  git status --short
  git log --oneline origin/main..HEAD
  git diff origin/main...HEAD --check
  ```

  Expected: no unexpected worktree changes and no whitespace defects.

- [ ] **Step 2: Request whole-branch review.**

  Give the reviewer the approved M5 design/specs, plan paths, merge base, commit range, full gate outputs, and the explicit requirement to check authorization-before-lookup, backend ownership, missing-data semantics, SSE terminal semantics, evidence truthfulness, and scope creep.

- [ ] **Step 3: Address findings one at a time.**

  For each finding, verify it against this branch and its accepted contracts before changing code. Run the focused regression and request re-review. Stop rather than merge if a load-bearing finding remains.

- [ ] **Step 4: Present integration choices.**

  Only after a clean review and fresh full gate, present exactly: local merge to `main`, push/create a PR, or keep the branch. Do not perform any integration action without the user's explicit choice.

## Stop conditions

- Stop before any production authentication/authorization change or normal Compose modification.
- Stop if the route cannot be restricted to the M5-E2E runtime, if authorization cannot precede controller access, or if a scenario needs a fabricated token/session/response or direct database write.
- Stop on a failed load-bearing command, live test, or unresolved review finding; preserve truthful evidence and do not claim M5.4 complete.
- Stop before push, merge, branch deletion, or worktree removal and request the user's integration choice.
