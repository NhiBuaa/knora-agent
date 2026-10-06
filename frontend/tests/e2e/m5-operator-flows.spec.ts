import { expect, test } from "@playwright/test";

import { loginAs, newRoleContext } from "./support/auth";

test("an operator reads authorized operations and explicit unavailable evaluation observations", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "operator");
  const page = await context.newPage();

  await loginAs(page, "operator");
  await page.goto("/operator/operations");
  await expect(page.getByRole("heading", { name: "Operations" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Operational observations" }),
  ).toBeVisible();
  await page.goto("/operator/evaluations");
  await expect(
    page.getByRole("button", { name: "Open report" }),
  ).toBeDisabled();
  await page
    .getByRole("textbox", { name: "Report ID", exact: true })
    .fill("m5-report-unavailable");
  await page.getByRole("button", { name: "Open report" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Evaluation report unavailable",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Report context" }),
  ).toContainText("EVALUATION_REPORT_UNAVAILABLE");
  await expect(page.locator("body")).not.toContainText("m5-operator-password");
  await context.close();
});

test("a non-operator receives the public operator denial", async ({
  browser,
}) => {
  const context = await newRoleContext(browser, "no-operator");
  const page = await context.newPage();

  await loginAs(page, "no-operator");
  await page.goto("/operator/operations");
  await expect(
    page.getByText("Operator access denied.", {
      exact: true,
    }),
  ).toBeVisible();
  await context.close();
});
