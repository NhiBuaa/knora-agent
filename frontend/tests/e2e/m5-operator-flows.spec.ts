import { expect, test } from "@playwright/test";

import { loginAs, newRoleContext } from "./support/auth";

test("an operator reads authorized operations and explicit unavailable evaluation observations", async ({ browser }) => {
  const context = await newRoleContext(browser, "operator");
  const page = await context.newPage();

  await loginAs(page, "operator");
  await page.goto("/operator/operations");
  await expect(page.getByRole("heading", { name: "Operations" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Operational observations" })).toBeVisible();
  await page.goto("/operator/evaluations");
  await expect(page.getByText("Evaluation unavailable", { exact: true })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("REPORT_ID_REQUIRED");
  await expect(page.locator("body")).not.toContainText("m5-operator-password");
  await context.close();
});

test("a non-operator receives the public operator denial", async ({ browser }) => {
  const context = await newRoleContext(browser, "no-operator");
  const page = await context.newPage();

  await loginAs(page, "no-operator");
  await page.goto("/operator/operations");
  await expect(page.getByText("You are not authorized to inspect operations.", { exact: true })).toBeVisible();
  await context.close();
});
