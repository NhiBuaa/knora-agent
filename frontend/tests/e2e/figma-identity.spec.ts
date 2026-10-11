import { randomUUID } from "node:crypto";
import { writeFile } from "node:fs/promises";
import {
  expect,
  test,
  type BrowserContext,
  type Request,
} from "@playwright/test";

import {
  captureIdentity,
  fillRegistration,
  openFigmaLogin,
  openFigmaRegistration,
} from "./support/figma-auth";

const evidence =
  "../.superpowers/sdd/2026-10-09-figma-reset-success-native-login/evidence/password-event-identity";

test("AU1 native sign-in has the designed brand, fields and resource geometry", async ({
  page,
}) => {
  await openFigmaLogin(page);
  await expect(
    page.getByRole("heading", { name: "Sign in to Knora", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Grounded answers,")).toBeVisible();
  expect(await page.locator("#kc-page-title").boundingBox()).toMatchObject({
    y: 175,
  });
  expect(await page.locator("#kc-form-login").boundingBox()).toMatchObject({
    y: 269,
  });
  await expect(page.locator("#username")).toHaveAttribute(
    "autocomplete",
    /username/,
  );
  await expect(page.locator("#password")).toHaveAttribute(
    "autocomplete",
    "current-password",
  );
  await expect(page.locator('input[name="credentialId"]')).toHaveCount(1);
  const leaf = page.locator(".knora-brand img");
  await expect(leaf).toBeVisible();
  expect(await leaf.boundingBox()).toMatchObject({ width: 18, height: 18 });
  const eye = page.locator("#password-show-password i");
  expect(await eye.boundingBox()).toMatchObject({ width: 18, height: 18 });
  expect(
    await eye.evaluate((element) => getComputedStyle(element).backgroundImage),
  ).toContain("bf7a4.svg");
  expect(
    await page.locator(".pf-v5-c-form-control:has(#username)").boundingBox(),
  ).toMatchObject({
    width: 420,
    height: 40,
  });
  expect(await page.locator("#kc-login").boundingBox()).toMatchObject({
    x: 829,
    y: 475,
    width: 420,
    height: 42,
  });
  const resetLink = await page
    .getByRole("link", { name: "Forgot Password?" })
    .boundingBox();
  expect(resetLink).not.toBeNull();
  expect(resetLink!.x + resetLink!.width).toBeCloseTo(1249, 0);
  for (const [id, y] of [
    ["username", 290],
    ["password", 374],
  ] as const) {
    expect(
      await page.locator(`.pf-v5-c-form-control:has(#${id})`).boundingBox(),
    ).toMatchObject({ y });
  }
  await captureIdentity(page, `${evidence}/AU1-live.png`);
});

for (const completionAction of [
  "Create account",
  "Forgot Password?",
  "generic-profile",
  "provider-sso",
] as const) {
  test(`native test-mail reset renders update password and information templates then ${completionAction}`, async ({
    page,
    browser,
  }) => {
    const ownedContexts: BrowserContext[] = [page.context()];
    try {
      await openFigmaRegistration(page);
      const username = `figma-${randomUUID()}`;
      const identity = {
        username,
        email: `${username}@example.test`,
        password: randomUUID(),
      };
      await fillRegistration(page, identity);
      await page
        .getByRole("button", { name: "Create account", exact: true })
        .click();
      await page.waitForURL(/\/workspaces\/[0-9a-f-]+$/);
      const providerCookies = (await page.context().cookies()).filter(
        (cookie) => /^KEYCLOAK_(IDENTITY|SESSION)(_LEGACY)?$/.test(cookie.name),
      );
      if (completionAction === "provider-sso") {
        expect(
          providerCookies.some((cookie) => cookie.name === "KEYCLOAK_IDENTITY"),
        ).toBe(true);
        // Prove the provider cookie authenticates before testing forced fresh login.
        const probe = await browser.newContext();
        ownedContexts.push(probe);
        try {
          await probe.addCookies(providerCookies);
          const probePage = await probe.newPage();
          await probePage.goto("http://127.0.0.1:3300/api/auth/login");
          await probePage.waitForURL(/\/workspaces\/[0-9a-f-]+$/);
          const original = await (
            await page.request.get("/api/auth/session")
          ).json();
          const reused = await (
            await probePage.request.get(
              "http://127.0.0.1:3300/api/auth/session",
            )
          ).json();
          expect(Boolean(original.session?.subject)).toBe(true);
          expect(reused.session.subject).toBe(original.session.subject);
        } finally {
          await probe.close();
        }
      }
      const context = await browser.newContext({
        viewport: { width: 1440, height: 960 },
      });
      ownedContexts.push(context);
      const requestBoundaries: {
        origin: string;
        path: string;
        promptLogin: boolean;
      }[] = [];
      if (completionAction === "provider-sso")
        context.on("request", (request) => {
          const target = new URL(request.url());
          if (
            ["http://127.0.0.1:3300", "http://127.0.0.1:8380"].includes(
              target.origin,
            )
          )
            requestBoundaries.push({
              origin: target.origin,
              path: target.pathname,
              promptLogin: target.searchParams.get("prompt") === "login",
            });
        });
      try {
        const reset = await context.newPage();
        await reset.goto("http://127.0.0.1:3300/api/auth/login");
        const initialAuthorization = new URL(reset.url()).searchParams;
        const changedPassword = randomUUID();
        const tokenResponse = await page.request.post(
          "http://127.0.0.1:8380/realms/master/protocol/openid-connect/token",
          {
            form: {
              grant_type: "password",
              client_id: "admin-cli",
              username: "figma-test-admin",
              password: "figma-test-admin-password",
            },
          },
        );
        expect(tokenResponse.ok()).toBe(true);
        const token = (await tokenResponse.json()).access_token;
        const headers = { Authorization: `Bearer ${token}` };
        const usersResponse = await page.request.get(
          `http://127.0.0.1:8380/admin/realms/knora-dev/users?username=${username}&exact=true`,
          { headers },
        );
        expect(usersResponse.ok()).toBe(true);
        const users = await usersResponse.json();
        expect(users).toHaveLength(1);
        const mailboxBeforeAction = await (
          await page.request.get("http://127.0.0.1:8025/api/v1/messages")
        ).json();
        const priorMessageIds = new Set(
          mailboxBeforeAction.messages.map((entry: { ID: string }) => entry.ID),
        );
        const actionResponse = await page.request.put(
          `http://127.0.0.1:8380/admin/realms/knora-dev/users/${users[0].id}/execute-actions-email?client_id=knora-web&redirect_uri=http%3A%2F%2F127.0.0.1%3A3300%2Fapi%2Fauth%2Fcallback`,
          {
            headers,
            data: [
              completionAction === "generic-profile"
                ? "UPDATE_PROFILE"
                : "UPDATE_PASSWORD",
            ],
          },
        );
        expect(actionResponse.ok()).toBe(true);
        let actionMessageId: string | undefined;
        await expect
          .poll(async () => {
            const response = await page.request.get(
              "http://127.0.0.1:8025/api/v1/messages",
            );
            const mailbox = await response.json();
            actionMessageId = mailbox.messages.find(
              (entry: { ID: string; To: { Address: string }[] }) =>
                !priorMessageIds.has(entry.ID) &&
                entry.To.some((to) => to.Address === identity.email),
            )?.ID;
            return Boolean(actionMessageId);
          })
          .toBe(true);
        const actionMail = await (
          await page.request.get(
            `http://127.0.0.1:8025/api/v1/message/${actionMessageId}`,
          )
        ).json();
        const actionLink = String(actionMail.Text).match(
          /http:\/\/127\.0\.0\.1:8380\/[^\s]+/,
        );
        expect(Boolean(actionLink)).toBe(true);
        await reset.goto(actionLink![0]);
        await expect(reset.locator("#kc-info-message")).toBeVisible();
        await captureIdentity(reset, `${evidence}/native-info-live.png`);
        await reset.locator("#kc-info-message a").click();
        if (completionAction === "generic-profile") {
          await expect(reset.locator("#kc-update-profile-form")).toBeVisible();
          await reset
            .locator('#kc-update-profile-form [type="submit"]')
            .click();
          await expect(reset.locator("#kc-info-message")).toBeVisible();
          await expect(
            reset.locator("[data-knora-reset-success-link]"),
          ).toHaveCount(0);
          await expect(
            reset.locator("#knora-password-updated-notice"),
          ).toHaveCount(0);
          await captureIdentity(
            reset,
            `${evidence}/generic-profile-completed.png`,
          );
          await reset.locator("#kc-info-message a").click();
          await expect(reset.locator("#kc-form-login")).toBeVisible();
          await expect(
            reset.locator("#knora-password-updated-notice"),
          ).toBeHidden();
          await captureIdentity(
            reset,
            `${evidence}/generic-profile-sign-in.png`,
          );
          return;
        }
        await expect(reset.locator("#kc-passwd-update-form")).toBeVisible();
        await expect(
          reset.getByRole("heading", { name: "Choose a new password" }),
        ).toBeVisible();
        const icon = reset.locator("#password-new-show-password i");
        expect(await icon.boundingBox()).toMatchObject({
          width: 18,
          height: 18,
        });
        expect(
          await icon.evaluate(
            (element) => getComputedStyle(element).backgroundImage,
          ),
        ).toContain("42cef.svg");
        await captureIdentity(
          reset,
          `${evidence}/native-update-password-live.png`,
        );
        await reset.locator("#password-new").fill(changedPassword);
        await reset.locator("#password-confirm").fill(changedPassword);
        let providerCookieSentWithFreshLogin = false;
        let freshLoginRequestObserved = false;
        let freshProviderRequest: Promise<Request> | undefined;
        if (completionAction === "provider-sso") {
          const logout = reset.locator('input[name="logout-sessions"]');
          if (await logout.count()) await logout.uncheck();
          await context.addCookies(providerCookies);
          // Request events include redirect destinations; route interception only
          // handles the first request in a redirect chain.
          freshProviderRequest = context.waitForEvent("request", {
            predicate: (request) => {
              const target = new URL(request.url());
              return (
                target.origin === "http://127.0.0.1:8380" &&
                target.pathname ===
                  "/realms/knora-dev/protocol/openid-connect/auth" &&
                target.searchParams.get("prompt") === "login"
              );
            },
          });
        }
        await reset.locator("#kc-submit").click();
        await expect(reset.locator("#kc-form-login")).toBeVisible();
        await expect(
          reset.locator("#knora-password-updated-notice"),
        ).toBeVisible();
        await expect(
          reset.locator("#knora-password-updated-notice"),
        ).toContainText(/Password updated/i);
        expect(
          await reset.locator("#knora-password-updated-notice").boundingBox(),
        ).toMatchObject({ x: 829, width: 420, height: 59 });
        const freshAuthorization = new URL(reset.url()).searchParams;
        expect(freshAuthorization.get("prompt")).toBe("login");
        for (const parameter of ["state", "nonce", "code_challenge"]) {
          expect(Boolean(freshAuthorization.get(parameter))).toBe(true);
          expect(
            freshAuthorization.get(parameter) !==
              initialAuthorization.get(parameter),
          ).toBe(true);
        }
        if (completionAction === "provider-sso") {
          const request = await freshProviderRequest!;
          freshLoginRequestObserved = true;
          const cookieHeader = (await request.allHeaders()).cookie ?? "";
          providerCookieSentWithFreshLogin =
            /(?:^|;\s*)KEYCLOAK_IDENTITY=/u.test(cookieHeader);
          await writeFile(
            `${evidence}/provider-sso-boundary-diagnostic.json`,
            JSON.stringify({
              freshLoginRequestObserved,
              providerCookieSentWithFreshLogin,
              sourceProviderCookieNames: providerCookies.map(
                (cookie) => cookie.name,
              ),
              remainingProviderCookieNames: (await context.cookies())
                .filter((cookie) => cookie.name.startsWith("KEYCLOAK_"))
                .map((cookie) => cookie.name),
            }),
          );
          expect(providerCookieSentWithFreshLogin).toBe(true);
          // Keycloak may retain the recognized username in native SSO context,
          // but prompt=login must still require a password instead of signing in.
          await expect(reset.locator("#password")).toBeVisible();
          await expect(reset.locator("#password")).toHaveValue("");
          const pendingSession = await context.request.get(
            "http://127.0.0.1:3300/api/auth/session",
          );
          expect(pendingSession.ok()).toBe(true);
          expect((await pendingSession.json()).session).toBeNull();
          await captureIdentity(
            reset,
            `${evidence}/provider-sso-password-success.png`,
          );
          await writeFile(
            `${evidence}/provider-sso-password-success.json`,
            JSON.stringify(
              {
                providerCookieAuthenticationProved: true,
                providerCookieSentWithFreshLogin: true,
                promptLogin: true,
                passwordFormVisible: true,
                transactionFreshness: true,
                passwordUpdatedNoticeVisible: true,
                scope:
                  "native UPDATE_PASSWORD email action; not OTP challenge coverage",
              },
              null,
              2,
            ),
          );
          return;
        }
        await reset
          .getByRole("link", { name: completionAction, exact: true })
          .click();
        await expect(
          reset.locator(
            completionAction === "Create account"
              ? "#kc-register-form"
              : "#email",
          ),
        ).toBeVisible();
        await captureIdentity(
          reset,
          `${evidence}/reset-success-${completionAction === "Create account" ? "create-account" : "forgot-password"}.png`,
        );
      } finally {
        if (completionAction === "provider-sso")
          await writeFile(
            `${evidence}/provider-sso-request-boundaries.json`,
            JSON.stringify(requestBoundaries, null, 2),
          );
        await context.close();
      }
    } catch {
      for (const owned of ownedContexts)
        for (const current of owned.pages())
          await current.goto("about:blank").catch(() => {});
      throw new Error(
        "Native completion journey failed; sensitive context removed.",
      );
    }
  });
}

test("AU3 and AU4 public outcomes have safe retry links and the original brand asset", async ({
  page,
}) => {
  for (const [path, title, action, capture] of [
    [
      "/auth/unavailable",
      "Sign-in is temporarily unavailable",
      "Try again",
      "AU3",
    ],
    [
      "/api/auth/callback?error=untrusted&error_description=untrusted-detail",
      "Couldn’t sign you in",
      "Try signing in again",
      "AU4",
    ],
  ] as const) {
    await page.goto(path);
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: action })).toHaveAttribute(
      "href",
      "/api/auth/login",
    );
    await expect(page.getByText("untrusted-detail")).not.toBeVisible();
    const leaf = page
      .getByRole("complementary", { name: "Knora" })
      .locator("img");
    await expect(leaf).toHaveAttribute("src", "/brand/knora-leaf.svg");
    expect(await leaf.boundingBox()).toMatchObject({ width: 18, height: 18 });
    expect(
      await page.locator(".kn-auth-outcome__content").boundingBox(),
    ).toMatchObject({ x: 820, width: 440 });
    await captureIdentity(page, `${evidence}/${capture}-live.png`);
  }
  await expect(page).toHaveURL("http://127.0.0.1:3300/auth/failed");
});

