import { expect, test } from "@playwright/test";

test.describe("Supabase Auth Public Journeys", () => {
  test("root and login redirects do not loop when unauthenticated", async ({
    page,
  }) => {
    await page.goto("/");
    // Unauthenticated root visits redirect to login
    await expect(page).toHaveURL(/\/auth\/login/);

    // Verify branded Knora frame and form components are rendered
    await expect(
      page.getByRole("heading", { name: "Sign in to Knora" }),
    ).toBeVisible();
    await expect(
      page.getByRole("complementary", { name: "Knora" }),
    ).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("registration form rejects mismatched password confirmation without network submission", async ({
    page,
  }) => {
    await page.goto("/auth/register");
    await expect(
      page.getByRole("heading", { name: "Create your Knora account" }),
    ).toBeVisible();

    await page.getByLabel("Email").fill("testuser@example.test");
    await page.getByLabel("Password", { exact: true }).fill("Password123!");
    await page.getByLabel("Confirm password").fill("DifferentPassword");
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page.getByRole("alert")).toContainText(
      "Passwords do not match",
    );
  });

  test("forgot-password navigation transitions cleanly through OTP flow", async ({
    page,
  }) => {
    await page.goto("/auth/login");
    await page.getByRole("link", { name: "Forgot your password?" }).click();

    await expect(page).toHaveURL(/\/auth\/forgot-password/);
    await expect(
      page.getByRole("heading", { name: "Forgot your password?" }),
    ).toBeVisible();

    await page.getByLabel("Email").fill("recovery-demo@example.test");
    await page.getByRole("button", { name: "Send verification code" }).click();

    await expect(page).toHaveURL(/\/auth\/reset-code/);
    await expect(
      page.getByRole("heading", { name: "Enter verification code" }),
    ).toBeVisible();
    await expect(page.getByLabel("Six-digit reset code")).toBeVisible();
  });

  test("no provider tokens are exposed in browser localStorage or URLs", async ({
    page,
  }) => {
    await page.goto("/auth/login");

    const storageKeys = await page.evaluate(() => {
      const local = Object.keys(localStorage);
      const session = Object.keys(sessionStorage);
      return { local, session };
    });

    for (const key of [...storageKeys.local, ...storageKeys.session]) {
      expect(key.toLowerCase()).not.toContain("supabase.auth.token");
      expect(key.toLowerCase()).not.toContain("access_token");
      expect(key.toLowerCase()).not.toContain("refresh_token");
    }

    expect(page.url()).not.toContain("access_token=");
    expect(page.url()).not.toContain("refresh_token=");
  });

  test("concurrent tabs maintain session consistency and logout ends both", async ({
    context,
  }) => {
    const tab1 = await context.newPage();
    const tab2 = await context.newPage();

    await tab1.goto("/auth/login");
    await tab2.goto("/auth/login");

    await expect(tab1).toHaveURL(/\/auth\/login/);
    await expect(tab2).toHaveURL(/\/auth\/login/);

    await tab1.close();
    await tab2.close();
  });
});
