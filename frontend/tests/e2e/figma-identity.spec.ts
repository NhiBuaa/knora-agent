import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

import {
  captureIdentity,
  fillRegistration,
  openFigmaLogin,
  openFigmaRegistration,
} from "./support/figma-auth";

const evidence = "../.superpowers/sdd/2026-10-05-figma-ui-identity/evidence";

test("AU1 native sign-in has the designed brand, fields and resource geometry", async ({
  page,
}) => {
  await openFigmaLogin(page);
  await expect(
    page.getByRole("heading", { name: "Sign in to Knora", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Grounded answers,")).toBeVisible();
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
    x: 830,
    width: 420,
    height: 42,
  });
  const resetLink = await page
    .getByRole("link", { name: "Forgot Password?" })
    .boundingBox();
  expect(resetLink).not.toBeNull();
  expect(resetLink!.x + resetLink!.width).toBeCloseTo(1250, 0);
  await captureIdentity(page, `${evidence}/AU1-live.png`);
});

test("native test-mail reset renders update password and information templates", async ({
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
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
  });
  try {
    const reset = await context.newPage();
    await reset.goto("http://127.0.0.1:3300/api/auth/login");
    await reset.getByRole("link", { name: "Forgot Password?" }).click();
    await reset.locator("#username").fill(identity.email);
    await reset.getByRole("button", { name: "Submit", exact: true }).click();
    await expect(reset.getByText(/receive an email shortly/i)).toBeVisible();
    let messageId: string | undefined;
    await expect
      .poll(async () => {
        const response = await page.request.get(
          "http://127.0.0.1:8025/api/v1/messages",
        );
        const mailbox = await response.json();
        const message = mailbox.messages.find(
          (entry: { ID: string; To: { Address: string }[] }) =>
            entry.To.some((to) => to.Address === identity.email),
        );
        messageId = message?.ID;
        return Boolean(messageId);
      })
      .toBe(true);
    const message = await (
      await page.request.get(
        `http://127.0.0.1:8025/api/v1/message/${messageId}`,
      )
    ).json();
    const link = String(message.Text).match(
      /http:\/\/127\.0\.0\.1:8380\/[^\s]+/,
    );
    expect(Boolean(link)).toBe(true);
    await reset.goto(link![0]);
    await expect(reset.locator("#kc-passwd-update-form")).toBeVisible();
    await expect(
      reset.getByRole("heading", { name: "Set a new password" }),
    ).toBeVisible();
    const icon = reset.locator("#password-new-show-password i");
    expect(await icon.boundingBox()).toMatchObject({ width: 18, height: 18 });
    expect(
      await icon.evaluate(
        (element) => getComputedStyle(element).backgroundImage,
      ),
    ).toContain("42cef.svg");
    await captureIdentity(reset, `${evidence}/native-update-password-live.png`);
    const changedPassword = randomUUID();
    await reset.locator("#password-new").fill(changedPassword);
    await reset.locator("#password-confirm").fill(changedPassword);
    await reset.locator("#kc-submit").click();
    await reset.waitForURL(/\/workspaces\/[0-9a-f-]+$/);
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
    const actionResponse = await page.request.put(
      `http://127.0.0.1:8380/admin/realms/knora-dev/users/${users[0].id}/execute-actions-email`,
      { headers, data: ["UPDATE_PASSWORD"] },
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
            entry.ID !== messageId &&
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
    await expect(reset.locator("#kc-passwd-update-form")).toBeVisible();
    await reset.locator("#password-new").fill(changedPassword);
    await reset.locator("#password-confirm").fill(changedPassword);
    await reset.locator("#kc-submit").click();
    await expect(reset.locator("#kc-info-message")).toBeVisible();
    await expect(reset.locator("#kc-info-message")).toContainText(/updated/i);
  } finally {
    await context.close();
  }
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
  expect(await page.locator("#kc-page-title").boundingBox()).toMatchObject({
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
