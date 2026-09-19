# M5 Live End-to-End Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated Keycloak-backed Playwright environment and live browser evidence for the remaining M5.4 acceptance gap.

**Architecture:** A dedicated Compose overlay adds only test-scoped Keycloak configuration while the existing PostgreSQL/API services remain authoritative. Playwright drives the real Next.js login, BFF, backend authorization, and public domain flows; deterministic provider seams are used only where the product already exposes them.

**Tech Stack:** Docker Compose overlay, Keycloak, Next.js 15, `@playwright/test`, TypeScript, existing FastAPI API, PostgreSQL, Vitest, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-09-19-m5-live-e2e-infrastructure-design.md`

## Global Constraints

- Use only test-only Keycloak realm, users, client settings, and local secrets; never commit production credentials or runtime tokens.
- Backend remains responsible for token validation, workspace/capability authorization, lifecycle state, citations, refusals, and M4 decisions.
- Every browser request must pass through the real Next.js BFF and backend authorization path; do not inject fabricated production sessions.
- Keep deterministic contract/seam tests and label their results `DETERMINISTIC_SEAM_PASS`; only live Playwright runs may produce live-pass evidence.
- A missing observation, failed stream, or disconnected browser is recorded as unavailable/interrupted/failure, never as success.
- Every behavior change follows RED -> GREEN -> REFACTOR; infrastructure changes must have a focused readiness or smoke test before dependent scenarios.
- Do not modify normal production Compose semantics, weaken authentication, merge, push, or remove the worktree without an explicit integration choice.

## File map

- Create `docker-compose.m5-e2e.yml`: isolated Keycloak service, local ports, readiness, and test-only environment overlay.
- Create `test/fixtures/keycloak/m5-realm.json`: imported realm, client, roles, workspace claims, and test users.
- Modify `frontend/package.json`: Playwright dependency and `test:e2e`/support scripts.
- Modify `frontend/package-lock.json`: lockfile entries produced by npm.
- Create `frontend/playwright.config.ts`: browser projects, base URL, startup/readiness, retries, and failure artifacts.
- Create `frontend/tests/e2e/support/environment.ts`: typed URLs and test-only environment validation.
- Create `frontend/tests/e2e/support/auth.ts`: real Keycloak login helpers and role/workspace browser contexts.
- Create `frontend/tests/e2e/m5-authentication.spec.ts`: login, logout, expired/denied session behavior.
- Create `frontend/tests/e2e/m5-user-flows.spec.ts`: document, question, citation, refusal, interruption, and lifecycle behavior.
- Create `frontend/tests/e2e/m5-operator-flows.spec.ts`: operator projections, denial, unavailable observations, and sensitive-field filtering.
- Modify `.agents/manual-tests/milestone-5/m5-e2e.evaluations.jsonl`: append sanitized live records only after successful runs.
- Modify `.agents/review/m5-final-verification.json`: record the live command, commit, environment, and final gate.

---

### Task 1: Add isolated Keycloak Compose overlay and realm fixture

**Files:**
- Create: `docker-compose.m5-e2e.yml`
- Create: `test/fixtures/keycloak/m5-realm.json`
- Test: `test/fixtures/keycloak/test_m5_e2e_compose.ps1`

**Interfaces:**
- Produces a service named `keycloak-m5-e2e` reachable from the host at `http://127.0.0.1:8180` and a realm issuer at `http://127.0.0.1:8180/realms/m5-e2e`.
- Produces OIDC endpoints consumed by Next.js: authorization `/protocol/openid-connect/auth`, token `/protocol/openid-connect/token`, JWKS `/protocol/openid-connect/certs`.
- Produces test identities `m5-user`, `m5-operator`, `m5-other-workspace`, and `m5-no-operator`; their claims map to distinct workspace/capability cases without exposing production data.

- [ ] **Step 1: Write the failing overlay validation test.**

  In `test/fixtures/keycloak/test_m5_e2e_compose.ps1`, load the overlay with `docker compose -f docker-compose.yml -f docker-compose.m5-e2e.yml config --quiet`, assert the Keycloak service and realm fixture paths exist, and fail if the published port is not `8180`.

- [ ] **Step 2: Run the validation test to verify it fails.**

  Run: `powershell -File test/fixtures/keycloak/test_m5_e2e_compose.ps1`  
  Expected: FAIL because the overlay and fixture do not yet exist.

- [ ] **Step 3: Write the minimal overlay and realm.**

  Use a pinned Keycloak image, `start-dev --import-realm`, a healthcheck against the realm endpoint, a named test-only volume, and local-only port binding. Set redirect URIs to the isolated Next.js callback URL and define only the roles/claims needed by the authorization matrix. Do not add Keycloak to `docker-compose.yml`.

