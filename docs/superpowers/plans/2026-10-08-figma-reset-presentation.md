# Figma reset presentation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Match reset request, verification and new-password labels and countdown presentation from
fresh Figma MCP while retaining native Keycloak protocol and privacy.
**Architecture:** Modify existing message keys and local native templates. Actual FreeMarker renders
with pinned parents remain the test subject; the fixture cannot authorize a recovery transaction.
**Tech Stack:** Keycloak26.3.3, FreeMarker2.3.32, Java21, existing CSS; Playwright/TypeScript.
**Spec:** [Approved integration design](../specs/2026-10-05-figma-ui-integration-design.md).

## Global Constraints

- Keycloak owns credentials, OTP/password decisions, cooldown and attempt budgets.
- Keep native action URLs, POST field names/intents, leading-zero input, escaping, no-JS fallback,
  password policy, logout-other-sessions and app-initiated cancellation.
- No realm/reset binding, password/Vault/SMTP/service/outage/deletion actions, installs, dependencies,
  merge/push, cleanup, generated API or shared frontend/theme CSS changes.
- Read complete MCP structure before edits; screenshot is a visual target, never an asset.
- Preserve exact existing local static assets and semantic accessible colors.
- Frontend format then format:check is mandatory for maintained frontend edits.
- Offline fixture/FreeMarker results do not prove native reset, CSP/MFA/Vault/replay or full acceptance.

## Directory ownership

| File | Responsibility |
| --- | --- |
| `themes/knora/login/messages/messages_en.properties` | Source copy with privacy adaptation |
| `themes/knora/login/knora-reset-otp.ftl` | Server cooldown rendered as minutes:seconds and existing enhancement |
| `themes/knora/login/login-update-password.ftl` | Source labels for ordinary reset, retained app-initiated controls |
| `infra/keycloak/providers/email-otp-reset/src/test/java/com/knora/keycloak/reset/EmailOtpResetFlowIT.java` | Actual request/OTP FreeMarker copy and no-JS cooldown regression |
| `frontend/tests/e2e/figma-ui-interactions.spec.ts` | Actual exported template presentation and JS countdown behavior |
| `frontend/tests/e2e/support/FigmaThemeRenderer.java` | Exact pinned parent password-visibility resource for offline interaction |
| `docs/development/figma-ui-visual-coverage.md` | Resolved copy/countdown and explicit remaining native/geometry limits |

No changes to exporter script, authenticator/store/service/POM, theme CSS or production assets.
The renderer's sole resource correction below is required by the discovered toggle regression.

## Task 1: Correct reset labels and server countdown presentation

**Dependency:** Trace result/candidate independently reviewed; record original clean BASE.
**Skills:** figma-design-to-code, test-driven-development, systematic-debugging,
verification-before-completion, requesting-code-review.
**Source:** Complete fresh contexts and returned renders in this plan's SDD `source/` directory:
242-272,242-333,242-389,246-311. They were retrieved directly by root, returned screenshots viewed,
no sparse response. Current brand18 leaf and password eye18 assets already local and unchanged.

- [ ] Read sources, native templates, existing actual-parent tests and renderer. Label mapping:

  ```properties
  updatePasswordTitle=Choose a new password
  knoraPasswordDescription=Set a new password for your Knora account.
  knoraConfirmNewPassword=Confirm new password
  knoraResetPassword=Reset password
  knoraResetPasswordReturn=After resetting your password, sign in again with the new password.
  knoraResetEmailTitle=Forgot your password?
  knoraResetEmailDescription=Enter the email for your account. If an account exists, we’ll send a 6-digit verification code.
  knoraResetSendCode=Send verification code
  knoraResetRemembered=Remembered it?
  knoraResetPrivacy=For privacy, Knora won’t confirm whether an account exists for this email.
  knoraOtpTitle=Enter verification code
  knoraOtpDescription=If an account exists, we sent a 6-digit verification code to {0}.
  knoraOtpChangeEmail=Use a different email
  knoraOtpResendPending=Resend code in
  ```

  Preserve knoraOtpExpires actual5-minute copy and generic invalid/error copy: provider may return
  a generic failure for budgets/storage as well as wrong/expired code. Do not falsely specialize it.
  Keep anti-enumeration prefix in OTP description instead of source's unconditional sent assertion;
  maskedEmail remains runtime escaped, not source literal. Document these intentional adaptations.
- [ ] RED actual FreeMarker assertions on request/OTP labels, escaped address and countdown:
  server30→00:30,61→01:01,0→Resend code without pending phrase/countdown. Keep existing native no-JS
  enabled-button and POST/value/formnovalidate assertions. Existing baseline copy must fail before
  production edit. Browser RED for reset request/new-password source labels and both existing OTP
  interactions, after exporting unchanged source with existing offline exporter.

  ```java
  assertTrue(request.contains("Forgot your password?"));
  assertTrue(request.contains("Send verification code"));
  assertTrue(otp.contains("Enter verification code"));
  assertTrue(otp.contains("Use a different email"));
  assertTrue(otp.contains("If an account exists"));
  ```

  Browser uses existing prepareFixture242:272/242:333/242:389/246:311; native submissions blocked.
  Preserve accessible code/password labels/IDs/autocomplete and both password visibility toggles.
