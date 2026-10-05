# Figma identity and email OTP — Implementation Plan

> For agentic workers: use executing-plans or subagent-driven-development task by task.

**Goal:** Implement the 12 identity variants, registration and the user-approved six-digit email
OTP reset journey.

**Architecture:** Keycloak owns forms, credentials, OTP and password policy. The existing BFF owns
OIDC transactions and application sessions; it supplies safe error screens and a fixed reauthentication option.

**Tech Stack:** Keycloak 26.3.3, Java 21/Maven, FreeMarker/CSS; Next.js with Tailwind CSS v4;
Vitest/Playwright.

**Spec:** [Integration design](../specs/2026-10-05-figma-ui-integration-design.md).
**Research:** [Pinned Keycloak findings](../../research/keycloak-email-otp-reset-2026-10-05.md).

**Directory structure:** Read the current/target tree, module responsibilities and dependency rules
in [the workflow's directory analysis](2026-10-05-figma-ui-workflow.md#phân-tích-cấu-trúc-thư-mục-dự-kiến).
The task's file list and this structure must remain consistent throughout execution.

## Global Constraints

- Preserve canonical /workspaces and /operator routes and backend authority.
- Keep credentials, OTP and password changes in Keycloak.
- Use Tailwind CSS v4 for the Next.js frontend, mapped to shared semantic tokens; no manual generated OpenAPI edits.
- Every maintained frontend change requires format, then format:check.
- Keep Keycloak dependencies at 26.3.3 and Java at 21; rebuild/retest on upgrades.
- Tailwind styles application auth error pages and account UI. Keycloak templates keep separate
  CSS assets with matching brand tokens and do not depend on the Next.js CSS bundle.
- No destructive realm import, production SMTP change or real-user reset during development.
- Five-minute code TTL, 15-minute recovery window, five verify submissions per account/window,
  30-second resend cooldown, three sends per account/window, 20 sends per IP/window are proposals
  selected by this plan, not native Keycloak defaults.

## Task I1: Keycloak presentation and registration

**Skills:** executing-plans, test-driven-development for form behavior; research for unresolved
platform details; verification-before-completion.

**Dependency:** F2 asset/token contract and approved registration/reset scope.

**Modify:** themes/knora/login/theme.properties;
themes/knora/login/resources/css/knora.css;
test/fixtures/keycloak/dev-realm.json;
docs/development/keycloak-theme.md;
backend/test/config/test_keycloak_theme.py.

**Create:** themes/knora/login/login.ftl, register.ftl, login-update-password.ftl, info.ftl;
themes/knora/login/messages/messages_en.properties;
scripts/configure-keycloak-auth-flow.ps1;
frontend/tests/e2e/figma-identity.spec.ts.

**Consumes:** F2 local brand/font assets; pinned native templates and form contract.
**Produces:** branded templates retaining Keycloak native loginAction, field names, hidden state,
validation and escaping. Account menu remains an application component from F2/I3.

Proposed realm choices: registrationAllowed=true, resetPasswordAllowed=true,
loginWithEmailAllowed=true, duplicateEmailsAllowed=false. Keep username registration and add email
sign-in. Do not silently add a mandatory email-verification screen absent from this Figma; retain
the current verifyEmail setting and document it. Use a test SMTP server for reset integration.

- [ ] Add real-browser failing checks for sign-in default/invalid, registration default/validation,
  successful registration landing in NO_ACTIVE_WORKSPACE, and password confirmation/policy errors.
- [ ] Adapt native 26.3.3 templates to the Figma layout, using the existing local fonts and exported
  assets. Keep any Figma display-name field mapped to explicit Keycloak profile fields; do not
  create a Knora password/profile store.
- [ ] Implement the configuration script with inspect/diff/apply behavior, exact target realm,
  idempotent updates and saved previous settings for rollback. Update import fixture for fresh
  environments; existing realms require the script. Never print credentials.
- [ ] Test the negative registration state with a real validation failure:

~~~ts
await page.getByRole("button", { name: "Create account", exact: true }).click();
await expect(page.getByRole("alert")).toBeVisible();
await expect(page).toHaveURL(/\/realms\/knora-dev\//);
~~~

- [ ] Run the Keycloak theme config pytest, scoped Playwright identity cases and visual comparison
  of AU1/AU2/AU8/AU9. Review/commit as feat: implement Figma Keycloak identity theme.

## Task I2: Keycloak email OTP provider

**Skills:** research, codebase-design, test-driven-development, executing-plans,
requesting-code-review and verification-before-completion.

**Dependency:** I1. Resolve and prove storage atomicity before connecting real password changes.

**Create under infra/keycloak/providers/email-otp-reset:**

- pom.xml
- src/main/java/com/knora/keycloak/reset/EmailOtpResetAuthenticator.java
- src/main/java/com/knora/keycloak/reset/EmailOtpResetAuthenticatorFactory.java
- src/main/java/com/knora/keycloak/reset/OtpChallengeService.java
- src/main/java/com/knora/keycloak/reset/OtpChallengeStore.java
- src/main/java/com/knora/keycloak/reset/KeycloakOtpChallengeStore.java
- src/main/resources/META-INF/services/org.keycloak.authentication.AuthenticatorFactory
- src/test/java/com/knora/keycloak/reset/OtpChallengeServiceTest.java
- src/test/java/com/knora/keycloak/reset/EmailOtpResetFlowIT.java
- src/test/java/com/knora/keycloak/reset/OtpChallengeConcurrencyIT.java

**Create:** themes/knora/login/knora-reset-email.ftl, knora-reset-otp.ftl;
themes/knora/email/theme.properties; themes/knora/email/html/knora-reset-otp.ftl;
themes/knora/email/text/knora-reset-otp.ftl;
themes/knora/email/messages/messages_en.properties.

**Modify:** infra/keycloak/Dockerfile, scripts/configure-keycloak-auth-flow.ps1,
test/fixtures/keycloak/dev-realm.json, docs/development/keycloak-theme.md;
add isolated test SMTP/container configuration to the identity integration harness.

**Interface design:** the Authenticator delegates recovery policy to OtpChallengeService.
OtpChallengeStore owns atomic operations, not a public map of counters. Define immutable Java
records for ChallengeScope(realmId, clientId, authSessionId, tabId, emailDigest),
ChallengeReference(id, generation), and an enum VerifyOutcome
(VERIFIED, INVALID, EXPIRED, EXHAUSTED, UNAVAILABLE).
The service exposes request(scope, email), resend(scope, reference), verify(scope, reference, code).
Results contain only safe render attributes and an internal verified user ID, never plaintext code.
Inject Clock, SecureRandom-backed generator, keyed digest and EmailTemplateProvider adapter.

- [ ] Write store contract tests for atomic generation rotation, one consume, fixed account budget
  across sessions and realm separation. Start with the pinned SingleUseObjectProvider adapter.
  Use atomic reservations/consume operations and explicit expiry; do not use replace as CAS.
- [ ] Prove the candidate adapter with concurrent sessions and two Keycloak nodes. If it cannot
  guarantee rotation/budgets, stop this slice before rollout and revise the storage design through
  brainstorming/codebase-design. A local in-memory map or auth-session notes alone cannot pass.
  This narrow technical decision does not block work on the other UI slices.
- [ ] Add policy RED cases for leading zero, expiry boundary, wrong code, resend before/after 30s,
  invalid old generation, consumed code, account disabled/email changed, SMTP/store failure and
  unknown-account decoy. Example contract expectations:

~~~java
assertEquals(VerifyOutcome.VERIFIED, firstConcurrentResult);
assertNotEquals(VerifyOutcome.VERIFIED, secondConcurrentResult);
assertEquals(VerifyOutcome.INVALID, verifyPreviousGenerationAfterResend);
assertEquals(VerifyOutcome.EXHAUSTED, sixthSubmissionInRecoveryWindow);
~~~

- [ ] Implement REQUIRED Authenticator/Factory provider knora-reset-email-otp. It owns email request,
  verify and resend and replaces native Choose User + Send Reset Email. On successful verification,
  set the user and END_AFTER_REQUIRED_ACTIONS, then continue to native Reset Password/UPDATE_PASSWORD.
  Disable Reset – Conditional OTP; preserve the user's enrolled authenticator credentials.
- [ ] Render six-digit entry with paste/leading-zero support and accessible labels; enforce the
  server cooldown regardless of JavaScript. Use generic unknown/disabled/delivery-failure output.
  Never include code/password/body in logs or application URLs.
- [ ] Package the JAR before kc.sh build in the existing Dockerfile. Use provided-scope Keycloak
  dependencies pinned to 26.3.3, JUnit for policy tests and failsafe integration tests in verify.
- [ ] Run:

~~~powershell
mvn -f infra/keycloak/providers/email-otp-reset/pom.xml clean verify
docker build -f infra/keycloak/Dockerfile -t knora-keycloak:26.3.3-otp .
./.venv/Scripts/python -m pytest backend/test/config/test_keycloak_theme.py
~~~

- [ ] Review security/concurrency evidence and compare AU10/AU11/AU11B/AU12/AU1B.
  Commit as feat: add Keycloak email OTP password recovery.

**Acceptance:** real test email → one-time code → native password update; replay/parallel requests
and account-wide budget bypass fail; all sensitive POSTs remain at Keycloak; existing MFA survives.

## Task I3: BFF errors, reset completion and account menu

**Skills:** executing-plans, test-driven-development, verification-before-completion.

**Dependency:** I2 + F2 + U1.

**Modify:** frontend/app/api/auth/login/route.ts, callback/route.ts;
frontend/components/shell/AccountMenu.tsx;
themes/knora/login/info.ftl; frontend/middleware.ts only for explicitly public error routes.

**Create:** frontend/app/auth/unavailable/page.tsx, frontend/app/auth/failed/page.tsx;
frontend/tests/auth-figma-integration.test.tsx.
**Test:** frontend/tests/e2e/figma-identity.spec.ts and m5-authentication.spec.ts.

**Consumes:** existing authorization transaction/session helpers. **Produces:** safe error pages
and one allowlisted login option, without changing the callback validation contract.

- [ ] Add RED tests: missing configuration → unavailable; failed/tampered callback → failed;
  retry creates fresh transaction; arbitrary redirect/prompt input is ignored; prompt=login is
  accepted; nonce/state/PKCE remain unique and validated.
- [ ] Implement the fixed option:

~~~ts
const requestedPrompt = new URL(request.url).searchParams.get("prompt");
if (requestedPrompt === "login") url.searchParams.set("prompt", "login");
~~~

Keep the rest of the existing authorization URL construction and transaction cookie behavior.
Do not echo untrusted callback error text or include tokens in error URLs.

- [ ] Route browser failures to designed AU3/AU4 pages with safe retry links. Clear invalid
  transaction cookies as appropriate while preserving the existing completed-login recovery path.
- [ ] Set reset-complete CTA to the fixed trusted /api/auth/login?prompt=login URL. With an existing
  SSO cookie, assert the sign-in form appears and a fresh transaction is used.
- [ ] Finish AU5 account menu using safe identity/initials and existing theme/logout controls;
  clear scoped panel preferences on sign-out. Confirm active/new-account landing routes.
- [ ] Run:

~~~powershell
npm --prefix frontend run test -- auth
npm --prefix frontend run typecheck
npm --prefix frontend run format
npm --prefix frontend run format:check
npm --prefix frontend run test:e2e -- figma-identity.spec.ts m5-authentication.spec.ts
~~~

- [ ] Review/commit as feat: integrate Figma auth outcomes and reset sign-in.