- [ ] **Step 4: Run the validation and readiness checks.**

  Run the PowerShell test, then `docker compose -f docker-compose.yml -f docker-compose.m5-e2e.yml up -d keycloak-m5-e2e` and `Invoke-WebRequest http://127.0.0.1:8180/realms/m5-e2e/.well-known/openid-configuration`.  
  Expected: config passes and the discovery document returns HTTP 200 with the realm issuer and endpoint URLs.

- [ ] **Step 5: Refactor and commit.**

  Confirm no production secret names or real hostnames occur in the fixture, run `git diff --check`, and commit:

  ```text
  test(m5): add isolated keycloak e2e environment
  ```

### Task 2: Install and configure Playwright without changing Vitest discovery

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tests/e2e/support/environment.ts`
- Test: `frontend/tests/e2e/support/environment.test.ts`

**Interfaces:**
- Produces `npm run test:e2e` for files under `frontend/tests/e2e/**/*.spec.ts`.
- `environment.ts` exports `m5E2EEnvironment(): { baseUrl: string; apiUrl: string; keycloakIssuer: string }` and throws a clear configuration error when a required test-only variable is missing.
- Keeps `frontend/vitest.config.ts` discovery unchanged so `.spec.ts` files are not run by Vitest.

- [ ] **Step 1: Write the failing environment test.**

  Assert that `m5E2EEnvironment()` returns the configured local URLs and rejects an empty `M5_E2E_BASE_URL`; assert that `package.json` contains `test:e2e` and `@playwright/test`.

- [ ] **Step 2: Run the focused test to verify it fails.**

  Run: `Set-Location frontend; npm test -- tests/e2e/support/environment.test.ts`  
  Expected: FAIL because the helper, package script, and dependency are absent.

- [ ] **Step 3: Add the dependency, scripts, helper, and config.**

  Add `@playwright/test` as a dev dependency, scripts `test:e2e` and `test:e2e:install`, and configure Chromium, `baseURL`, isolated artifact output, `trace: "retain-on-failure"`, screenshots and video on failure. Do not make Playwright files part of Vitest's include glob.

- [ ] **Step 4: Run the focused and configuration checks.**

  Run `npm install`, `npm test -- tests/e2e/support/environment.test.ts`, `npm run typecheck`, and `npx playwright test --list`.  
  Expected: focused test/typecheck pass and Playwright lists only `frontend/tests/e2e/**/*.spec.ts`.

- [ ] **Step 5: Refactor and commit.**

  Verify the lockfile has no unrelated dependency churn and commit:

  ```text
  test(m5): configure playwright live e2e runner
  ```

### Task 3: Implement real Keycloak authentication helpers and authentication scenarios

**Files:**
- Create: `frontend/tests/e2e/support/auth.ts`
- Create: `frontend/tests/e2e/m5-authentication.spec.ts`
- Test: `frontend/tests/e2e/m5-authentication.spec.ts`

**Interfaces:**
- `loginAs(page, identity: "user" | "operator" | "other-workspace" | "no-operator"): Promise<void>` follows the real `/api/auth/login` redirect, fills the Keycloak test form, waits for `/api/auth/callback`, and asserts the httpOnly session via an authenticated page rather than reading the cookie.
- `newRoleContext(browser, identity)` returns a separate browser context for each role/workspace case.

- [ ] **Step 1: Write RED browser scenarios.**

  Add tests for successful user login and logout, missing/expired session redirect, operator login, cross-workspace safe denial, and non-operator denial of `/operator`. The tests must assert user-visible status and HTTP-safe behavior, not Keycloak internals.

- [ ] **Step 2: Run the scenarios before helpers are complete.**

  Run: `Set-Location frontend; npx playwright test tests/e2e/m5-authentication.spec.ts --project=chromium`  
  Expected: FAIL because the helper and configured environment are incomplete.

- [ ] **Step 3: Implement the real login helper.**

  Use the configured authorization endpoint and test credentials from environment variables, wait for the callback URL, and avoid logging passwords, authorization codes, access tokens, or cookies. Use distinct contexts for each identity.

- [ ] **Step 4: Run GREEN authentication scenarios.**

  Start the overlay, API, and Next.js test server with the test-only OIDC variables, then run the focused Playwright file.  
  Expected: all authentication and authorization assertions pass; an unavailable dependency is reported as infrastructure failure, not recorded as a product pass.

- [ ] **Step 5: Refactor and commit.**

  Remove duplicated login/navigation code, assert no token/credential strings appear in test output, and commit:

  ```text
  test(m5): verify live keycloak authentication boundaries
  ```

### Task 4: Add live user and operator M5 flows

**Files:**
- Create: `frontend/tests/e2e/m5-user-flows.spec.ts`
- Create: `frontend/tests/e2e/m5-operator-flows.spec.ts`
- Modify: `frontend/tests/e2e/support/auth.ts`
- Test: the two new Playwright spec files

**Interfaces:**
- User specs consume `loginAs` and the public `/app` UI; they do not call private modules or seed internal tables directly.
- Operator specs consume `newRoleContext` and the public `/operator` UI; they assert backend-owned projections and safe missing-data states.
- Each spec emits a structured in-memory result `{ scenario, identity, outcome, observedState }` for the evidence step; it never includes credentials, tokens, raw exceptions, or provider secrets.

- [ ] **Step 1: Write RED user-flow scenarios.**

  Cover document upload and ingestion progress, serving projection, question answer with citation inspection, refusal, interrupted/failed response, archive/unarchive, and deletion-request observation using unique test identifiers and existing deterministic provider seams where the product already supports them.

- [ ] **Step 2: Write RED operator-flow scenarios.**

  Cover authorized trace/evaluation/operations/M4 views, explicit unavailable observations, sensitive-field absence, operator denial for `m5-no-operator`, and cross-workspace denial for `m5-other-workspace`.

- [ ] **Step 3: Run focused scenarios to verify the initial failures.**

  Run each file with `npx playwright test ... --project=chromium`.  
  Expected: failures identify missing selectors, data bootstrap, or environment readiness; do not weaken authorization or skip a scenario to make it pass.

- [ ] **Step 4: Implement only test bootstrap and selectors required by the accepted UI.**

  Use public API/setup seams already present in M5.1–M5.3. Keep backend outcomes authoritative, wait for explicit stage/terminal states, and assert refusal/failure/interruption are not rendered as completed answers. Use separate browser contexts for workspace and operator identities.

- [ ] **Step 5: Run GREEN focused scenarios and the frontend regression suite.**

  Run the two focused Playwright files, `npm test`, `npm run typecheck`, `npm run lint`, and `npm run build`.  
  Expected: live scenarios pass and the existing frontend gate remains green.

- [ ] **Step 6: Refactor and commit.**

  Deduplicate stable selectors and data helpers, retain failure traces only when needed for diagnosis, run `git diff --check`, and commit:

  ```text
  test(m5): verify live user and operator journeys
  ```

### Task 5: Record live evidence and run the complete M5 release gate

**Files:**
- Modify: `.agents/manual-tests/milestone-5/m5-e2e.evaluations.jsonl`
- Modify: `.agents/review/m5-final-verification.json`
- Test: repository-wide verification commands

**Interfaces:**
- Evidence records include `subject_commit`, scenario ID, `environment: "live-keycloak-playwright"`, outcome, observed public state, and sanitized artifact reference only.
- Existing `DETERMINISTIC_SEAM_PASS` and `BLOCKED_LIVE_E2E` records remain append-only; do not rewrite old history.

- [ ] **Step 1: Run the complete live command sequence.**

  Run from the repository root:

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

  Expected: every command passes; if Keycloak or browser startup fails, stop and record the exact infrastructure blocker instead of claiming a live pass.

- [ ] **Step 2: Append sanitized live evaluation records.**

  Record one JSONL object per scenario with the current commit SHA, command, identity class, public outcome, and pass/failure classification. Never include credentials, tokens, cookies, raw provider payloads, or unfiltered exception text.

- [ ] **Step 3: Update final verification evidence.**

  Record the exact commit range, environment startup command, all gate outputs, live scenario counts, remaining deferred items, and review verdict. Keep `BLOCKED_LIVE_E2E` only for scenarios genuinely blocked by an external dependency.

- [ ] **Step 4: Self-review and commit evidence.**

  Run `git diff --check`, inspect the diff for secret-like fields, confirm evidence `subject_commit` equals `git rev-parse HEAD`, and commit:

  ```text
  test(m5): record live e2e verification gate
  ```

- [ ] **Step 5: Stop at the integration checkpoint.**

  Request focused code review for the complete M5.4 branch. Do not push, merge, delete the branch, or remove the worktree; present the exact verification and integration choices to the user.

## Stop conditions

- Stop before modifying production authentication or authorization if the existing OIDC contract cannot support the test realm.
- Stop if a scenario requires direct database writes or fabricated tokens; report the missing supported seam for approval.
- Stop on any failed load-bearing gate or unresolved review finding; preserve the failure evidence and do not label M5.4 complete.
- Stop before integration actions and ask the user to choose local merge, PR, or keep-branch-as-is.
