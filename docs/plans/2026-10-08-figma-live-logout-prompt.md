# Figma live logout and forced sign-in — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development.

**Goal:** Verify the existing account logout and allowlisted forced sign-in journeys through real BFF and Keycloak services.
**Architecture:** Extend the guarded application group in the existing browser suite. Use the retained Figma harness and versioned synthetic identities; source fixtures cannot establish SSO termination.
**Tech Stack:** Next.js, React, TypeScript, Tailwind CSS v4, Playwright, Keycloak26.3.3.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Browser requests continue through the BFF. Keycloak owns credentials, reset codes and passwords.
- Preserve canonical /workspaces and /operator routes and backend authority.
- No OTP binding, password/reset/registration/MFA/Vault/realm configuration, outage, worker,
  document/workspace/conversation mutation, merge/push or cleanup.
- Controller resumed retained main services after CheckConfigurationOnly; project
  knora-figma-e2e, browser3300, API8800, Keycloak8380, mail8025. Do not start proof/proxy services.
- No mock/intercepted service responses, artificial clock or session-cookie forging.
- Do not persist credentials, cookies, tokens, codes, authorization URLs, state/nonce/PKCE values.
  Compare sensitive values in memory through boolean assertions. Native captures mask filled passwords.
- Preserve every prior Q1 artifact; add only live-logout-prompt-2026-10-08 evidence.
- Maintained production/helper/config/realm files are outside this verification-only task.
  Report an actual failure with evidence before expanding ownership.
- Every maintained frontend change requires format, then format:check; typecheck sequentially.

## Directory ownership

| File | Responsibility |
| --- | --- |
| frontend/tests/e2e/figma-ui-interactions.spec.ts | Real guarded application login/prompt/logout assertions |
| docs/development/figma-ui-visual-coverage.md | Exact native/BFF evidence and remaining expiry/reset limitations |

## Task 1: Verify real account logout and allowlisted forced sign-in

**Skills:** verification-before-completion, requesting-code-review; systematic-debugging on actual failure.
**Interfaces:** Existing openFigmaLogin(page), captureIdentity(page,path), realm.users fixture,
figma application project, AccountMenu and /api/auth/{login,session,logout}.

- [ ] Record clean BASE and every Q1 hash excluding root evidence/regression-preflight only.
  Read existing guarded application group, figma-auth/figma-environment helpers, AccountMenu,
  logout/login routes, session safe projection and coverage edges before mapping.
  Service ownership must pass the unchanged openFigmaLogin guard. Controller owns service readiness.
- [ ] Add one case at each1440×960 and390×844, named `live account logout and forced sign-in at {width}`.
  Use versioned m5-user from realm.users and existing native fields; never print credentials.
  openFigmaLogin starts the normal authorization transaction. Retain state, nonce and
  code_challenge in memory. Submit native credentials, await real callback and workspace landing.
  Assert session endpoint returns a non-null safe session with subject/capabilities and no token keys.
- [ ] In the same context with existing SSO, visit
  `/api/auth/login?prompt=login&returnTo=https://untrusted.example`. Assert native sign-in is shown,
  the Keycloak origin/realm is exact, prompt=login survives, untrusted returnTo is absent,
  redirect_uri is the fixed callback. Assert transaction state/nonce/code_challenge differ from
  the prior normal transaction using boolean assertions, never value-dumping equality assertions.
  Complete the native sign-in as the same synthetic user; verify real callback and same safe subject.
  Capture only a password-empty native sign-in page before filling, under the task folder.
- [ ] At the real application origin set one scoped panel-preference key and one unrelated key:
  `knora:conversation-panels:v1:test-scope` and `unrelated-preference`. Open actual account menu
  by safe subject, verify Signed in and Log out. Capture account menu after fonts load.
  Use Enter on the actual Log out menuitem. Observe real BFF POST /api/auth/logout303 and
  exact Keycloak logout pathname. Activate existing native logout confirmation if present;
  require the application Signed out heading/link afterward. Do not skip SSO confirmation.
- [ ] Assert scoped preference removed and unrelated preference retained at application origin.
  GET /api/auth/session has null session; GET /api/v1/workspaces is401. Open normal Sign in
  link again and require the native password form rather than an automatic SSO callback.
  This proves logout termination and fresh sign-in availability, not natural session expiry.
  Do not submit the last form; capture its password-empty state with the masking helper.
- [ ] Record only sanitized JSON booleans/status/pathnames plus source viewport. Observe all
  non-GET /api/v1 requests and require none; expected auth/session/preference activity must be
  distinguished from business mutations. No response substitution or request abortion.
- [ ] Run only the new two cases in application mode:
  `FIGMA_TEST_MODE=application npm --prefix frontend run test:e2e -- --config playwright.figma.config.ts figma-ui-interactions.spec.ts --grep 'live account logout and forced sign-in'`.
  Normalize color env, no retry. View captures, disclose mobile adaptation and real exact outcomes.
  If actual UI/provider failure occurs, diagnose and report before production/helper edits.
- [ ] Update accurately exercised ledger rows/sections. Do not claim reset completion, OTP binding,
  account switching or natural expired-session proof. Preserve all existing limits.
  Inventory after: all prior hashes unchanged, additions solely task folder. Run format→check→typecheck;
  rerun covering browser cases only if formatter changes their code. Self-review, exact2path commit,
  release owned3300, save task-1-report.md. Controller originalBASE→HEAD independent Spec/Quality review.

**Finish condition:** Real logout and forced-native-sign-in behavior independently verified at both sizes;
native OTP, expiry, other prototype actions and whole-design acceptance remain open.
