import { createHmac, randomUUID } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import {
  captureIdentity,
  fillRegistration,
  openFigmaLogin,
  openFigmaRegistration,
} from "./support/figma-auth";

const keycloakOrigin = "http://127.0.0.1:8380";
const applicationOrigin = "http://127.0.0.1:3300";
const realmPath = "/realms/knora-dev/";
const evidenceDirectory = path.resolve(
  process.cwd(),
  "../.superpowers/sdd/2026-10-08-figma-otp-native-runtime/evidence/native-otp-runtime-2026-10-08",
);

type Credential = { id: string; type: string };
type MailMessage = { ID: string; To: { Address: string }[] };

// Secrets stay inside the bounded callback. Replace the entire native DOM before a
// failure reaches Playwright's reporter/error-context serializer.
async function sanitizeFailure(context: BrowserContext) {
  for (const page of context.pages()) {
    await page
      .evaluate(() => {
        document.documentElement.innerHTML =
          "<head><title>Native stage failed</title></head><body>Sanitized native stage failure</body>";
      })
      .catch(() => undefined);
  }
}

async function sensitive(stage: string, action: () => Promise<unknown>) {
  try {
    await action();
  } catch {
    throw new Error(`NATIVE_STAGE_${stage}`);
  }
}

async function nativeForm(page: Page, input: string) {
  const form = page.locator(`form:has(${input})`);
  const action = await form.getAttribute("action");
  expect(
    Boolean(
      action &&
        new URL(action, page.url()).origin === keycloakOrigin &&
        new URL(action, page.url()).pathname.startsWith(realmPath),
    ),
  ).toBe(true);
  return form;
}

async function submit(
  page: Page,
  input: string,
  intent: string,
  stage: string,
  bypass = false,
) {
  await sensitive(stage, async () => {
    const form = await nativeForm(page, input);
    const button = form.locator(`button[name="intent"][value="${intent}"]`);
    if (bypass)
      await button.evaluate((element: HTMLButtonElement) => {
        element.disabled = false;
        element.form!.noValidate = true;
        element.form!.requestSubmit(element);
      });
    else await button.click();
  });
}

async function guardedContext(context: BrowserContext) {
  let rejected = false;
  await context.route("**/*", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      const fields = new URLSearchParams(request.postData() ?? "");
      const sensitiveFields = [
        "password",
        "password-new",
        "password-confirm",
        "code",
        "totp",
        "otp",
        "totpSecret",
      ];
      if (sensitiveFields.some((field) => fields.has(field))) {
        const destination = new URL(request.url());
        if (
          destination.origin !== keycloakOrigin ||
          !destination.pathname.startsWith(realmPath)
        ) {
          rejected = true;
          await route.abort();
          return;
        }
      }
    }
    await route.continue();
  });
  return () => expect(rejected).toBe(false);
}

async function capture(page: Page, state: string) {
  await sensitive("CAPTURE", async () => {
    // Clearing fires the template's paint handler, removing digits from six cells.
    for (const input of await page.locator("#code, #otp, #totp").all())
      await input.fill("");
    expect(await page.locator("#kc-totp-settings").count()).toBe(0);
    await mkdir(evidenceDirectory, { recursive: true });
    const suffix = test.info().project.name;
    await captureIdentity(
      page,
      path.join(evidenceDirectory, `${state}-${suffix}.png`),
    );
    const geometry = await page.locator(".knora-auth").boundingBox();
    await writeFile(
      path.join(evidenceDirectory, `${state}-${suffix}.json`),
      JSON.stringify(
        {
          state,
          viewport: page.viewportSize(),
          geometry,
          horizontalOverflow: await page.evaluate(
            () => document.documentElement.scrollWidth > window.innerWidth,
          ),
        },
        null,
        2,
      ),
    );
  });
}

async function messages(page: Page, email: string): Promise<MailMessage[]> {
  const response = await page.request.get(
    "http://127.0.0.1:8025/api/v1/messages",
  );
  expect(response.ok()).toBe(true);
  const mailbox = await response.json();
  return mailbox.messages.filter((message: MailMessage) =>
    message.To.some((recipient) => recipient.Address === email),
  );
}

