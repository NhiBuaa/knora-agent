import { expect, test } from "@playwright/test";

import { loginAs, newRoleContext } from "./support/auth";
import { m5E2EEnvironment } from "./support/environment";

test("a real user login exposes the expected safe session shape", async ({ browser }) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  await loginAs(page, "user");

  await context.close();
});

test("a user completes the real authorization-code login and can log out", async ({ browser }) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  await loginAs(page, "user");
  await expect(page.getByRole("heading", { name: "Workspace" })).toBeVisible();
  await expect(page.getByText("Selected workspace: m5-workspace")).toBeVisible();

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByText('{"ok":true}')).toBeVisible();
  await page.goto("/app");
  await expect(page.getByRole("alert")).toHaveText("No workspace is available for this session.");
  await context.close();
});

test("a visitor with a missing or expired session sees the explicit unavailable workspace state", async ({ browser }) => {
  const context = await newRoleContext(browser, "user");
  const page = await context.newPage();

  await page.goto("/app");
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("heading", { name: "Workspace" })).toBeVisible();
  await expect(page.getByText("No workspace is available for this session.", { exact: true })).toBeVisible();
  await context.close();
});

test("an operator can open the operator surface after real login", async ({ browser }) => {
  const context = await newRoleContext(browser, "operator");
  const page = await context.newPage();

  await loginAs(page, "operator");
  await page.goto("/operator");
  await expect(page.getByRole("heading", { name: "Operator observations" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Operator navigation" })).toBeVisible();
  await context.close();
});

test("another workspace cannot use the target workspace operator endpoint", async ({ browser }) => {
  const context = await newRoleContext(browser, "other-workspace");
  const page = await context.newPage();

  await loginAs(page, "other-workspace");
  await expect(page.getByText("Selected workspace: m5-other-workspace")).toBeVisible();
  const response = await page.request.get(
    `${m5E2EEnvironment().apiUrl}/v1/workspaces/m5-workspace/operator/operations`,
  );

  expect([401, 403]).toContain(response.status());
  await expect(page.getByText("m5-workspace")).not.toBeVisible();
  await context.close();
});

test("a signed-in non-operator is denied the operator surface", async ({ browser }) => {
  const context = await newRoleContext(browser, "no-operator");
  const page = await context.newPage();

  await loginAs(page, "no-operator");
  await page.goto("/operator");
  await expect(page.getByRole("alert")).toHaveText("You do not have operator access.");
  await context.close();
});
