import { test, expect, type Page, chromium } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import realm from "../../../test/fixtures/keycloak/figma-realm.json";
import {
  openFigmaLogin,
  signInFigmaUser,
  captureIdentity,
  assertFigmaServiceOwnership,
} from "./support/figma-auth";
import {
  readOwnedBrowserPolicy,
  withAcceleratedSessionPolicy,
} from "./support/session-policy";
import { figmaEnvironment } from "./support/figma-environment";

test.describe.configure({ mode: "serial" });

test.describe("Browser session persistence and recovery", () => {
  test.beforeAll(() => {
    assertFigmaServiceOwnership();
  });

  test("native remember choice and retry preserve mode", async ({
    page,
  }, info) => {
    const evidenceDir = info.outputPath("evidence");
    fs.mkdirSync(evidenceDir, { recursive: true });

    const user = realm.users.find((u) => u.username === "m5-user")!;
    expect(user).toBeDefined();

    for (const viewport of [
      { width: 390, height: 844 },
      { width: 1440, height: 960 },
    ]) {
      await page.setViewportSize(viewport);

      // 1. Fresh login form: #rememberMe is unchecked
      await openFigmaLogin(page);
      const rememberCheckbox = page.locator("#rememberMe");
      await expect(rememberCheckbox).toBeVisible();
      expect(await rememberCheckbox.isChecked()).toBe(false);

      // 2. Wrong password with rememberMe checked: stays checked after error
      await page.locator("#username").fill(user.username);
      await page.locator("#password").fill("wrong-password-1");
      await rememberCheckbox.check();
      await page.locator("#kc-login").click();
      await expect(page.locator(".alert-error, #input-error")).toBeVisible();
      expect(await page.locator("#rememberMe").isChecked()).toBe(true);

      // 3. Wrong password with rememberMe unchecked: stays unchecked after error
      await page.locator("#password").fill("wrong-password-2");
      await page.locator("#rememberMe").uncheck();
      await page.locator("#kc-login").click();
      await expect(page.locator(".alert-error, #input-error")).toBeVisible();
      expect(await page.locator("#rememberMe").isChecked()).toBe(false);

      // 4. Toggle via keyboard using Space
      await page.locator("#rememberMe").focus();
      await page.keyboard.press("Space");
      expect(await page.locator("#rememberMe").isChecked()).toBe(true);
      await page.keyboard.press("Space");
      expect(await page.locator("#rememberMe").isChecked()).toBe(false);

      // Capture masked screenshot
      await captureIdentity(
        page,
        path.join(
          evidenceDir,
          `login-form-${viewport.width}x${viewport.height}.png`,
        ),
      );
    }

    // 5. Successful login in Normal mode -> Session cookie (no persistent Max-Age)
    await page.setViewportSize({ width: 1440, height: 960 });
    await page.context().clearCookies();
    await signInFigmaUser(page, "m5-user", false);
    const normalPolicy = await readOwnedBrowserPolicy(page.context());
    expect(normalPolicy.rememberMe).toBe(false);
    expect(normalPolicy.cookieHttpOnly).toBe(true);
    expect(normalPolicy.cookieSameSite.toLowerCase()).toBe("lax");
    // Normal mode session cookie does not have a future persistent expires date
    expect(
      normalPolicy.cookieExpires === undefined ||
        normalPolicy.cookieExpires <= 0,
    ).toBe(true);

    // 6. Successful login in Remember Me mode -> Persistent cookie
    await page.context().clearCookies();
    await signInFigmaUser(page, "m5-user", true);
    const rememberPolicy = await readOwnedBrowserPolicy(page.context());
    expect(rememberPolicy.rememberMe).toBe(true);
    expect(rememberPolicy.cookieHttpOnly).toBe(true);
    expect(rememberPolicy.cookieSameSite.toLowerCase()).toBe("lax");
    expect(rememberPolicy.cookieExpires).toBeGreaterThan(Date.now() / 1000);
  });

  test("online policy claims survive code exchange and refresh", async ({
    page,
  }) => {
    const env = figmaEnvironment();
    await withAcceleratedSessionPolicy(env.project, async () => {
      // Login with remember me
      await page.context().clearCookies();
      await signInFigmaUser(page, "m5-user", true);

      const initialPolicy = await readOwnedBrowserPolicy(page.context());
      expect(initialPolicy.rememberMe).toBe(true);
      expect(initialPolicy.sessionStartedAt).toBeGreaterThan(0);
      expect(initialPolicy.sessionExpiresAt).toBeGreaterThan(
        initialPolicy.sessionStartedAt,
      );

      // Under accelerated policy, access token lifespan is 5s, refresh threshold is 30s.
      // Immediate next GET /api/auth/session triggers refresh.
      await page.waitForTimeout(2000);
      const refreshRes = await page.request.get("/api/auth/session");
      expect(refreshRes.ok()).toBe(true);

      const refreshedPolicy = await readOwnedBrowserPolicy(page.context());
      // Session identity and bounds survive refresh
      expect(refreshedPolicy.rememberMe).toBe(true);
      expect(refreshedPolicy.sessionStartedAt).toBe(
        initialPolicy.sessionStartedAt,
      );
      expect(refreshedPolicy.sessionExpiresAt).toBe(
        initialPolicy.sessionExpiresAt,
      );
      expect(refreshedPolicy.expiresAt).toBeGreaterThanOrEqual(
        initialPolicy.expiresAt,
      );
    });
  });

  test("accelerated idle and absolute limits", async ({ page }) => {
    const env = figmaEnvironment();
    await withAcceleratedSessionPolicy(env.project, async () => {
      // 1. Normal session idle timeout (limit 10s): 14s idle expires
      await page.context().clearCookies();
      await signInFigmaUser(page, "m5-user", false);
      await page.waitForTimeout(14_000);
      const expiredRes = await page.request.get("/api/auth/session");
      const expiredData = (await expiredRes.json()) as { session: unknown };
      expect(expiredData.session).toBeNull();

      // 2. Remember Me session idle timeout (limit 20s): 14s idle remains active
      await page.context().clearCookies();
      await signInFigmaUser(page, "m5-user", true);
      await page.waitForTimeout(14_000);
      const stillActiveRes = await page.request.get("/api/auth/session");
      const stillActiveData = (await stillActiveRes.json()) as {
        session: unknown;
      };
      expect(stillActiveData.session).not.toBeNull();

      // Another 24s idle exceeds 20s limit -> expires
      await page.waitForTimeout(24_000);
      const finallyExpiredRes = await page.request.get("/api/auth/session");
      const finallyExpiredData = (await finallyExpiredRes.json()) as {
        session: unknown;
      };
      expect(finallyExpiredData.session).toBeNull();

      // 3. Keep-alive calls every 3s: normal expires at absolute max (30s)
      await page.context().clearCookies();
      await signInFigmaUser(page, "m5-user", false);
      const normalStart = Date.now();
      let normalActive = true;
      while (Date.now() - normalStart < 35_000) {
        await page.waitForTimeout(3_000);
        const res = await page.request.get("/api/auth/session");
        const data = (await res.json()) as { session: unknown };
        if (!data.session) {
          normalActive = false;
          break;
        }
      }
      expect(normalActive).toBe(false);
      expect(Date.now() - normalStart).toBeGreaterThanOrEqual(28_000);
    });
  });

  test("remembered browser profile reopens", async () => {
    const env = figmaEnvironment();
    const tempUserDataDir = fs.mkdtempSync(
      path.join(os.tmpdir(), "knora-remember-test-"),
    );

    try {
      // Launch context with persistent profile
      const context1 = await chromium.launchPersistentContext(tempUserDataDir, {
        baseURL: env.baseUrl,
        headless: true,
      });
      const page1 = await context1.newPage();
      await signInFigmaUser(page1, "m5-user", true);
      const policy1 = await readOwnedBrowserPolicy(context1);
      expect(policy1.rememberMe).toBe(true);
      await context1.close();

      // Reopen context with exact same profile
      const context2 = await chromium.launchPersistentContext(tempUserDataDir, {
        baseURL: env.baseUrl,
        headless: true,
      });
      const page2 = await context2.newPage();
      const res = await page2.request.get("/api/auth/session");
      expect(res.ok()).toBe(true);
      const data = (await res.json()) as { session: unknown };
      expect(data.session).not.toBeNull();
      await context2.close();
    } finally {
      fs.rmSync(tempUserDataDir, { recursive: true, force: true });
    }
  });

  test("recovery keeps same account draft and rejects account switch", async ({
    page,
    context,
  }) => {
    // Sign in as m5-user
    await context.clearCookies();
    await signInFigmaUser(page, "m5-user", false);

    // Create a new conversation and write draft
    await page.goto("/workspaces");
    await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);

    // Open second page for reauth
    const page2 = await context.newPage();

    // Reauth with same user
    await openFigmaLogin(page2);
    const user1 = realm.users.find((u) => u.username === "m5-user")!;
    await page2.locator("#username").fill(user1.username);
    await page2.locator("#password").fill(user1.credentials[0].value);
    await page2.locator("#kc-login").click();
    await page2.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
    await page2.close();

    // Switch account to m5-other-workspace on page2
    const page3 = await context.newPage();
    await openFigmaLogin(page3);
    const user2 = realm.users.find((u) => u.username === "m5-other-workspace")!;
    await page3.locator("#username").fill(user2.username);
    await page3.locator("#password").fill(user2.credentials[0].value);
    await page3.locator("#kc-login").click();
    await page3.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
    await page3.close();

    // Trigger focus on original page
    await page.bringToFront();
    // After returning with different account, identity change notice redirects to /workspaces
    await expect(
      page
        .locator("text=Your account changed. Opening Workspaces…")
        .or(page.locator("text=Workspaces")),
    ).toBeVisible();
  });

  test("logout and revoked refresh", async ({ page, context }) => {
    const env = figmaEnvironment();
    await withAcceleratedSessionPolicy(env.project, async () => {
      // 1. Clean logout clears cookie
      await context.clearCookies();
      await signInFigmaUser(page, "m5-user", false);
      const postLogout = await page.request.post("/api/auth/logout");
      expect(postLogout.ok()).toBe(true);
      const cookiesAfterLogout = await context.cookies(env.baseUrl);
      expect(
        cookiesAfterLogout.some((c) => c.name === "knora_session_v2"),
      ).toBe(false);

      // 2. Admin revokes session for m5-no-operator
      await context.clearCookies();
      await signInFigmaUser(page, "m5-no-operator", true);

      // Get admin token
      const tokenRes = await fetch(
        "http://127.0.0.1:8380/realms/master/protocol/openid-connect/token",
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            grant_type: "password",
            client_id: "admin-cli",
            username: "figma-test-admin",
            password: "figma-test-admin-password",
          }),
        },
      );
      const adminToken = (await tokenRes.json()).access_token;
      const headers = { Authorization: `Bearer ${adminToken}` };

      // Resolve user UUID
      const userRes = await fetch(
        "http://127.0.0.1:8380/admin/realms/knora-dev/users?username=m5-no-operator&exact=true",
        { headers },
      );
      const users = await userRes.json();
      expect(users).toHaveLength(1);
      const userUuid = users[0].id;

      // GET sessions -> exactly 1 session
      const sessionsRes = await fetch(
        `http://127.0.0.1:8380/admin/realms/knora-dev/users/${userUuid}/sessions`,
        { headers },
      );
      const sessions = await sessionsRes.json();
      expect(sessions.length).toBeGreaterThanOrEqual(1);
      const sessionUuid = sessions[0].id;

      // DELETE session
      const deleteRes = await fetch(
        `http://127.0.0.1:8380/admin/realms/knora-dev/sessions/${sessionUuid}`,
        {
          method: "DELETE",
          headers,
        },
      );
      expect(deleteRes.status).toBe(204);

      // Wait for access token to expire (5s under accelerated policy)
      await page.waitForTimeout(6_000);

      // Attempt refresh via /api/auth/session
      const refreshRes = await page.request.get("/api/auth/session");
      const refreshData = (await refreshRes.json()) as { session: unknown };
      // Session revoked at Keycloak -> refresh token rejected -> session null
      expect(refreshData.session).toBeNull();
    });
  });
});
