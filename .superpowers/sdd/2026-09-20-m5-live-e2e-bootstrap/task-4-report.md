# Task 4 — bootstrap-focused live M5 verification

Status: **complete for the approved focused scope** (2026-09-20)

## Review inputs

Task 1 and Task 2 reports were reviewed against the approved bootstrap plan/spec and the two
scoped review verdicts. The reviewed commit range is `50ea06b..f4424ee`. No load-bearing finding
remains in the bootstrap, readiness, fixture, or browser-test scope.

## Live evidence

The sanctioned readiness command ran against the migrated Compose services and real Keycloak
authorization-code + PKCE login. Its output remained sanitized and included exact claims for the
fixture identities and both provisioned Workspaces.

Focused browser command:

```powershell
Set-Location frontend
npx playwright test tests/e2e/m5-user-flows.spec.ts tests/e2e/m5-operator-flows.spec.ts --project=chromium --reporter=list
```

Result: **6 passed**.

- **4 user cases:** native no-evidence refusal; upload/serving lifecycle; archive/unarchive;
  delete-capable public deletion-request policy observation.
- **2 operator cases:** authorized operations/evaluation-unavailable presentation; same-workspace
  non-operator denial.

The deletion-capable flow observed the backend policy state `blocked` with
`DOCUMENT_DELETION_POLICY_UNAVAILABLE`; the public result is recorded as `unavailable`, and the
document remains present. This is policy-unavailable evidence, not a successful deletion claim.

Frontend verification:

```powershell
Set-Location frontend
npm run typecheck
npm test
```

Results: typecheck passed; Vitest reported **17 files passed, 49 tests passed**.

Exact claim checks covered the fixture identities' workspace and capability sets, including the
isolated `documents:delete` grant for `m5-delete-user`; no token, cookie, password, database URL,
raw exception, or provider payload was emitted.

## Deferred live coverage

Provider-failure/interruption is **`BLOCKED_LIVE_E2E`** and deferred. The approved environment has
no deterministic public provider-failure or interruption seam. No mock, fabricated SSE response,
or fabricated outcome was used to turn this gap into a pass.

## Boundary

This report records the focused bootstrap verification only. It does **not** claim Task 5 or the
M5.4 release gate complete; the original full release-gate command sequence remains separate.
