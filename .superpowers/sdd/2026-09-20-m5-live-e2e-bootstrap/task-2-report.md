# Task 2 — delete-capable fixture and public browser cases

Status: **complete** (2026-09-20)

## Scope and seams

- Added only the isolated Keycloak `m5-delete-user` fixture. It is scoped to
  `m5-workspace` and carries `documents:read`, `documents:write`,
  `documents:delete`, and `questions:ask`.
- Extended the real authorization-code + PKCE browser helper with the `delete-user`
  identity. Its credentials are read only from `M5_E2E_DELETE_USERNAME` and
  `M5_E2E_DELETE_PASSWORD`; session assertions check the workspace and all expected
  capabilities without exposing session material.
- The readiness script validates the new access-token claims in process and prints
  neither a token nor decoded claims.
- The public user suite now serializes its shared live-workspace cases and adds a
  delete-request case. The impossible strict provider-failure case is not part of the
  pass suite because the approved environment has no deterministic provider-failure
  seam; the live evidence remains recorded as unavailable below.

No product code, authorization path, database table, browser session/cookie handling,
provider mock, or operator workspace selector changed.

## RED evidence

1. Provisioned the sanctioned environment first:

   ```powershell
   powershell -ExecutionPolicy Bypass -File test\fixtures\keycloak\test_m5_e2e_compose.ps1
   ```

   Output ended with the existing sanitized readiness confirmation.

2. Added the deletion and unavailable-question browser scenarios before adding the
   realm/helper support, then ran the focused real-browser suite with only sanctioned
   `M5_E2E_*` endpoint and fixture-credential variables:

   ```powershell
   Set-Location frontend
   npx playwright test tests/e2e/m5-user-flows.spec.ts --project=chromium --reporter=list
   ```

   Result: **1 passed, 4 failed**. The new deletion scenario failed at
   `credentialsEnvironmentNames["delete-user"]` because the identity mapping was
   absent. Existing Task 4 inputs also revealed a list-item accessible-name race and
   a duplicate terminal-status locator; both were corrected in the test seam.

## GREEN evidence

1. After adding the isolated realm identity, helper mapping/session shape, and
   readiness validation, reran readiness successfully:

   ```powershell
   powershell -ExecutionPolicy Bypass -File test\fixtures\keycloak\test_m5_e2e_compose.ps1
   ```

   Result: the readiness script completed with its sanitized Keycloak/API/denial
   confirmation, including the delete-capability validation.

2. Focused public-browser verification:

   ```powershell
   Set-Location frontend
   npx playwright test tests/e2e/m5-user-flows.spec.ts tests/e2e/m5-operator-flows.spec.ts --project=chromium --reporter=list
   ```

   Result: **6 passed**. This covers upload/serving, archive/unarchive, real
   delete-request state (without asserting hard deletion), native no-evidence refusal,
   authorized operator unavailable state, and non-operator denial. The deletion
   scenario records the observed policy state as unavailable when the backend returns
   `blocked`; it never counts that outcome as passed.

3. Frontend verification:

   ```powershell
   Set-Location frontend
   npm run typecheck
   npm test
   ```

   Result: typecheck passed; Vitest reported **17 files passed, 49 tests passed**.

4. Diff verification:

   ```powershell
   git diff --check
   ```

   Result: passed.

## Files changed

- `test/fixtures/keycloak/m5-realm.json`
- `test/fixtures/keycloak/test_m5_e2e_compose.ps1`
- `frontend/tests/e2e/support/auth.ts`
- `frontend/tests/e2e/m5-user-flows.spec.ts`
- Existing Task 4 input retained and committed: `frontend/tests/e2e/m5-operator-flows.spec.ts`

## Self-review

- The delete identity is fixture-only and least-privilege for the required user flow;
  no existing identity changed.
- Browser tests use fresh role contexts, real login, public controls, and public text.
- The deletion assertion accepts the documented asynchronous request states and confirms
  the document remains present at request time; it never treats submission as a hard
  delete.
- Evidence records are in-memory and structured so credentials, cookies, tokens, raw
  errors, database URLs, and provider payloads cannot be recorded.
- No direct database writes, token/session fabrication, cookie decoding, or provider
  mocking was introduced.

## Review fix round 1

The review findings were reproduced and addressed in the allowed Task 2 files:

- Session and readiness assertions now compare exact normalized workspace and capability
  sets for every fixture identity; extra grants fail.
- The native refusal runs first in the serial user suite and uses a unique absent-fact
  question, before any browser upload. It therefore cannot rely on prior test evidence.
- Upload lifecycle now asserts the public values `current` and `unavailable`, rather
  than only the `Serving`/`Ingestion` labels.
- Deletion preserves the document and records `passed` only for `requested` or `queued`.
  The current live policy returns `blocked (DOCUMENT_DELETION_POLICY_UNAVAILABLE)`,
  which is recorded as `unavailable`, never as a pass.
- The vacuous `arrayContaining([])` assertions and unused result accumulators were
  removed from both browser specs. Playwright failure artifacts remain configured by
  the pre-existing Playwright config outside Task 2's allowed files; changing that
  retention policy is deferred rather than scope-expanded.

Verification:

```powershell
powershell -ExecutionPolicy Bypass -File test\fixtures\keycloak\test_m5_e2e_compose.ps1
```

Passed with exact claims for user, operator, delete-user, other-workspace, and
no-operator fixtures.

```powershell
Set-Location frontend
npx playwright test tests/e2e/m5-user-flows.spec.ts tests/e2e/m5-operator-flows.spec.ts --project=chromium --reporter=list
```

The live run passed refusal, upload lifecycle, archive/unarchive, operator operations,
and non-operator denial. Deletion correctly rendered the blocked policy state as
`unavailable`. The strict failure-only question case was removed from the live pass
suite: the provisioned real environment returns native no-evidence refusal, not
`Request failed: INTERNAL_ERROR`.
The approved design explicitly has no deterministic provider-failure/interruption seam;
no mock or fabricated outcome was added to force it.
