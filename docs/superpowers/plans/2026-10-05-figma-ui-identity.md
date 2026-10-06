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

## Task 1: I1 — Keycloak presentation and registration

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

**Exact assets:** themes/knora/login/resources/images/* for the original leaf/orbit and password
eye-off assets actually used by I1; include a local figma-assets.json provenance/checksum manifest
and .gitattributes (`*.svg -text`). Copy original bytes from the shared Figma cache, preserve
intrinsic dimensions, and verify rendered geometry. Use Keycloak resource URLs rather than Next
public URLs; later I2/I3 append only assets with their own designed callsites.

**Isolated test harness:** create docker-compose.figma-e2e.yml, scripts/prepare-figma-e2e.ps1,
test/fixtures/keycloak/figma-realm.json, frontend/playwright.figma.config.ts,
frontend/tests/e2e/support/figma-environment.ts, figma-auth.ts, figma-environment.test.ts and
backend/test/config/test_figma_e2e_harness.py. These are test infrastructure for the approved
real-browser requirement. Use project knora-figma-e2e and fixed loopback ports: frontend3300,
API8800, Keycloak8380, Postgres5543, Minio9900/9901, test SMTP1025/mailbox8025. Recheck availability.
Validate exact project, ports, realm and ambient override rejection before mutations. Use separate
Keycloak/Postgres database and project-namespaced volumes, idempotent migrations/fixture setup;
ordinary startup must not delete/reset resources. Preserve daily services and all existing M5
endpoint guards/configuration. I2 extends this harness for the real provider/two-node proof.

**Consumes:** F2 local brand/font assets; pinned native templates and form contract.
**Produces:** branded templates retaining Keycloak native loginAction, field names, hidden state,
validation and escaping. Account menu remains an application component from F2/I3.

Proposed realm choices: registrationAllowed=true, resetPasswordAllowed=true,
loginWithEmailAllowed=true, duplicateEmailsAllowed=false. Keep username registration and add email
sign-in. Do not silently add a mandatory email-verification screen absent from this Figma; retain
the current verifyEmail setting and document it. Use a test SMTP server for reset integration.
AU8/AU9 collect username/email/password/confirmation only. Pinned Keycloak's default profile also
requires firstName/lastName for users; make those two native attributes optional for registration
in the exact target development/test realm. Preserve their existing values, validation, permissions
and every unrelated/custom attribute. Include profile inspect/diff/apply and saved prior profile
for rollback in the configuration script. Do not invent hidden names or add name fields absent
from this design. If additional required custom attributes conflict, report before applying.

- [ ] Add real-browser failing checks for sign-in default/invalid, registration default/validation,
  successful fresh registration landing in the backend-created active My Workspace, and password
  confirmation/policy errors. Separately archive the owned Workspace through the real API with
  its current revision, then prove NO_ACTIVE_WORKSPACE landing. Preserve the existing resolver's
  first-identity default creation; do not fabricate an empty fresh-account state.
- [ ] Establish the isolated harness and guard tests before live identity checks. Derive only the
  test realm/client callback for frontend3300; keep daily/dev fixture endpoints compatible. Do not
  run the existing destructive prepare-local-e2e script against running daily services.
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

## Task 2: I2 — Keycloak email OTP provider

**Skills:** research, codebase-design, test-driven-development, executing-plans,
requesting-code-review and verification-before-completion.

**Dependency:** I1. Resolve and prove storage atomicity before connecting real password changes.

**Create under infra/keycloak/providers/email-otp-reset:**

- pom.xml
- .gitignore (Maven target/ only)
- src/main/java/com/knora/keycloak/reset/EmailOtpResetAuthenticator.java
- src/main/java/com/knora/keycloak/reset/EmailOtpResetAuthenticatorFactory.java
- src/main/java/com/knora/keycloak/reset/OtpChallengeService.java
- src/main/java/com/knora/keycloak/reset/OtpChallengeStore.java
- src/main/java/com/knora/keycloak/reset/KeycloakOtpChallengeStore.java
- src/main/resources/META-INF/services/org.keycloak.authentication.AuthenticatorFactory
- src/test/java/com/knora/keycloak/reset/OtpChallengeServiceTest.java
- src/test/java/com/knora/keycloak/reset/EmailOtpResetFlowIT.java
- src/test/java/com/knora/keycloak/reset/OtpChallengeConcurrencyIT.java
- src/test/probe/java/com/knora/keycloak/reset/probe/StorageProbeResource.java
- src/test/probe/java/com/knora/keycloak/reset/probe/StorageProbeResourceFactory.java
- src/test/probe/resources/META-INF/beans.xml
- src/test/probe/resources/META-INF/services/org.keycloak.services.resource.RealmResourceProviderFactory
- src/main/java/com/knora/keycloak/reset/persistence/OtpRecoveryWindowEntity.java
- src/main/java/com/knora/keycloak/reset/persistence/OtpChallengeEntity.java
- src/main/java/com/knora/keycloak/reset/persistence/OtpJpaEntityProvider.java
- src/main/java/com/knora/keycloak/reset/persistence/OtpJpaEntityProviderFactory.java
- src/main/resources/META-INF/services/org.keycloak.connections.jpa.entityprovider.JpaEntityProviderFactory
- src/main/resources/META-INF/knora-otp-changelog.xml

**Create for storage proof only:** docker-compose.figma-otp-proof.yml,
scripts/prepare-figma-otp-proof.ps1.
Test-only scripts/figma-otp-pg-commit-proxy.py may be added for a controlled lost-COMMIT-response
schedule: owned proof node only, isolated Keycloak database, internal network with no host port.
Arm exactly one synthetic probe connection; forward COMMIT, confirm backend completion, then
suppress its reply and close that connection. Bound timeouts and never log credentials, SQL or
payloads. Assert adapter UNAVAILABLE/no mail authorization while the survivor reads committed
budget; restore direct proof-node configuration and disarm after the test. This fault component
must never enter production images or Compose graphs.

The Maven storage-proof profile produces a separate
storage-probe classifier JAR from test/probe sources; neither those classes nor the JAR may enter
the production provider artifact or image. The override adds a second owned test node on
127.0.0.1:8381 after checking port availability, exact project ownership and ambient selectors.
The probe requires explicit enablement, the exact isolated knora-dev realm, a secret
X-Knora-Storage-Proof header and a knora-otp-proof: key namespace scoped to the realm ID.
Never log the header. Bounded in-process latches may schedule transactions; storage under test
must remain the real KeycloakSession/SingleUseObjectProvider. Preserve the existing test project.

**Create:** themes/knora/login/knora-reset-email.ftl, knora-reset-otp.ftl;
themes/knora/email/theme.properties; themes/knora/email/html/knora-reset-otp.ftl;
themes/knora/email/text/knora-reset-otp.ftl;
themes/knora/email/messages/messages_en.properties.

**Modify:** infra/keycloak/Dockerfile, scripts/configure-keycloak-auth-flow.ps1,
test/fixtures/keycloak/dev-realm.json, docs/development/keycloak-theme.md;
add isolated test SMTP/container configuration to the identity integration harness.
Also modify themes/knora/login/messages/messages_en.properties and
themes/knora/login/resources/css/knora.css for the owned OTP labels and layout.

**Remaining source implementation while the physical database outage gate is blocked:**
implement the unbound Authenticator/Factory, login/email templates and meaningful offline
translation/rendering tests within the listed paths. Compile/package and inspect the production
artifact without applying the reset flow, reloading the provider into live password recovery or
performing real password changes. These tests are source evidence, not native acceptance.
The blocked outage test must not be retried through an equivalent workaround.

**Shared HMAC configuration:** obtain a Base64 secret of at least 32 bytes from Keycloak Vault
using entry `knora-email-otp-hmac-` plus lowercase SHA-256 hex of the actual realm ID. The pinned
file Vault provider prefixes physical entries using realm name; this does not constitute native
realm-ID isolation. The application entry adds the ID namespace. Missing, malformed or
unavailable keys fail closed before store/SMTP; no random, environment or plaintext fallback.
Use request-local secret handling and close Vault values; do not claim complete JVM zeroization.
All nodes and restarts use the same stable key. Hot rotation is unsupported because changing
the key changes budget identities. Rotation requires disabling recovery on all nodes, draining
all in-flight requests/SMTP, waiting a full 15-minute window plus transaction drain, then
coordinating the replacement across all nodes before re-enabling. SMTP drain is not assumed
bounded by the five-second JTA limit. No mixed-key rolling interval or fallback key ring.
Document operator provisioning without editing daily Compose or production secrets. Future
test-only Vault mounts may use the existing proof Compose/preparation paths after a separate
runtime scope ruling; ordinary harness changes require an explicit path amendment.

**Interface design:** the Authenticator delegates recovery policy to OtpChallengeService.
The initial SingleUseObjectProvider anchored initializer was rejected by actual two-node
expiry/stale-holder proof on 2026-10-06. Next prove a private relational adapter in Keycloak's
own PostgreSQL database through the pinned custom JPA entity seam; no Knora database access.
Keep the KeycloakOtpChallengeStore facade. The custom JPA API is unsupported and requires
upgrade retesting. Use atomic initial-row admission, IP-before-account lock order, fresh database
time after locks and exact generation checks. Preserve fixed 15-minute account/IP windows,
five verification attempts, three account sends, twenty IP sends, 30-second cooldown and
five-minute code expiry. Resend never resets the account verification budget.
Prove bounded independent transactions in actual Quarkus/JTA, including suspension/restoration
of the outer transaction and thread-local session. Observe completion of the exact independent
transaction; callback return alone is insufficient. Publish successful transitions only after
STATUS_COMMITTED; rollback-only, unknown completion and restoration failure are UNAVAILABLE.
Commit budgets and a digest-only PENDING challenge before SMTP. PENDING cannot verify;
failed/ambiguous reservation completion prevents SMTP. Failed/ambiguous SMTP leaves PENDING
unverifiable and retains budgets without relying on another invalidation write.
After known SMTP success, activate only the existing exact scope/generation under account and
challenge locks with a unique server-generated activation operation ID. Reject expired, consumed,
cancelled, missing or rotated rows; same-operation ACTIVE is idempotent, different operations fail.
On ambiguous activation completion, permit one bounded independently committed reconciliation
of the same operation ID and exact ACTIVE, unexpired, unconsumed scope/generation. No repeated
SMTP or reservation. Confirmed committed reconciliation may publish success; unconfirmed results
remain UNAVAILABLE. Delivered ACTIVE state may survive reply loss and later be confirmed; generic
responses or unavailable cancellation do not establish invalidation. Verification requires ACTIVE
and confirmed committed consume. Generation-conditional follow-ups never recreate state or refund
budgets. Actual proofs cover rollback-only after successful SQL, lost activation reply, crash
between SMTP and activation, late activation after resend and failed follow-up.
The existing test-only probe may wrap and delegate real session/JPA query calls to mark the real
independent transaction rollback-only after actual insertion/consume. No production injection or
mock completion result; observe durable outcomes on the other node and restored caller context.
First-row races, lock order/timeouts, caller rollback, commit visibility, crash/expiry, competing
resend/verify and SMTP failure all require actual two-node proof before password integration.
Relational proof may extend the existing test-only probe and concurrency test at their scoped
paths. If runtime isolation cannot be proved, record the precise failure and revise the protocol.
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
- [ ] Use the test-only probe to observe both commit orders, deferred publication, rollback,
  duplicate queued writes, token consume races and expiry/stale-holder replacement. Keep fault
  characterization and deliberately failing safety assertions distinct from acceptance. A
  characterized candidate failure does not establish that every SPI protocol is impossible.
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

## Task 3: I3 — BFF errors, reset completion and account menu

**Skills:** executing-plans, test-driven-development, verification-before-completion.

**Dependency:** accepted I2 storage/service and unbound adapter source + F2 + U1 for frontend
and source implementation. Full native reset-complete/password/SSO acceptance still depends on
I2 runtime gates. While physical outage is blocked, implement and review the I3 source without
reset-flow application, live password changes or claiming native completion. Local tests/build
and prepared browser assertions remain partial evidence. This split permits safe source progress
without waiving the pending I2 gates.

**Modify:** frontend/app/api/auth/login/route.ts, callback/route.ts;
frontend/components/shell/AccountMenu.tsx;
themes/knora/login/info.ftl; frontend/middleware.ts only for explicitly public error routes.

**Create:** frontend/app/auth/unavailable/page.tsx, frontend/app/auth/failed/page.tsx;
frontend/tests/auth-figma-integration.test.tsx.
Create frontend/components/auth/AuthOutcome.tsx and auth-outcome.css for the shared AU3/AU4
composition, and frontend/components/shell/account-menu.css for scoped AU5 styling. Preserve
shared global/provider CSS; use semantic Tailwind utilities and only necessary scoped overrides.
Modify frontend/tests/auth-session.test.ts and frontend/tests/auth-callback-resolver.test.ts
for callback RED cases and preservation of completed-login workspace recovery.
Extend the existing offline template cases in
infra/keycloak/providers/email-otp-reset/src/test/java/com/knora/keycloak/reset/EmailOtpResetFlowIT.java
to render the trusted reset-completion CTA and preserve unfinished native action links. Do not
change provider policy/service source for I3. The fixed application path resolves against trusted
configured client base URL, not the Keycloak page origin or submitted/request redirect data.
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