async function deliveredCode(page: Page, email: string, seen: Set<string>) {
  let messageId = "";
  await expect
    .poll(
      async () => {
        const message = (await messages(page, email)).find(
          (entry) => !seen.has(entry.ID),
        );
        messageId = message?.ID ?? "";
        return Boolean(messageId);
      },
      { timeout: 20_000 },
    )
    .toBe(true);
  seen.add(messageId);
  const detail = await page.request.get(
    `http://127.0.0.1:8025/api/v1/message/${messageId}`,
  );
  expect(detail.ok()).toBe(true);
  const body = await detail.json();
  const code = String(body.Text).match(/\b[0-9]{6}\b/)?.[0] ?? "";
  expect(/^[0-9]{6}$/.test(code)).toBe(true);
  return code;
}

async function adminCredentials(page: Page, username: string) {
  const tokenResponse = await page.request.post(
    `${keycloakOrigin}/realms/master/protocol/openid-connect/token`,
    {
      form: {
        client_id: "admin-cli",
        grant_type: "password",
        username: "figma-test-admin",
        password: "figma-test-admin-password",
      },
    },
  );
  expect(tokenResponse.ok()).toBe(true);
  const token = (await tokenResponse.json()).access_token;
  const headers = { Authorization: `Bearer ${token}` };
  const usersResponse = await page.request.get(
    `${keycloakOrigin}/admin/realms/knora-dev/users`,
    { headers, params: { username, exact: "true" } },
  );
  expect(usersResponse.ok()).toBe(true);
  const users = await usersResponse.json();
  expect(users.length === 1 && users[0].username === username).toBe(true);
  const response = await page.request.get(
    `${keycloakOrigin}/admin/realms/knora-dev/users/${users[0].id}/credentials`,
    { headers },
  );
  expect(response.ok()).toBe(true);
  return (await response.json()).map((credential: Credential) => ({
    id: credential.id,
    type: credential.type,
  })) as Credential[];
}

function totp(secret: string) {
  const normalized = secret.replace(/\s/g, "").toUpperCase();
  expect(/^[A-Z2-7]+$/.test(normalized)).toBe(true);
  let bits = "";
  for (const character of normalized)
    bits += "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
      .indexOf(character)
      .toString(2)
      .padStart(5, "0");
  const bytes = Buffer.from(
    Array.from({ length: Math.floor(bits.length / 8) }, (_, index) =>
      parseInt(bits.slice(index * 8, index * 8 + 8), 2),
    ),
  );
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30_000)));
  const digest = createHmac("sha1", bytes).update(counter).digest();
  bytes.fill(0);
  const offset = digest[digest.length - 1] & 15;
  return String(
    (digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000,
  ).padStart(6, "0");
}