test("AU2 invalid credentials are a native Keycloak response", async ({
  page,
}) => {
  await openFigmaLogin(page);
  await page.locator("#username").fill("figma-invalid-test-user");
  await page.locator("#password").fill(randomUUID());
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("Invalid");
  await expect(page).toHaveURL(/\/realms\/knora-dev\//);
  await captureIdentity(page, `${evidence}/AU2-live.png`);
});

test("AU2 corrected credentials reach the same owned Workspace", async ({
  page,
  browser,
}) => {
  const username = `figma-corrected-${randomUUID()}`;
  const identity = {
    username,
    email: `${username}@example.test`,
    password: `Correct-${randomUUID()}-Password`,
  };
  const retryContext = await browser.newContext();
  const retryPage = await retryContext.newPage();
  try {
    await openFigmaRegistration(page);
    await fillRegistration(page, identity);
    await page
      .getByRole("button", { name: "Create account", exact: true })
      .click();
    await page.waitForURL(/\/workspaces\/[0-9a-f-]+$/);
    const ownedWorkspaceUrl = page.url();
    const ownedWorkspaceId = new URL(ownedWorkspaceUrl).pathname
      .split("/")
      .at(-1);

    await retryPage.goto("http://127.0.0.1:3300/api/auth/login");
    await expect(retryPage.locator("#kc-form-login")).toBeVisible();
    await retryPage.locator("#username").fill(identity.email);
    await retryPage.locator("#password").fill(`Wrong-${randomUUID()}`);
    await retryPage
      .getByRole("button", { name: "Sign in", exact: true })
      .click();
    await expect(retryPage.getByRole("alert")).toContainText("Invalid");
    await expect(retryPage.locator("#username")).toHaveValue(identity.email);
    const rejectedSession = await retryPage.request.get(
      "http://127.0.0.1:3300/api/auth/session",
    );
    expect(rejectedSession.status()).toBe(200);
    expect(await rejectedSession.json()).toMatchObject({ session: null });
    await captureIdentity(retryPage, `${evidence}/edge-84-invalid.png`);

    await retryPage.locator("#password").fill(identity.password);
    await retryPage
      .getByRole("button", { name: "Sign in", exact: true })
      .click();
    await expect(retryPage).toHaveURL(ownedWorkspaceUrl);
    expect(new URL(retryPage.url()).pathname).toBe(
      `/workspaces/${ownedWorkspaceId}`,
    );
    await captureIdentity(retryPage, `${evidence}/edge-84-corrected.png`);
  } catch {
    // Native actions contain authentication state; remove sensitive DOM before reporting.
    for (const current of [page, retryPage]) {
      await current.goto("about:blank").catch(() => {});
    }
    throw new Error(
      "Corrected native credentials journey failed; sensitive DOM removed.",
    );
  } finally {
    await retryContext.close();
  }
});

test("AU2 invalid credentials can enter the native recovery request", async ({
  page,
}) => {
  await openFigmaLogin(page);
  await page.locator("#username").fill("figma-invalid-recovery-user");
  await page.locator("#password").fill(randomUUID());
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Invalid");
  await page
    .getByRole("link", { name: "Forgot Password?", exact: true })
    .click();
  await expect(page.locator("#email")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Forgot your password?", exact: true }),
  ).toBeVisible();
  await captureIdentity(page, `${evidence}/AU2-recovery-request-live.png`);
});

test("AU4 failed authentication starts a fresh native sign-in", async ({
  page,
}) => {
  await page.goto("/auth/failed");
  await expect(
    page.getByRole("heading", { name: "Couldn’t sign you in", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Try signing in again", exact: true })
    .click();
  await expect(page).toHaveURL(/\/realms\/knora-dev\//);
  await expect(page.locator("#kc-form-login")).toBeVisible();
  await captureIdentity(page, `${evidence}/AU4-retry-sign-in-live.png`);
});

test("AU8 registration exposes exactly four approved native fields", async ({
  page,
}) => {
  await openFigmaRegistration(page);
  await expect(
    page.getByRole("heading", {
      name: "Create your Knora account",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.locator('input:not([type="hidden"]):not([type="submit"])'),
  ).toHaveCount(4);
  await expect(
    page.locator('input[name="firstName"], input[name="lastName"]'),
  ).toHaveCount(0);
  for (const [id, y] of [
    ["username", 308],
    ["email", 392],
    ["password", 476],
    ["password-confirm", 560],
  ] as const) {
    expect(
      await page.locator(`.pf-v5-c-form-control:has(#${id})`).boundingBox(),
    ).toMatchObject({ y });
  }
  expect(await page.locator("#kc-submit").boundingBox()).toMatchObject({
    y: 623,
  });
  expect(await page.locator("#kc-register-form").boundingBox()).toMatchObject({
    y: 287,
  });
  expect(await page.locator("#kc-page-title").boundingBox()).toMatchObject({
    y: 175,
    width: 420,
    height: 40,
  });
  expect(
    await page.evaluate(() => document.fonts.check('600 30px "Roboto Slab"')),
  ).toBe(true);
  await captureIdentity(page, `${evidence}/AU8-live.png`);
});

test("AU9 empty registration shows native validation", async ({ page }) => {
  await openFigmaRegistration(page);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page).toHaveURL(/\/realms\/knora-dev\//);
  await expect(page.locator('[aria-invalid="true"]').first()).toBeVisible();
  const status = await page
    .locator(".pf-v5-c-input-group .pf-v5-c-form-control__icon.pf-m-status i")
    .boundingBox();
  const eye = await page.locator("#password-show-password i").boundingBox();
  expect(status).not.toBeNull();
  expect(eye).not.toBeNull();
  expect(status!.x + status!.width).toBeLessThanOrEqual(eye!.x);
  await expect(
    page.getByText("Check the details below and try again."),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Sign in", exact: true })
    .scrollIntoViewIfNeeded();
  await expect(
    page.getByRole("link", { name: "Sign in", exact: true }),
  ).toBeInViewport();
  await captureIdentity(page, `${evidence}/AU9-live.png`);
});

test("registration confirmation and policy errors remain native", async ({
  page,
}) => {
  try {
    await openFigmaRegistration(page);
    const username = `figma-${randomUUID()}`;
    const identity = {
      username,
      email: `${username}@example.test`,
      password: randomUUID(),
    };
    await fillRegistration(page, identity, randomUUID());
    // Submit bypasses only native client policy hints, so the response proves server enforcement.
    await page
      .locator("#kc-register-form")
      .evaluate((form: HTMLFormElement) => form.submit());
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page.locator("#input-error-password-confirm")).toBeVisible();
    await fillRegistration(page, { ...identity, password: "short" });
    await page
      .locator("#kc-register-form")
      .evaluate((form: HTMLFormElement) => form.submit());
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page.locator("#input-error-password")).toContainText(
      /12|length/i,
    );
    // Recover the same server-rejected form, rather than proving success in a
    // separate registration transaction.
    await fillRegistration(page, identity);
    await page
      .getByRole("button", { name: "Create account", exact: true })
      .click();
    await page.waitForURL(/\/workspaces\/[0-9a-f-]+$/);
    const resolution = await page.request.post("/api/v1/workspaces/resolve", {
      data: { hint_id: null },
    });
    expect(resolution.ok()).toBe(true);
    const resolved = await resolution.json();
    expect(resolved.state).toBe("ACTIVE");
    expect(resolved.workspace.name).toBe("My Workspace");
    expect(new URL(page.url()).pathname).toBe(
      `/workspaces/${resolved.workspace.id}`,
    );
    await captureIdentity(
      page,
      `${evidence}/edge-70-corrected-registration.png`,
    );
  } catch {
    await page.goto("about:blank").catch(() => {});
    throw new Error(
      "Native registration recovery failed; sensitive context removed.",
    );
  }
});

test("native registration lands in ACTIVE and archived owner returns to NO_ACTIVE_WORKSPACE", async ({
  page,
  browser,
}) => {
  await openFigmaRegistration(page);
  const username = `figma-${randomUUID()}`;
  const identity = {
    username,
    email: `${username}@example.test`,
    password: randomUUID(),
  };
  await fillRegistration(page, identity);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page.waitForURL(/\/workspaces\/[0-9a-f-]+$/);
  const safeSession = await (
    await page.request.get("/api/auth/session")
  ).json();
  await page
    .getByRole("button", { name: `Account: ${safeSession.session.subject}` })
    .click();
  const account = page.getByRole("menu");
  await expect(account.getByText("Signed in")).toBeVisible();
  await expect(
    account.getByText(safeSession.session.subject, { exact: true }),
  ).toBeVisible();
  await expect(
    account.getByRole("menuitem", { name: "Appearance" }),
  ).toBeVisible();
  expect(await account.boundingBox()).toMatchObject({ width: 230 });
  await captureIdentity(page, `${evidence}/AU5-live.png`);
  await page.keyboard.press("Escape");
  const resolution = await page.request.post("/api/v1/workspaces/resolve", {
    data: { hint_id: null },
  });
  expect(resolution.ok()).toBe(true);
  const active = await resolution.json();
  expect(active.state).toBe("ACTIVE");
  expect(active.workspace.name).toBe("My Workspace");
  const archive = await page.request.post(
    `/api/v1/workspaces/${active.workspace.id}/archive`,
    { headers: { "If-Match": String(active.workspace.revision) } },
  );
  expect(archive.ok()).toBe(true);
  const empty = await page.request.post("/api/v1/workspaces/resolve", {
    data: { hint_id: null },
  });
  expect(empty.ok()).toBe(true);
  expect((await empty.json()).state).toBe("NO_ACTIVE_WORKSPACE");
  const context = await browser.newContext();
  try {
    const emailLogin = await context.newPage();
    await emailLogin.goto("http://127.0.0.1:3300/api/auth/login");
    await expect(emailLogin.locator("#kc-form-login")).toBeVisible();
    await emailLogin.locator("#username").fill(identity.email);
    await emailLogin.locator("#password").fill(identity.password);
    await emailLogin
      .getByRole("button", { name: "Sign in", exact: true })
      .click();
    await emailLogin.waitForURL(/\/workspaces$/);
  } finally {
    await context.close();
  }
});
