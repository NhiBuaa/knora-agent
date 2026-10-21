# M5 Live End-to-End Infrastructure Design

**Status:** Design approved by user on 2026-09-19  
**Branch:** `codex/m5-e2e-verification`  
**Scope:** Remove the remaining M5.4 live-browser acceptance blocker with an isolated
Playwright and Keycloak test environment.

## 1. Goal

M5.4 already proves contracts, authorization rules, and user/operator behavior through
deterministic application seams. The remaining acceptance gap is a real browser run through the
Next.js application and a real OIDC authorization-code flow.

This change adds repeatable local test infrastructure that proves those flows without production
credentials, without changing production authorization semantics, and without turning the
frontend into a domain authority.

## 2. Chosen approach

Use a dedicated Docker Compose overlay for M5 end-to-end testing. The normal Compose definition
remains the base environment. The overlay adds an isolated Keycloak service and test-only
configuration. Playwright starts or connects to the frontend and drives the browser against the
combined environment.

This approach was selected over adding Keycloak permanently to the normal development stack or
continuing with mocked browser seams. It preserves normal development behavior while providing
real authentication and browser evidence that mocks cannot supply.

## 3. Environment architecture

```text
Playwright browser
    |
    | authorization code + PKCE
    v
Next.js test instance <----> Keycloak test realm
    |
    | BFF forwards bearer token
    v
FastAPI test instance -----> PostgreSQL test data
```

The environment uses isolated local ports and deterministic test identities. A realm import
defines the OIDC client, redirect URI, roles, workspace claims, and test users required by the
authorization matrix. All credentials in the fixture are intentionally test-only and must never
be accepted by a production deployment.

The backend remains responsible for token validation, WorkspacePrincipal construction,
workspace authorization, capability authorization, and every domain outcome. Next.js owns only
browser session handling and presentation.

## 4. Components and ownership

### 4.1 Compose overlay

Add an M5-specific Compose overlay that:

- adds Keycloak with a pinned image version and realm import;
- supplies only local test configuration;
- reuses the existing PostgreSQL/backend services where compatible;
- exposes isolated ports so it does not replace a developer's normal environment;
- includes health checks or readiness probes needed by the test runner.

The overlay must not introduce production defaults, copy real secrets, or weaken an existing
authentication path.

### 4.2 Keycloak realm fixture

Add a committed, deterministic realm fixture containing:

- one confidential or public client matching the existing Next.js OIDC implementation;
- exact local redirect and logout URIs;
- a normal workspace user;
- an operator-capable user;
- a user belonging to another workspace;
- a user without the operator capability.

Passwords and client credentials are test fixtures, clearly labeled and scoped to the isolated
realm. Tokens and runtime session material are never committed to evidence.

### 4.3 Playwright runner

Add `@playwright/test`, a Playwright configuration, and explicit package scripts for live E2E.
The runner targets only files under a dedicated `frontend/tests/e2e/` directory so Vitest and
Playwright do not accidentally discover each other's suites.

The configuration uses an isolated browser base URL and provides deterministic startup,
readiness, timeout, trace-on-failure, screenshot-on-failure, and video-on-failure behavior.
Generated browser artifacts remain untracked unless a sanitized artifact is deliberately added
as acceptance evidence.

### 4.4 Test data bootstrap

Tests prepare data through existing public or supported application seams. They do not write
directly to internal tables merely to manufacture a successful UI state. Where a provider outcome
must be deterministic, the environment may use an existing fake provider or test adapter, but the
browser, BFF, token validation, backend authorization, persistence, and public API path remain
real.

Each test uses unique workspace-scoped identifiers and cleans up or uses disposable environment
state so retries do not depend on the order of previous runs.

## 5. Browser scenarios

The live suite covers the load-bearing M5 paths:

1. login, callback, httpOnly session creation, logout, and rejected/expired sessions;
2. user access to the authorized workspace and safe denial of a different workspace;
3. upload, ingestion polling, and serving projection;
4. question submission, validated answer, citation inspection, and refusal;
5. interrupted or failed response shown as failure/unavailable rather than a final answer;
6. archive, unarchive, and deletion-request observation where the accepted backend contract
   permits them;
7. operator trace, evaluation, operations, and M4 lifecycle views;
8. denial for a non-operator and for an opaque identifier from another workspace;
9. unavailable observations rendered explicitly, without invented zeroes or success states;
10. absence of credentials, raw exceptions, provider secrets, and unauthorized internal fields
    from browser-visible responses and pages.

Scenarios may share authenticated storage state only within the same role and workspace. Cross-role
and cross-workspace tests use separate browser contexts.

## 6. Failure and safety semantics

Startup failures identify the unavailable dependency instead of being recorded as product test
failures. Authentication or authorization failures are asserted through safe public behavior and
must not reveal resource existence.

The suite never bypasses Keycloak by injecting a fabricated production session. It may use
Playwright setup to perform the real login once and save test-only browser storage for later tests.
Backend authorization remains active for every request.

If the browser disconnects before a terminal answer event, the UI must retain an interrupted or
failure state. Missing trace, evaluation, metric, or M4 lifecycle data remains unavailable. The
test harness must not convert either condition into success.

## 7. Evidence and verification

Live executions append sanitized records to the existing M5 evaluation evidence. Each record
identifies the tested commit, scenario, environment type, outcome, and non-secret artifact
reference. Existing deterministic seam results remain labeled `DETERMINISTIC_SEAM_PASS`; only a
successful Playwright execution against the isolated Keycloak environment may replace
`BLOCKED_LIVE_E2E` with a live pass result.

The final gate includes:

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

The exact Compose startup and shutdown commands will be locked in the implementation plan. A
failed command or unresolved load-bearing review finding keeps M5.4 incomplete.

## 8. Expected file ownership

The implementation is expected to touch only test infrastructure and evidence, principally:

- a new M5 E2E Compose overlay;
- a new test-only Keycloak realm fixture;
- `frontend/package.json` and `frontend/package-lock.json`;
- a new Playwright configuration;
- new files under `frontend/tests/e2e/`;
- narrow test bootstrap helpers where required;
- existing M5.4 evidence files after a real run.

Any required production-code behavior change is outside this infrastructure design. It must be
treated as a verified finding, assigned to the owning slice, and handled with its own approved
design and RED -> GREEN -> REFACTOR cycle.

## 9. Non-goals

- No production Keycloak deployment or secret management.
- No redesign of login, BFF sessions, workspace claims, or backend authorization.
- No weakening of authorization for test convenience.
- No replacement of the existing deterministic contract and seam tests.
- No broad CI redesign; CI wiring may be proposed later after local live E2E is stable.
- No new domain behavior, durable conversation model, or frontend-owned decision logic.

## 10. Acceptance criteria

The design is satisfied when a clean local environment can execute the Playwright suite through a
real Keycloak login, all load-bearing user/operator and negative scenarios pass, live evidence is
recorded without secrets, the full M5 regression gate remains green, and final review reports no
unresolved load-bearing finding.