test("native recovery, resend, consume and fresh sign-in preserve credential authority", async ({
  page,
  browser,
}) => {
  test.setTimeout(180_000);
  let stage = "REGISTRATION";
  const ownedContexts: BrowserContext[] = [page.context()];
  const guards: (() => void)[] = [];
  let ssoCookieMetadata: unknown[] = [];
  try {
    guards.push(await guardedContext(page.context()));
    const username = `figma-otp-${randomUUID()}`;
    const identity = {
      username,
      email: `${username}@example.test`,
      password: `Old-${randomUUID()}-Password`,
    };
    const newPassword = `New-${randomUUID()}-Password`;
    await openFigmaRegistration(page);
    await nativeForm(page, "#password");
    await sensitive(stage, () => fillRegistration(page, identity));
    await sensitive(stage, () =>
      page.getByRole("button", { name: "Create account", exact: true }).click(),
    );
    await page.waitForURL(/\/workspaces\/[0-9a-f-]+$/, { timeout: 30_000 });
    const workspaceUrl = page.url();
    expect(new URL(workspaceUrl).origin === applicationOrigin).toBe(true);

    // Desktop proves the supported CONFIGURE_TOTP action on only this new account.
    let totpSecret = "";
    let enrolled: Credential | undefined;
    if (test.info().project.name === "desktop1440x960") {
      stage = "MFA_AUTHORIZATION";
      // Use the BFF's fresh authorization redirect, before Keycloak rewrites it to
      // a login action. The request context retains the transaction cookie.
      const authorization = await page.request.get(
        `${applicationOrigin}/api/auth/login?prompt=login`,
        { maxRedirects: 0 },
      );
      expect(authorization.status() === 307).toBe(true);
      const enrollment = new URL(authorization.headers().location);
      expect(
        enrollment.origin === keycloakOrigin &&
          enrollment.pathname === `${realmPath}protocol/openid-connect/auth`,
      ).toBe(true);
      enrollment.searchParams.set("kc_action", "CONFIGURE_TOTP");
      await sensitive(stage, () => page.goto(enrollment.toString()));
      stage = "MFA_CREDENTIAL_LOGIN";
      if (await page.locator("#kc-form-login").count()) {
        await sensitive(stage, () =>
          page.locator("#username").fill(identity.email),
        );
        await sensitive(stage, () =>
          page.locator("#password").fill(identity.password),
        );
        await sensitive(stage, () => page.locator("#kc-login").click());
      }
      stage = "MFA_SETUP_FORM";
      await expect(page.locator("#kc-totp-settings-form")).toBeVisible();
      stage = "MFA_MANUAL_MODE";
      await sensitive(stage, () => page.locator("#mode-manual").click());
      stage = "MFA_NATIVE_SECRET";
      totpSecret =
        (await page.locator("#kc-totp-secret-key").textContent()) ?? "";
      await nativeForm(page, "#totp");
      stage = "MFA_SETUP_SUBMIT";
      await sensitive(stage, () =>
        page.locator("#totp").fill(totp(totpSecret)),
      );
      await sensitive(stage, () =>
        page.locator("#userLabel").fill("Isolated native OTP proof"),
      );
      await sensitive(stage, () => page.locator("#saveTOTPBtn").click());
      stage = "MFA_RETURN_WORKSPACE";
      await page.waitForURL(/\/workspaces\/[0-9a-f-]+$/, { timeout: 30_000 });
      const credentials = await adminCredentials(page, username);
      const otpCredentials = credentials.filter(
        (credential) => credential.type === "otp",
      );
      expect(otpCredentials.length === 1).toBe(true);
      enrolled = otpCredentials[0];
    }

    stage = "EXISTING_SSO_LOGIN";
    const ssoContext = await browser.newContext({
      baseURL: applicationOrigin,
      viewport: test.info().project.use.viewport,
    });
    ownedContexts.push(ssoContext);
    guards.push(await guardedContext(ssoContext));
    const ssoPage = await ssoContext.newPage();
    await openFigmaLogin(ssoPage);
    await sensitive(stage, () =>
      ssoPage.locator("#username").fill(identity.email),
    );
    await sensitive(stage, () =>
      ssoPage.locator("#password").fill(identity.password),
    );
    await sensitive(stage, () => ssoPage.locator("#kc-login").click());
    await ssoPage.waitForURL(/\/workspaces\/[0-9a-f-]+$/, { timeout: 30_000 });

    stage = "EMAIL";
    const recovery = await browser.newContext({
      baseURL: applicationOrigin,
      viewport: test.info().project.use.viewport,
    });
    ownedContexts.push(recovery);
    guards.push(await guardedContext(recovery));
    const reset = await recovery.newPage();
    await openFigmaLogin(reset);
    const initialAuthorization = new URL(reset.url()).searchParams;
    await sensitive(stage, () =>
      reset.getByRole("link", { name: "Forgot Password?" }).click(),
    );
    await expect(reset.locator("#email")).toBeVisible();
    await capture(reset, "empty-email");
    await sensitive(stage, () => reset.locator("#email").fill(identity.email));
    await submit(reset, "#email", "request", stage);
    await expect(reset.locator("#code")).toBeVisible();
    await capture(reset, "empty-otp");
    const knownChallengeHeading = await reset
      .locator("#kc-page-title")
      .innerText();
    const seen = new Set<string>();
    stage = "EMAIL_DELIVERY";
    const firstCode = await deliveredCode(page, identity.email, seen);

    stage = "OTP_MALFORMED";
    await sensitive(stage, () => reset.locator("#code").fill("abc"));
    await submit(reset, "#code", "verify", stage, true);
    await expect(reset.locator("#otp-error")).toBeVisible();
    stage = "OTP_WRONG";
    const wrong = firstCode === "000000" ? "000001" : "000000";
    await sensitive(stage, () => reset.locator("#code").fill(wrong));
    await submit(reset, "#code", "verify", stage);
    await expect(reset.locator("#otp-error")).toBeVisible();
    await capture(reset, "rejected-otp");

    stage = "RESEND_COOLDOWN";
    expect(await reset.locator("#otp-resend").isDisabled()).toBe(true);
    await submit(reset, "#code", "resend", stage, true);
    await expect(reset.locator("#code")).toBeVisible();
    expect((await messages(page, identity.email)).length === 1).toBe(true);
    // Real elapsed server cooldown; no native clock or database fixture changes.
    await expect(reset.locator("#otp-resend")).toBeEnabled({ timeout: 35_000 });
    await submit(reset, "#code", "resend", "RESEND_ALLOWED");
    const nextCode = await deliveredCode(page, identity.email, seen);
    expect(nextCode !== firstCode).toBe(true);
    stage = "OLD_GENERATION";
    await sensitive(stage, () => reset.locator("#code").fill(firstCode));
    await submit(reset, "#code", "verify", stage);
    await expect(reset.locator("#otp-error")).toBeVisible();

    stage = "OTP_CORRECT";
    const verifyAction = await (
      await nativeForm(reset, "#code")
    ).getAttribute("action");
    await sensitive(stage, () => reset.locator("#code").fill(nextCode));
    await submit(reset, "#code", "verify", stage);
    await expect(reset.locator("#kc-passwd-update-form")).toBeVisible();
    await capture(reset, "native-password");
    stage = "PASSWORD_CONFIRMATION";
    await sensitive(stage, () =>
      reset.locator("#password-new").fill(newPassword),
    );
    await sensitive(stage, () =>
      reset.locator("#password-confirm").fill(`${newPassword}different`),
    );
    await nativeForm(reset, "#password-new");
    await sensitive(stage, () => reset.locator("#kc-submit").click());
    await expect(reset.locator("#input-error-password-confirm")).toBeVisible();
    stage = "PASSWORD_POLICY";
    await sensitive(stage, () => reset.locator("#password-new").fill("short"));
    await sensitive(stage, () =>
      reset.locator("#password-confirm").fill("short"),
    );
    await sensitive(stage, () => reset.locator("#kc-submit").click());
    // Native UpdatePassword uses a global ModelException error for policy failures.
    await expect(reset.locator("#kc-passwd-update-form")).toBeVisible();
    await expect(reset.getByRole("alert")).toBeVisible();
    expect(
      /minimum length.*12|at least.*12/i.test(
        await reset.getByRole("alert").innerText(),
      ),
    ).toBe(true);
    stage = "PASSWORD_UPDATE";
    await sensitive(stage, () =>
      reset.locator("#password-new").fill(newPassword),
    );
    await sensitive(stage, () =>
      reset.locator("#password-confirm").fill(newPassword),
    );
    const logout = reset.locator('input[name="logout-sessions"]');
    stage = "PASSWORD_SESSION_OPTION";
    if (await logout.count()) await logout.uncheck();
    stage = "PASSWORD_NATIVE_SUBMIT";
    await sensitive(stage, () => reset.locator("#kc-submit").click());
    stage = "PASSWORD_COMPLETION_INFO";
    stage = "PASSWORD_COMPLETION_INFO";
    await expect(reset.locator("#kc-info-message")).toBeVisible();
    expect(new URL(reset.url()).origin === keycloakOrigin).toBe(true);
    stage = "PASSWORD_COMPLETION_CTA";
    const completion = reset.locator("#kc-info-message a");
    expect((await completion.count()) === 1).toBe(true);
    const completionHref = await completion.getAttribute("href");
    const normalizedCompletion = completionHref
      ? new URL(completionHref, keycloakOrigin)
      : undefined;
    expect(
      Boolean(normalizedCompletion) &&
        normalizedCompletion!.origin === applicationOrigin &&
        normalizedCompletion!.pathname === "/api/auth/login" &&
        normalizedCompletion!.searchParams.get("prompt") === "login" &&
        Array.from(normalizedCompletion!.searchParams.keys()).length === 1,
    ).toBe(true);
    await capture(reset, "detached-completion");

    stage = "CONSUMED_REPLAY";
    // Replay the exact prior native verification endpoint without exporting the URL/body.
    const replay = await reset.request.post(verifyAction!, {
      form: { intent: "verify", code: nextCode },
      maxRedirects: 0,
    });
    const replayBody = await replay.text();
    expect(!replayBody.includes('id="kc-passwd-update-form"')).toBe(true);
    if (enrolled) {
      const credentials = await adminCredentials(page, username);
      expect(
        credentials.some(
          (credential) =>
            credential.id === enrolled!.id &&
            credential.type === enrolled!.type,
        ),
      ).toBe(true);
    }

    stage = "EXISTING_SSO_COOKIES";
    // The BFF owns the browser session; Keycloak's SSO state is server-side.
    const realmCookieUrl = `${keycloakOrigin}${realmPath}`;
    const sourceCookies = await ssoContext.cookies(realmCookieUrl);
    ssoCookieMetadata = (await ssoContext.cookies()).map(
      ({ name, domain, path: cookiePath, secure, httpOnly, sameSite }) => ({
        name,
        domain,
        path: cookiePath,
        secure,
        httpOnly,
        sameSite,
      }),
    );
    await recovery.addCookies(sourceCookies);
    expect(
      (await recovery.cookies(realmCookieUrl)).some(
        (cookie) => cookie.name === "knora_session",
      ),
    ).toBe(true);
    stage = "COMPLETION_CTA_CLICK";
    await sensitive(stage, () => completion.click());
    stage = "FRESH_NATIVE_AUTHORIZATION";
    await expect(reset.locator("#kc-form-login")).toBeVisible();
    const freshAuthorization = new URL(reset.url()).searchParams;
    expect(freshAuthorization.get("prompt") === "login").toBe(true);
    for (const parameter of ["state", "nonce", "code_challenge"])
      expect(
        Boolean(freshAuthorization.get(parameter)) &&
          freshAuthorization.get(parameter) !==
            initialAuthorization.get(parameter),
      ).toBe(true);
    stage = "OLD_PASSWORD";
    await sensitive(stage, () =>
      reset.locator("#username").fill(identity.email),
    );
    await sensitive(stage, () =>
      reset.locator("#password").fill(identity.password),
    );
    await sensitive(stage, () => reset.locator("#kc-login").click());
    await expect(reset.getByRole("alert")).toBeVisible();
    stage = "NEW_PASSWORD";
    await sensitive(stage, () => reset.locator("#password").fill(newPassword));
    await sensitive(stage, () => reset.locator("#kc-login").click());
    if (enrolled) {
      stage = "MFA_LOGIN";
      await expect(reset.locator("#otp")).toBeVisible();
      expect(new URL(reset.url()).origin === keycloakOrigin).toBe(true);
      await nativeForm(reset, "#otp");
      await sensitive(stage, () =>
        reset.locator("#otp").fill(totp(totpSecret)),
      );
      await sensitive(stage, () => reset.locator("#kc-login").click());
    }
    stage = "WORKSPACE";
    await reset.waitForURL(/\/workspaces\/[0-9a-f-]+$/, { timeout: 30_000 });
    expect(reset.url() === workspaceUrl).toBe(true);

    stage = "UNKNOWN_ACCOUNT";
    const unknownEmail = `figma-otp-unknown-${randomUUID()}@example.test`;
    const anonymous = await browser.newContext({
      baseURL: applicationOrigin,
      viewport: test.info().project.use.viewport,
    });
    ownedContexts.push(anonymous);
    guards.push(await guardedContext(anonymous));
    const unknown = await anonymous.newPage();
    await openFigmaLogin(unknown);
    await sensitive(stage, () =>
      unknown.getByRole("link", { name: "Forgot Password?" }).click(),
    );
    await sensitive(stage, () => unknown.locator("#email").fill(unknownEmail));
    await submit(unknown, "#email", "request", stage);
    await expect(unknown.locator("#code")).toBeVisible();
    expect(
      (await unknown.locator("#kc-page-title").innerText()) ===
        knownChallengeHeading,
    ).toBe(true);
    // Two bounded observations; existing service proof establishes the no-mail contract.
    expect((await messages(page, unknownEmail)).length === 0).toBe(true);
    await capture(unknown, "unknown-uniform");
    expect((await messages(page, unknownEmail)).length === 0).toBe(true);
    for (const assertGuard of guards) assertGuard();
    await writeFile(
      path.join(evidenceDirectory, `result-${test.info().project.name}.json`),
      JSON.stringify(
        {
          nativeJourney: true,
          malformedRejected: true,
          wrongRejected: true,
          cooldownServerEnforced: true,
          resendAllowed: true,
          previousGenerationRejected: true,
          consumedReplayRejected: true,
          policyRejected: true,
          confirmationRejected: true,
          detachedCompletion: true,
          existingSsoFreshLogin: true,
          transactionFreshness: true,
          oldPasswordRejected: true,
          newPasswordAccepted: true,
          exactOwnedWorkspace: true,
          unknownUniformNoDelivery: true,
          totpCredentialPreserved: Boolean(enrolled),
          freshLoginRequiresTotp: Boolean(enrolled),
          sensitiveDestinationRejected: false,
        },
        null,
        2,
      ),
    );
  } catch {
    await mkdir(evidenceDirectory, { recursive: true });
    const states = [];
    for (const context of ownedContexts)
      for (const nativePage of context.pages())
        states.push(
          await nativePage
            .evaluate(() => ({
              nativeOrigin: window.location.origin === "http://127.0.0.1:8380",
              passwordForm: Boolean(
                document.querySelector("#kc-passwd-update-form"),
              ),
              otpForm: Boolean(document.querySelector("#code")),
              loginForm: Boolean(document.querySelector("#kc-form-login")),
              mfaForm: Boolean(
                document.querySelector("#kc-totp-settings-form"),
              ),
              completionInfo: Boolean(
                document.querySelector("#kc-info-message"),
              ),
              completionAnchorCount:
                document.querySelectorAll("#kc-info-message a").length,
              completionHrefSafe: (() => {
                const href =
                  document.querySelector<HTMLAnchorElement>(
                    "#kc-info-message a",
                  )?.href;
                if (!href) return false;
                const url = new URL(href);
                return (
                  url.origin === "http://127.0.0.1:3300" &&
                  url.pathname === "/api/auth/login" &&
                  url.search === "?prompt=login"
                );
              })(),
              submitDisabled:
                (
                  document.querySelector(
                    "#kc-submit",
                  ) as HTMLButtonElement | null
                )?.disabled ?? false,
              logoutVisible: Boolean(
                (
                  document.querySelector(
                    'input[name="logout-sessions"]',
                  ) as HTMLElement | null
                )?.offsetParent,
              ),
            }))
            .catch(() => ({ unavailable: true })),
        );
    await writeFile(
      path.join(evidenceDirectory, `failure-${test.info().project.name}.json`),
      JSON.stringify({ stage, states, ssoCookieMetadata }, null, 2),
    );
    for (const context of ownedContexts) await sanitizeFailure(context);
    throw new Error(`NATIVE_STAGE_${stage}`);
  } finally {
    for (const context of ownedContexts.slice(1)) await context.close();
  }
});