- [ ] Apply exact dictionary values. In login-update-password.ftl use scoped confirm key and
  `label="knoraResetPassword"` only ordinary non-app-initiated branch; preserve app-initiated
  Submit/Cancel unchanged. Add source return instruction only non-app-initiated branch after form
  actions, using existing knora-disclaimer class. Keep logout-other-sessions and policy scripts.
  Copy communicates the intended next step; it is not a native success proof.
- [ ] OTP pending button stays enabled in server markup for no-JS, with unchanged native intent.
  Render label span, server numeric data and zero-padded countdown:

  ```ftl
  <#assign retry = retryAfterSeconds!0>
  <span id="otp-resend-label"><#if retry gt 0>${msg("knoraOtpResendPending")}<#else>${msg("knoraOtpResend")}</#if></span><#if retry gt 0> <span id="otp-retry" data-seconds="${retry?c}">${(retry / 60)?floor?string("00")}:${(retry % 60)?string("00")}</span></#if>
  ```

  Keep button `data-ready-label="${msg("knoraOtpResend")}"` for localized ready label.
  Enhancement reads Number(countdown.dataset.seconds), preserving finite/positive guard and
  Date-based250ms timer. Format displayed remaining:
  ```js
  const formatCountdown = (seconds) =>
    `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  ```
  At zero enable existing button, set label from ready data, remove countdown, clear interval.
  Server admission remains authority. No-JS can submit early as already supported fallback;
  pending information reflects server render and does not imply client-enforced admission.
- [ ] GREEN offline FlowIT focused new presentation + existing no-JS methods using cached pinned
  Maven container offline/network-none/read-only proof cache. Then complete EmailOtpResetFlowIT
  only for native translation consistency, not storage-proof/native lifecycle suite. No clean
  (avoid classifier removal), downloads or service restart. Exact command:
  ```powershell
  docker run --rm --network none --mount "type=bind,source=C:/Developer/Projects/knora-agent-worktree/figma-ui-identity,target=/work" --mount "type=volume,source=knora-figma-e2e_maven-proof-cache,target=/root/.m2,readonly" --workdir /work/infra/keycloak/providers/email-otp-reset --entrypoint mvn maven:3.9.9-eclipse-temurin-21 -o '-Dtest=EmailOtpResetFlowIT' test
  ```
- [ ] Export actual templates using `node frontend/tests/e2e/support/figma-theme-export.mjs`
  without live-parent flag; verify existing pinned parent resources/hashes. Targeted browser GREEN
  source-copy test and two existing native FTL OTP tests. JS proves00:30 disabled,00:01 disabled,
  ready Resend code enabled/countdown absent at30; no-JS proves enabled native button and00:30.
  Leading-zero paste, six mirror cells, invalid role and56px input checks retained.
  Native blocked action remains blocked; never submit password/reset.
- [ ] Resolve the observed offline toggle failure at its resource boundary. Existing rendered
  password HTML references `/resources/js/passwordVisibility.js`, but the renderer excludes the
  base login resources prefix. In the existing pinned JarFile block, read only
  `theme/base/login/resources/js/passwordVisibility.js`, require that entry exists, verify its
  unchanged bytes length698 and SHA256
  `6DF35FB0B98BFC3B78BB9936FCECA7D91BB53DCC0CD3DF7399B4FA3537C565ED`, then copy those exact bytes to
  `output/resources/js/passwordVisibility.js`. Use existing JDK APIs, no dependency or broad
  prefix expansion. Keep native toggle clicks/type password→text→password assertions for both
  empty fields; do not replace functionality assertions with markup preservation. Re-export offline
  and rerun only failed source-copy browser case; two OTP GREEN cases remain valid. Report the
  missing-resource RED, exact pinned JAR/entry proof and new resource hash. This is offline
  reference extraction, not a theme/service asset edit or live fetch.
  The password fixture must also set `pageId` to `login-update-password` for state242-389 only,
  matching the native parent body prefix `login-` and existing theme selector
  `body[data-page-id="login-login-update-password"]`. Keep the exact42cef asset assertion;
  other fixture page IDs remain unchanged. This corrects offline page identity, without CSS edits.
- [ ] Capture only four affected states at1440×960/390×844 with empty code/password values;
  preserve previous captures as historical evidence, use new reset-presentation evidence subdirectory.
  Capture JSON copy/fit/input/button/static asset effective geometry. Compare returned full wrapper
  source with annotation strip accounted for; do not crop or alter source artifacts. Record residual
  content origin/field/notice/CSS geometry; no page parity acceptance from labels.
  Before/after whole Q1 hashes exclude only root active regression-preflight. Offline exporter may
  legitimately change four native HTMLs and add the exact698-byte parent script above; enumerate
  changes/addition and preserve unrelated HTML/resources.
  Both new current captures and new HTML differences explicitly allowed; no blanket rebaseline.
  Preservation exception: cached246-404 success HTML predates accepted completion-origin validation
  commit5614653. Retain the current-source export and separately preserve the exactly reproduced
  historical4491-byte HTML/hash with its old-source identity in this task's SDD evidence. Record the
  fifth difference as prior-source formatting drift, not a reset change or new completion proof.
- [ ] Run format→format:check→typecheck sequentially, self-review exact seven paths, release owned3300,
  commit exactly seven owned paths and report command results, source mapping, RED/GREEN, hashes/visual QA,
  privacy/no-JS/generic-error adaptations and native blockers. Root independent originalBASE→HEAD review.

**Finish condition:** Source labels and actual server-derived countdown proven through existing native
templates, privacy/protocol/no-JS preservation reviewed. Native binding/live reset remain held.
