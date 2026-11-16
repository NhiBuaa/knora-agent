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

  test("successful registration creates user, receives session and navigates to workspaces", async ({
    page,
  }) => {
    await page.goto("/auth/register");
    await expect(
      page.getByRole("heading", { name: "Create your Knora account" }),
    ).toBeVisible();

    await page.getByLabel("Email").fill("newuser@example.test");
    await page.getByLabel("Password", { exact: true }).fill("Password123!");
    await page.getByLabel("Confirm password").fill("Password123!");
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page).toHaveURL(/\/workspaces/);

    const sessionResponse = await page.request.get("/api/auth/session");
    expect(sessionResponse.status()).toBe(200);
    const sessionBody = await sessionResponse.json();
    expect(sessionBody.session).not.toBeNull();
    expect(sessionBody.session.capabilities).toContain("documents:read");
  });

  test("recovery OTP flow updates password and revokes previous active session across all contexts", async ({
    browser,
  }) => {
    // 1. Context 1: User logs in with original password and establishes an active session
    const context1 = await browser.newContext();
    const page1 = await context1.newPage();
    await page1.goto("/auth/login");
    await page1.getByLabel("Email").fill("testuser@example.test");
    await page1.getByLabel("Password", { exact: true }).fill("Password123!");
    await page1.getByRole("button", { name: "Sign in" }).click();
    await expect(page1).toHaveURL(/\/workspaces/);

    const initialSession = await (
      await page1.request.get("/api/auth/session")
    ).json();
    expect(initialSession.session).not.toBeNull();

    // 2. Context 2: Initiates recovery flow via OTP -> new password
    const context2 = await browser.newContext();
    const page2 = await context2.newPage();
    await page2.goto("/auth/login");
    await page2.getByRole("link", { name: "Forgot your password?" }).click();

    await expect(page2).toHaveURL(/\/auth\/forgot-password/);
    await expect(
      page2.getByRole("heading", { name: "Forgot your password?" }),
    ).toBeVisible();

    await page2.getByLabel("Email").fill("testuser@example.test");
    await page2.getByRole("button", { name: "Send verification code" }).click();

    await expect(page2).toHaveURL(/\/auth\/reset-code/);
    await expect(
      page2.getByRole("heading", { name: "Enter verification code" }),
    ).toBeVisible();

    await page2.getByLabel("Six-digit reset code").fill("123456");
    await page2.getByRole("button", { name: "Verify code" }).click();

    await expect(page2).toHaveURL(/\/auth\/new-password/);
    await expect(
      page2.getByRole("heading", { name: "Choose a new password" }),
    ).toBeVisible();

    await page2
      .getByLabel("New password", { exact: true })
      .fill("NewPassword123!");
    await page2
      .getByLabel("Confirm new password", { exact: true })
      .fill("NewPassword123!");
    await page2.getByRole("button", { name: "Reset password" }).click();

    await expect(page2).toHaveURL(/\/auth\/login\?reset=1/);

    // 3. Verify previous active session in Context 1 is completely revoked
    const revokedSessionRes = await page1.request.get("/api/auth/session");
    const revokedSession = await revokedSessionRes.json();
    expect(revokedSession.session).toBeNull();

    await page1.goto("/workspaces");
    await expect(page1).toHaveURL(/\/auth\/login/);

    // 4. Verify login with newly updated password works
    await page2.getByLabel("Email").fill("testuser@example.test");
    await page2.getByLabel("Password", { exact: true }).fill("NewPassword123!");
    await page2.getByRole("button", { name: "Sign in" }).click();
    await expect(page2).toHaveURL(/\/workspaces/);

    await context1.close();
    await context2.close();
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

  test("expiring token triggers concurrent multi-tab refresh cleanly with fixture barrier verification", async ({
    context,
  }) => {
    // Reset refresh count on fixture server
    await fetch("http://127.0.0.1:54321/fixture-stats/reset-refresh-count", {
      method: "POST",
    });

    const tab1 = await context.newPage();
    await tab1.goto("/auth/login");
    // Login with concurrent-expiring user (expires_in: 35s > 30s)
    await tab1
      .getByLabel("Email")
      .fill("concurrent-expiring-user@example.test");
    await tab1.getByLabel("Password", { exact: true }).fill("Password123!");
    await tab1.getByRole("button", { name: "Sign in" }).click();
    await expect(tab1).toHaveURL(/\/workspaces/);

    // Verify navigating to /workspaces did NOT trigger an early refresh
    const initialStats = await (
      await fetch("http://127.0.0.1:54321/fixture-stats/refresh-count")
    ).json();
    expect(initialStats.count).toBe(0);

    const tab2 = await context.newPage();
    await tab2.goto("/workspaces");
    await expect(tab2).toHaveURL(/\/workspaces/);

    // Wait 6 seconds so remaining token validity is ~28-29s (within the <= 30s near-expiry window)
    await tab1.waitForTimeout(6000);

    // Both tabs request session concurrently while token is near expiry
    const [res1, res2] = await Promise.all([
      tab1.request.get("/api/auth/session"),
      tab2.request.get("/api/auth/session"),
    ]);

    expect(res1.status()).toBe(200);
    expect(res2.status()).toBe(200);
    const s1 = await res1.json();
    const s2 = await res2.json();
    expect(s1.session).not.toBeNull();
    expect(s2.session).not.toBeNull();
    expect(s1.session.subject).toBe(s2.session.subject);

    // Verify that the concurrent requests were deduplicated and fixture saw exactly 1 refresh call
    const finalStats = await (
      await fetch("http://127.0.0.1:54321/fixture-stats/refresh-count")
    ).json();
    expect(finalStats.count).toBe(1);

    await tab1.close();
    await tab2.close();
  });

  test("logout terminates session, rejects old session across all tabs and rejects old cookie replayed from an independent context", async ({
    browser,
    context,
  }) => {
    const tab1 = await context.newPage();
    await tab1.goto("/auth/login");
    await tab1.getByLabel("Email").fill("testuser@example.test");
    await tab1.getByLabel("Password", { exact: true }).fill("Password123!");
    await tab1.getByRole("button", { name: "Sign in" }).click();
    await expect(tab1).toHaveURL(/\/workspaces/);

    // Save cookies before logout
    const savedCookies = await context.cookies();
    expect(savedCookies.some((c) => c.name === "knora_session")).toBe(true);

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

    // In Tab 2, reloading protected workspace redirects to login
    await tab2.reload();
    await expect(tab2).toHaveURL(/\/auth\/login/);

    // Session in Tab 2 is also cleared
    const sessionTab2 = await (
      await tab2.request.get("/api/auth/session")
    ).json();
    expect(sessionTab2.session).toBeNull();

    await tab1.close();
    await tab2.close();

    // Now verify old cookie replay from a completely independent browser context is rejected
    const isolatedContext = await browser.newContext();
    await isolatedContext.addCookies(savedCookies);
    const isolatedPage = await isolatedContext.newPage();

    // The backend/BFF must reject the revoked session
    const replaySessionRes =
      await isolatedPage.request.get("/api/auth/session");
    const replaySessionData = await replaySessionRes.json();
    expect(replaySessionData.session).toBeNull();

    // Navigating to protected workspace must redirect to login
    await isolatedPage.goto("/workspaces");
    await expect(isolatedPage).toHaveURL(/\/auth\/login/);

    await isolatedContext.close();
  });
});
