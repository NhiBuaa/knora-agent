import { expect, test } from "@playwright/test";

import { loginAs, newRoleContext } from "./support/auth";

test("a real user login exposes the expected safe session shape", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  await loginAs(page, "user");

  await context.close();
});

test("logout ends Keycloak SSO before the same browser signs in as the operator", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  await loginAs(page, "user");
  await expect(page).toHaveURL(/\/workspaces\/[^/]+$/);

  const safeSession = await (
    await page.request.get("/api/auth/session")
  ).json();
  await page.evaluate(() => {
    sessionStorage.setItem(
      "knora:conversation-panels:v1:test-scope",
      "private-panel-preferences",
    );
    sessionStorage.setItem("unrelated-preference", "keep");
  });
  await page
    .getByRole("button", { name: `Account: ${safeSession.session.subject}` })
    .click();
  await expect(page.getByRole("menu").getByText("Signed in")).toBeVisible();
  await page.getByRole("menuitem", { name: "Log out" }).press("Enter");
  await expect(page).toHaveURL(/\/protocol\/openid-connect\/logout/);
  await page.locator("#kc-logout").click();
  await expect(page.getByRole("heading", { name: "Signed out" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
  expect(
    await page.evaluate(() =>
      sessionStorage.getItem("knora:conversation-panels:v1:test-scope"),
    ),
  ).toBeNull();
  expect(
    await page.evaluate(() => sessionStorage.getItem("unrelated-preference")),
  ).toBe("keep");
  await loginAs(page, "operator");
  await page.goto("/operator");
  await expect(
    page.getByRole("heading", { name: "Operator observations" }),
  ).toBeVisible();
  await context.close();
});

test("prompt=login shows native sign-in despite an existing Keycloak SSO session", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "user");
  try {
    const page = await context.newPage();
    await loginAs(page, "user");
    await page.goto(
      "/api/auth/login?prompt=login&returnTo=https://untrusted.example",
    );
    await expect(page.locator("#kc-form-login")).toBeVisible();
    expect(new URL(page.url()).searchParams.get("prompt")).toBe("login");
    expect(new URL(page.url()).searchParams.has("returnTo")).toBe(false);
  } finally {
    await context.close();
  }
});

test("a visitor with a missing session cannot open the retired product route", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  const response = await page.goto("/app");
  expect(response?.status()).toBe(404);
  await context.close();
});

test("an operator can open the operator surface after real login", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "operator");
  const page = await context.newPage();

  await loginAs(page, "operator");
  await page.goto("/operator");
  await expect(
    page.getByRole("heading", { name: "Operator observations" }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Operator navigation" }),
  ).toBeVisible();
  await context.close();
});

test("another workspace cannot use the target workspace operator endpoint", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "other-workspace");
  const page = await context.newPage();

  await loginAs(page, "other-workspace");
  const response = await page.request.get(
    "/api/v1/workspaces/m5-workspace/operator/operations",
  );

  expect(response.status()).toBe(403);
  await expect(page.getByText("m5-workspace")).not.toBeVisible();
  await context.close();
});

test("a signed-in non-operator is denied the operator surface", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "no-operator");
  const page = await context.newPage();

  await loginAs(page, "no-operator");
  await page.goto("/operator/operations");
  await expect(
    page.getByText("You are not authorized to inspect operations.", {
      exact: true,
    }),
  ).toBeVisible();
  await context.close();
});
