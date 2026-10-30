import { test, expect, type BrowserContext, chromium } from "@playwright/test";
import { randomUUID } from "node:crypto";
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
  getKeycloakAdminToken,
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
    test.setTimeout(180_000);
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
      await expect(
        page.locator(
          "[role='alert'], .alert-error, #input-error, .pf-v5-c-alert",
        ),
      ).toBeVisible();
      expect(await page.locator("#rememberMe").isChecked()).toBe(true);

      // 3. Wrong password with rememberMe unchecked: stays unchecked after error
      await page.locator("#password").fill("wrong-password-2");
      await page.locator("#rememberMe").uncheck();
      await page.locator("#kc-login").click();
      await expect(
        page.locator(
          "[role='alert'], .alert-error, #input-error, .pf-v5-c-alert",
        ),
      ).toBeVisible();
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

    // Assert all cookies satisfy <= 4096 bytes constraint
    const cookies = await page.context().cookies();
    for (const c of cookies) {
      expect(c.name.length + c.value.length).toBeLessThanOrEqual(4096);
    }
  });

  test("online policy claims survive code exchange and refresh", async ({
    page,
  }) => {
    test.setTimeout(90_000);
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

  test("accelerated idle and absolute limits", async ({ browser }) => {
    test.setTimeout(240_000);
    const env = figmaEnvironment();
    const activeContexts: BrowserContext[] = [];

    await withAcceleratedSessionPolicy(env.project, async () => {
      try {
        // 1. Normal session idle timeout (accelerated limit 10s): 14s idle expires
        const normalIdleCtx = await browser.newContext({
          baseURL: env.baseUrl,
        });
        activeContexts.push(normalIdleCtx);
        const p1 = await normalIdleCtx.newPage();
        await signInFigmaUser(p1, "m5-user", false);
        await p1.waitForTimeout(14_000);
        const expiredRes = await p1.request.get("/api/auth/session");
        const expiredData = (await expiredRes.json()) as { session: unknown };
        expect(expiredData.session).toBeNull();
        await normalIdleCtx.close();

        // 2. Remember Me session idle timeout (accelerated limit 20s): 14s idle remains active
        const remIdleCtx = await browser.newContext({ baseURL: env.baseUrl });
        activeContexts.push(remIdleCtx);
        const p2 = await remIdleCtx.newPage();
        await signInFigmaUser(p2, "m5-user", true);
        await p2.waitForTimeout(14_000);
        const stillActiveRes = await p2.request.get("/api/auth/session");
        const stillActiveData = (await stillActiveRes.json()) as {
          session: unknown;
        };
        expect(stillActiveData.session).not.toBeNull();

        // Another 24s idle (> 20s limit after refresh) -> expires
        await p2.waitForTimeout(24_000);
        const finallyExpiredRes = await p2.request.get("/api/auth/session");
        const finallyExpiredData = (await finallyExpiredRes.json()) as {
          session: unknown;
        };
        expect(finallyExpiredData.session).toBeNull();
        await remIdleCtx.close();

        // 3. Keep-alive calls every 3s: normal expires at absolute max (30s)
        const normalAbsCtx = await browser.newContext({ baseURL: env.baseUrl });
        activeContexts.push(normalAbsCtx);
        const p3 = await normalAbsCtx.newPage();
        await signInFigmaUser(p3, "m5-user", false);
        const normalStart = Date.now();
        let normalActive = true;
        while (Date.now() - normalStart < 35_000) {
          await p3.waitForTimeout(3_000);
          const res = await p3.request.get("/api/auth/session");
          const data = (await res.json()) as { session: unknown };
          if (!data.session) {
            normalActive = false;
            break;
          }
        }
        expect(normalActive).toBe(false);
        expect(Date.now() - normalStart).toBeGreaterThanOrEqual(28_000);
        await normalAbsCtx.close();

        // 4. Keep-alive calls every 3s: Remember Me expires at absolute max (60s)
        const remAbsCtx = await browser.newContext({ baseURL: env.baseUrl });
        activeContexts.push(remAbsCtx);
        const p4 = await remAbsCtx.newPage();
        await signInFigmaUser(p4, "m5-user", true);
        const remStart = Date.now();
        let remActive = true;
        while (Date.now() - remStart < 68_000) {
          await p4.waitForTimeout(3_000);
          const res = await p4.request.get("/api/auth/session");
          const data = (await res.json()) as { session: unknown };
          if (!data.session) {
            remActive = false;
            break;
          }
        }
        expect(remActive).toBe(false);
        expect(Date.now() - remStart).toBeGreaterThanOrEqual(58_000);
        await remAbsCtx.close();
      } finally {
        for (const ctx of activeContexts) {
          await ctx.close().catch(() => {});
        }
      }
    });
  });

  test("remembered browser profile reopens", async () => {
    test.setTimeout(90_000);
    const env = figmaEnvironment();
    const tempUserDataDir = fs.mkdtempSync(
      path.join(os.tmpdir(), "knora-remember-test-"),
    );

    let context1: BrowserContext | undefined;
    let context2: BrowserContext | undefined;
    try {
      // Launch context with persistent profile
      context1 = await chromium.launchPersistentContext(tempUserDataDir, {
        baseURL: env.baseUrl,
        headless: true,
      });
      const page1 = await context1.newPage();
      await signInFigmaUser(page1, "m5-user", true);
      const policy1 = await readOwnedBrowserPolicy(context1);
      expect(policy1.rememberMe).toBe(true);
      await context1.close();
      context1 = undefined;

      // Reopen context with exact same profile
      context2 = await chromium.launchPersistentContext(tempUserDataDir, {
        baseURL: env.baseUrl,
        headless: true,
      });
      const page2 = await context2.newPage();
      const res = await page2.request.get("/api/auth/session");
      expect(res.ok()).toBe(true);
      const data = (await res.json()) as { session: unknown };
      expect(data.session).not.toBeNull();
      await context2.close();
      context2 = undefined;
    } finally {
      if (context1) await context1.close().catch(() => {});
      if (context2) await context2.close().catch(() => {});
      fs.rmSync(tempUserDataDir, { recursive: true, force: true });
    }
  });

  test("recovery keeps same account draft and rejects account switch", async ({
    browser,
  }) => {
    test.setTimeout(240_000);
    const env = figmaEnvironment();
    const context = await browser.newContext({ baseURL: env.baseUrl });
    const page = await context.newPage();

    try {
      // 1. Sign in as m5-user (normal mode)
      await signInFigmaUser(page, "m5-user", false);

      // 2. Resolve workspace ID and create a real conversation
      const wsRes = await page.request.get("/api/v1/workspaces");
      expect(wsRes.ok()).toBe(true);
      const workspaces = (await wsRes.json()) as {
        items: Array<{ id: string }>;
      };
      expect(workspaces.items.length).toBeGreaterThan(0);
      const workspaceId = workspaces.items[0].id;

      const sessionRes = await page.request.get("/api/auth/session");
      expect(sessionRes.ok()).toBe(true);
      const sessionData = (await sessionRes.json()) as {
        session: { issuer: string; subject: string };
      };
      expect(sessionData.session).toBeDefined();

      const convRes = await page.request.post(
        `/api/v1/workspaces/${workspaceId}/conversations`,
        {
          data: {},
          headers: {
            "Idempotency-Key": randomUUID(),
            "x-knora-expected-issuer": sessionData.session.issuer,
            "x-knora-expected-subject": sessionData.session.subject,
          },
        },
      );
      expect(convRes.ok()).toBe(true);
      const conversation = (await convRes.json()) as { id: string };
      const conversationId = conversation.id;

      // 3. Mount the chat tab and write a draft in composer
      await page.goto(
        `/workspaces/${workspaceId}/conversations/${conversationId}`,
      );
      const textarea = page.locator("textarea");
      await expect(textarea).toBeVisible();

      const draftText = "Preserved draft before session expiry check";
      await textarea.fill(draftText);
      expect(await textarea.inputValue()).toBe(draftText);

      // Track network requests: assert 0 POST replay and single history read
      let postCount = 0;
      let historyReadCount = 0;
      page.on("request", (req) => {
        const url = new URL(req.url());
        if (
          req.method() === "POST" &&
          (url.pathname.includes("/conversations") ||
            url.pathname.includes("/turns"))
        ) {
          postCount++;
        }
        if (
          req.method() === "GET" &&
          (url.pathname ===
            `/api/v1/workspaces/${workspaceId}/conversations/${conversationId}` ||
            url.pathname ===
              `/api/v1/workspaces/${workspaceId}/conversations/${conversationId}/turns`)
        ) {
          historyReadCount++;
        }
      });

      // 4. Clear cookies to simulate session expiry and trigger focus recovery
      await context.clearCookies();
      await page.evaluate(() => {
        window.dispatchEvent(new Event("blur"));
        window.dispatchEvent(new Event("focus"));
      });
      await expect(page.locator("text=Your session has expired")).toBeVisible();
      expect(await textarea.inputValue()).toBe(draftText);
      expect(postCount).toBe(0);

      // 5. Re-authenticate same account (m5-user) in a second page (forced reauth)
      const page2 = await context.newPage();
      await signInFigmaUser(page2, "m5-user", false, true);
      await page2.close();

      // Return to chat tab and click Reload history
      await page.bringToFront();
      historyReadCount = 0;
      await page.getByRole("button", { name: "Reload history" }).click();
      await expect(
        page.locator("text=Your session has expired"),
      ).not.toBeVisible();

      // Assertions for same account recovery:
      // - History GET fetched exactly 1 time
      // - 0 automatic POST replay
      // - Draft preserved in composer
      // - Textarea unlocked
      expect(historyReadCount).toBe(1);
      expect(postCount).toBe(0);
      expect(await textarea.inputValue()).toBe(draftText);
      await expect(textarea).toBeEnabled();

      // 6. Account switch to m5-other-workspace in a third page (forced reauth)
      const page3 = await context.newPage();
      await signInFigmaUser(page3, "m5-other-workspace", false, true);
      await page3.close();

      // Return to original tab and trigger focus
      await page.bringToFront();
      await page.evaluate(() => {
        window.dispatchEvent(new Event("blur"));
        window.dispatchEvent(new Event("focus"));
      });

      // Assertions for account switch (F7):
      // - Navigates exactly to /workspaces (not inside a conversation)
      // - Scoped UI of previous conversation (draft, turn cards, textarea) is removed
      // - 0 automatic POST replay
      await page.waitForURL((url) => url.pathname === "/workspaces", {
        timeout: 15_000,
      });
      expect(new URL(page.url()).pathname).toBe("/workspaces");
      await expect(page.locator("textarea#conversation-question")).toHaveCount(
        0,
      );
      await expect(page.locator(`text=${draftText}`)).toHaveCount(0);
      await expect(page.locator("ol.flex.flex-col")).toHaveCount(0);
      expect(postCount).toBe(0);
    } finally {
      await context.close().catch(() => {});
    }
  });

  test("logout and revoked refresh", async ({ page, context }) => {
    test.setTimeout(180_000);
    const env = figmaEnvironment();
    await withAcceleratedSessionPolicy(env.project, async () => {
      // 1. Clean logout with Origin header clears cookie
      await context.clearCookies();
      await signInFigmaUser(page, "m5-user", false);
      const postLogout = await page.request.post("/api/auth/logout", {
        headers: { Origin: env.baseUrl },
      });
      expect(postLogout.ok()).toBe(true);
      const cookiesAfterLogout = await context.cookies(env.baseUrl);
      expect(
        cookiesAfterLogout.some((c) => c.name === "knora_session_v2"),
      ).toBe(false);

      // 2. Admin revokes single session for m5-no-operator
      await context.clearCookies();
      await signInFigmaUser(page, "m5-no-operator", true);

      // Get admin token
      const adminToken = await getKeycloakAdminToken();
      const headers = { Authorization: `Bearer ${adminToken}` };

      // Resolve user UUID
      const userRes = await fetch(
        "http://127.0.0.1:8380/admin/realms/knora-dev/users?username=m5-no-operator&exact=true",
        { headers },
      );
      const users = (await userRes.json()) as Array<{ id: string }>;
      expect(users).toHaveLength(1);
      const userUuid = users[0].id;

      // GET sessions -> exactly 1 synthetic user session with client knora-web
      const sessionsRes = await fetch(
        `http://127.0.0.1:8380/admin/realms/knora-dev/users/${userUuid}/sessions`,
        { headers },
      );
      const sessions = (await sessionsRes.json()) as Array<{
        id: string;
        clients: Record<string, string>;
      }>;
      const knoraSessions = sessions.filter(
        (s) => s.clients && Object.values(s.clients).includes("knora-web"),
      );
      expect(knoraSessions).toHaveLength(1);
      const sessionUuid = knoraSessions[0].id;

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

  test("continuous real idle 15 and 33 minutes", async ({ browser }, info) => {
    test.setTimeout(45 * 60 * 1000);
    const env = figmaEnvironment();
    const evidenceDir = info.outputPath("evidence");
    fs.mkdirSync(evidenceDir, { recursive: true });

    // Function to compute cryptographic SHA-256 policy digest from measured server state
    async function measurePolicyDigest(): Promise<{
      version: string;
      digest: string;
      state: Record<string, unknown>;
    }> {
      const adminToken = await getKeycloakAdminToken();
      const sInfoRes = await fetch("http://127.0.0.1:8380/admin/serverinfo", {
        headers: { Authorization: `Bearer ${adminToken}` },
      });
      if (!sInfoRes.ok) {
        throw new Error(`Failed to read serverinfo: HTTP ${sInfoRes.status}`);
      }
      const sInfo = (await sInfoRes.json()) as {
        systemInfo?: { version?: string };
      };
      const version = sInfo.systemInfo?.version;
      if (!version) {
        throw new Error("Keycloak serverinfo missing systemInfo.version");
      }

      const realmRes = await fetch(
        "http://127.0.0.1:8380/admin/realms/knora-dev",
        { headers: { Authorization: `Bearer ${adminToken}` } },
      );
      if (!realmRes.ok) {
        throw new Error(`Failed to read realm policy: HTTP ${realmRes.status}`);
      }
      const realmData = (await realmRes.json()) as Record<string, unknown>;

      const clientRes = await fetch(
        "http://127.0.0.1:8380/admin/realms/knora-dev/clients?clientId=knora-web",
        { headers: { Authorization: `Bearer ${adminToken}` } },
      );
      if (!clientRes.ok) {
        throw new Error(`Failed to read client: HTTP ${clientRes.status}`);
      }
      const clients = (await clientRes.json()) as Array<{
        attributes?: Record<string, string>;
      }>;
      const clientAttrs = clients[0]?.attributes ?? {};

      const state = {
        keycloakVersion: version,
        rememberMe: Boolean(realmData.rememberMe),
        ssoSessionIdleTimeout: Number(realmData.ssoSessionIdleTimeout),
        ssoSessionMaxLifespan: Number(realmData.ssoSessionMaxLifespan),
        ssoSessionIdleTimeoutRememberMe: Number(
          realmData.ssoSessionIdleTimeoutRememberMe,
        ),
        ssoSessionMaxLifespanRememberMe: Number(
          realmData.ssoSessionMaxLifespanRememberMe,
        ),
        clientSessionIdleTimeout: Number(realmData.clientSessionIdleTimeout),
        clientSessionMaxLifespan: Number(realmData.clientSessionMaxLifespan),
        accessTokenLifespan: Number(realmData.accessTokenLifespan),
        clientAccessTokenLifespan: clientAttrs["access.token.lifespan"] ?? null,
      };

      const canonicalJson = JSON.stringify(state, Object.keys(state).sort());
      const digestBuf = await crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(canonicalJson),
      );
      const digest =
        "sha256:" +
        Array.from(new Uint8Array(digestBuf))
          .map((b) => b.toString(16).padStart(2, "0"))
          .join("");

      return { version, digest, state };
    }

    // 0. Pre-measurement of policy digest before quiet window
    const initialPolicy = await measurePolicyDigest();

    // 3 parallel independent browser contexts
    const normal15Ctx = await browser.newContext({ baseURL: env.baseUrl });
    const normal33Ctx = await browser.newContext({ baseURL: env.baseUrl });
    const rem33Ctx = await browser.newContext({ baseURL: env.baseUrl });
    const allContexts = [normal15Ctx, normal33Ctx, rem33Ctx];

    try {
      const p15 = await normal15Ctx.newPage();
      const p33 = await normal33Ctx.newPage();
      const pRem = await rem33Ctx.newPage();

      // Native login for each context
      await signInFigmaUser(p15, "m5-user", false);
      await signInFigmaUser(p33, "m5-user", false);
      await signInFigmaUser(pRem, "m5-user", true);

      // Assert policy and cookie boundaries
      const pol15 = await readOwnedBrowserPolicy(normal15Ctx);
      const pol33 = await readOwnedBrowserPolicy(normal33Ctx);
      const polRem = await readOwnedBrowserPolicy(rem33Ctx);

      expect(pol15.rememberMe).toBe(false);
      expect(pol33.rememberMe).toBe(false);
      expect(polRem.rememberMe).toBe(true);

      for (const ctx of allContexts) {
        const cookies = await ctx.cookies();
        for (const c of cookies) {
          expect(c.name.length + c.value.length).toBeLessThanOrEqual(4096);
        }
      }

      // Comprehensive request predicate: intercepts any renewing or protected route
      let renewingRequests15 = 0;
      let renewingRequests33 = 0;
      let renewingRequestsRem = 0;

      const isRenewingOrProtectedRoute = (urlStr: string) => {
        try {
          const u = new URL(urlStr);
          const p = u.pathname;
          return (
            p.startsWith("/api/auth/") ||
            p.startsWith("/api/v1/") ||
            p.includes("/protocol/openid-connect/") ||
            p.includes("/realms/knora-dev/")
          );
        } catch {
          return false;
        }
      };

      normal15Ctx.on("request", (req) => {
        if (isRenewingOrProtectedRoute(req.url())) renewingRequests15++;
      });
      normal33Ctx.on("request", (req) => {
        if (isRenewingOrProtectedRoute(req.url())) renewingRequests33++;
      });
      rem33Ctx.on("request", (req) => {
        if (isRenewingOrProtectedRoute(req.url())) renewingRequestsRem++;
      });

      const idle15Ms = Number(process.env.FIGMA_IDLE_15_SECONDS ?? 900) * 1000;
      const idle33Ms = Number(process.env.FIGMA_IDLE_33_SECONDS ?? 1980) * 1000;
      const monotonicStart = performance.now();
      const quietStartIso = new Date().toISOString();

      // 1. Wait 15 minutes (900s)
      await new Promise((resolve) => setTimeout(resolve, idle15Ms));
      expect(renewingRequests15).toBe(0);

      // After 900s: normal15 is still active!
      const res15 = await p15.request.get("/api/auth/session");
      expect(res15.ok()).toBe(true);
      const data15 = (await res15.json()) as { session: unknown };
      expect(data15.session).not.toBeNull();
      const ws15 = await p15.request.get("/api/v1/workspaces");
      expect(ws15.ok()).toBe(true);

      // 2. Wait remaining time to 33 minutes (1980s - 900s = 1080s)
      await new Promise((resolve) => setTimeout(resolve, idle33Ms - idle15Ms));
      expect(renewingRequests33).toBe(0);
      expect(renewingRequestsRem).toBe(0);

      // After 1980s: normal33 has expired (normal idle limit 1800s exceeded)
      const res33 = await p33.request.get("/api/auth/session");
      const data33 = (await res33.json()) as { session: unknown };
      expect(data33.session).toBeNull();

      // After 1980s: rem33 is still within 7-day idle limit -> refresh succeeds
      const wsRem = await pRem.request.get("/api/v1/workspaces");
      expect(wsRem.ok()).toBe(true);
      const resRem = await pRem.request.get("/api/auth/session");
      const dataRem = (await resRem.json()) as { session: unknown };
      expect(dataRem.session).not.toBeNull();

      // 3. Post-measurement: verify zero policy drift during quiet window
      const finalPolicy = await measurePolicyDigest();
      expect(finalPolicy.digest).toBe(initialPolicy.digest);

      // 4. Fresh UI navigation tests:
      // normal33 navigates to protected /workspaces -> redirected to login
      const nav33 = await normal33Ctx.newPage();
      await nav33.goto(env.baseUrl + "/workspaces");
      await nav33.waitForURL(
        (url) =>
          url.pathname.includes("/auth") ||
          url.pathname.includes("/login") ||
          url.port === "8380",
        { timeout: 15_000 },
      );
      expect(new URL(nav33.url()).pathname).not.toBe("/workspaces");
      await expect(
        nav33.locator(
          "#username, input[name='username'], [role='alert'], text=Sign in",
        ),
      ).toBeVisible({ timeout: 15_000 });
      await nav33.close();

      // rem33 navigates to protected /workspaces -> refreshed, enters workspace shell
      const navRem = await rem33Ctx.newPage();
      await navRem.goto(env.baseUrl + "/workspaces");
      await navRem.waitForURL((url) => url.pathname === "/workspaces", {
        timeout: 15_000,
      });
      expect(new URL(navRem.url()).pathname).toBe("/workspaces");
      await expect(
        navRem.locator(
          "main, [data-testid='workspace-shell'], text=Workspaces",
        ),
      ).toBeVisible({ timeout: 15_000 });
      const checkWs = await navRem.request.get("/api/v1/workspaces");
      expect(checkWs.ok()).toBe(true);
      const wsData = (await checkWs.json()) as {
        items?: Array<{ id: string }>;
      };
      expect(wsData.items?.length).toBeGreaterThan(0);
      await navRem.close();

      // Capture masked screenshots
      for (const vp of [
        { width: 390, height: 844 },
        { width: 1440, height: 960 },
      ]) {
        await pRem.setViewportSize(vp);
        await captureIdentity(
          pRem,
          path.join(
            evidenceDir,
            `real-idle-rem33-${vp.width}x${vp.height}.png`,
          ),
        );
      }

      // Record evidence JSON (schemaVersion 1) with monotonic measurements and real policy digest
      const monotonicEnd = performance.now();
      const quietEndIso = new Date().toISOString();
      const elapsedSeconds = Number(
        ((monotonicEnd - monotonicStart) / 1000).toFixed(2),
      );
      const evidenceData = {
        schemaVersion: 1,
        subjectSha: process.env.FIGMA_SUBJECT_SHA ?? "HEAD",
        project: env.project,
        KeycloakVersion: finalPolicy.version,
        policyDigest: finalPolicy.digest,
        policyState: finalPolicy.state,
        contextCases: ["normal15", "normal33", "remembered33"],
        startedAt: quietStartIso,
        finishedAt: quietEndIso,
        monotonicStartMs: Math.round(monotonicStart),
        monotonicEndMs: Math.round(monotonicEnd),
        elapsedSeconds: elapsedSeconds,
        zeroRenewingRequestsDuringIdle:
          renewingRequests15 === 0 &&
          renewingRequests33 === 0 &&
          renewingRequestsRem === 0,
        renewingRequestCounts: {
          normal15: renewingRequests15,
          normal33: renewingRequests33,
          remembered33: renewingRequestsRem,
        },
        zeroPolicyDrift: finalPolicy.digest === initialPolicy.digest,
        outcomes: {
          normal15StillActive: data15.session !== null,
          normal33Expired: data33.session === null,
          remembered33Refreshed: dataRem.session !== null,
        },
        freshNavigationOutcomes: {
          normal33RedirectedToLogin: true,
          remembered33EnteredWorkspace: true,
        },
        cookieSizeVerified: true,
        screenshots: [
          "real-idle-rem33-390x844.png",
          "real-idle-rem33-1440x960.png",
        ],
      };
      fs.writeFileSync(
        path.join(evidenceDir, "session-persistence-real-idle.json"),
        JSON.stringify(evidenceData, null, 2),
        "utf8",
      );
    } finally {
      for (const ctx of allContexts) {
        await ctx.close().catch(() => {});
      }
    }
  });
});
