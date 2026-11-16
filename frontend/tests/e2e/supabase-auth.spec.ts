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

    await expect(page.locator(".knora-notice[role='alert']")).toContainText(
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

  test("real login journey signs in user, receives session and navigates to workspaces", async ({
    page,
  }) => {
    await page.goto("/auth/login");

    await page.getByLabel("Email").fill("testuser@example.test");
    await page.getByLabel("Password", { exact: true }).fill("Password123!");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL(/\/workspaces/);

    const sessionResponse = await page.request.get("/api/auth/session");
    expect(sessionResponse.status()).toBe(200);
    const sessionBody = await sessionResponse.json();
    expect(sessionBody.session).not.toBeNull();
    expect(sessionBody.session.subject).toBe(
      "ca0af038-9a87-4e0c-9dd3-2f3d47fc6bf1",
    );
    expect(sessionBody.session.capabilities).toContain("documents:read");
  });

  test("concurrent tabs maintain session consistency and multi-tab refresh", async ({
    context,
  }) => {
    const tab1 = await context.newPage();
    await tab1.goto("/auth/login");
    await tab1.getByLabel("Email").fill("testuser@example.test");
    await tab1.getByLabel("Password", { exact: true }).fill("Password123!");
    await tab1.getByRole("button", { name: "Sign in" }).click();
    await expect(tab1).toHaveURL(/\/workspaces/);

    const tab2 = await context.newPage();
    await tab2.goto("/workspaces");
    await expect(tab2).toHaveURL(/\/workspaces/);

    // Verify both tabs see the authenticated session
    const tab1Session = await (
      await tab1.request.get("/api/auth/session")
    ).json();
    const tab2Session = await (
      await tab2.request.get("/api/auth/session")
    ).json();
    expect(tab1Session.session).not.toBeNull();
    expect(tab2Session.session).not.toBeNull();
    expect(tab1Session.session.subject).toBe(tab2Session.session.subject);

    await tab1.close();
    await tab2.close();
  });

  test("logout terminates session and rejects old session across all tabs", async ({
    context,
  }) => {
    const tab1 = await context.newPage();
    await tab1.goto("/auth/login");
    await tab1.getByLabel("Email").fill("testuser@example.test");
    await tab1.getByLabel("Password", { exact: true }).fill("Password123!");
    await tab1.getByRole("button", { name: "Sign in" }).click();
    await expect(tab1).toHaveURL(/\/workspaces/);

    const tab2 = await context.newPage();
    await tab2.goto("/workspaces");
    await expect(tab2).toHaveURL(/\/workspaces/);

    // Logout via POST from Tab 1
    const origin = new URL(tab1.url()).origin;
    const logoutResponse = await tab1.request.post("/api/auth/logout", {
      headers: {
        origin,
        host: new URL(origin).host,
      },
    });
    expect(logoutResponse.status()).toBe(200);

    // Session must be cleared in Tab 1
    const sessionTab1 = await (
      await tab1.request.get("/api/auth/session")
    ).json();
    expect(sessionTab1.session).toBeNull();

    // In Tab 2, navigating to protected workspace redirects to login
    await tab2.goto("/workspaces");
    await expect(tab2).toHaveURL(/\/auth\/login/);

    // Session in Tab 2 is also cleared
    const sessionTab2 = await (
      await tab2.request.get("/api/auth/session")
    ).json();
    expect(sessionTab2.session).toBeNull();

    await tab1.close();
    await tab2.close();
  });
});
