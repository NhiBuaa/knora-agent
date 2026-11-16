import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { spawn, type ChildProcess } from "node:child_process";
import path from "node:path";

const FIXTURE_PORT = 54329;
const FIXTURE_URL = `http://127.0.0.1:${FIXTURE_PORT}`;

describe("Supabase Fixture Server Guards & Subject Isolation", () => {
  let fixtureProcess: ChildProcess;

  beforeAll(async () => {
    const fixtureScript = path.resolve(
      __dirname,
      "e2e/support/supabase-fixture-server.mjs",
    );
    fixtureProcess = spawn(process.execPath, [fixtureScript], {
      env: {
        ...process.env,
        SUPABASE_FIXTURE_PORT: String(FIXTURE_PORT),
      },
      stdio: "pipe",
    });

    // Wait until fixture server is ready
    let ready = false;
    for (let i = 0; i < 50; i++) {
      try {
        const res = await fetch(`${FIXTURE_URL}/auth/v1/health`);
        if (res.ok) {
          ready = true;
          break;
        }
      } catch {
        // Retry
      }
      await new Promise((r) => setTimeout(r, 100));
    }
    if (!ready) {
      throw new Error("Fixture server failed to start on port " + FIXTURE_PORT);
    }
  });

  afterAll(() => {
    if (fixtureProcess && !fixtureProcess.killed) {
      fixtureProcess.kill();
    }
  });

  describe("Authentication guards", () => {
    it("rejects resource requests without Authorization header with 401", async () => {
      const endpoints = [
        { path: "/v1/auth/session", method: "GET" },
        { path: "/v1/workspaces/resolve", method: "POST", body: {} },
        { path: "/v1/workspaces", method: "GET" },
        { path: "/v1/workspaces", method: "POST", body: { name: "Test" } },
        { path: "/v1/workspaces/ws-default-workspace", method: "GET" },
        {
          path: "/v1/workspaces/ws-default-workspace/documents",
          method: "GET",
        },
        {
          path: "/v1/workspaces/ws-default-workspace/conversations",
          method: "GET",
        },
      ];

      for (const endpoint of endpoints) {
        const res = await fetch(`${FIXTURE_URL}${endpoint.path}`, {
          method: endpoint.method,
          headers: { "Content-Type": "application/json" },
          body: endpoint.body ? JSON.stringify(endpoint.body) : undefined,
        });
        expect(res.status).toBe(401);
        const data = await res.json();
        expect(data.error?.code).toBe("UNAUTHENTICATED");
      }
    });

    it("rejects requests with malformed or invalid tokens with 401", async () => {
      const res = await fetch(`${FIXTURE_URL}/v1/workspaces`, {
        headers: { Authorization: "Bearer invalid.fake.token" },
      });
      expect(res.status).toBe(401);
      const data = await res.json();
      expect(data.error?.code).toBe("UNAUTHENTICATED");
    });

    it("rejects revoked sessions with 401", async () => {
      // 1. Sign up a new user to obtain token and session
      const signupRes = await fetch(`${FIXTURE_URL}/auth/v1/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "revoked-test@example.test",
          password: "Password123!",
        }),
      });
      expect(signupRes.status).toBe(200);
      const { access_token } = await signupRes.json();

      // 2. Resource access works before revocation
      const beforeRes = await fetch(`${FIXTURE_URL}/v1/auth/session`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      expect(beforeRes.status).toBe(200);

      // 3. Logout to revoke session
      const logoutRes = await fetch(`${FIXTURE_URL}/auth/v1/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${access_token}` },
      });
      expect(logoutRes.status).toBe(204);

      // 4. Resource access is now rejected with 401
      const afterRes = await fetch(`${FIXTURE_URL}/v1/auth/session`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      expect(afterRes.status).toBe(401);
      const afterData = await afterRes.json();
      expect(afterData.error?.code).toBe("UNAUTHENTICATED");

      // Workspaces access with revoked session is also rejected with 401
      const wsRes = await fetch(`${FIXTURE_URL}/v1/workspaces`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      expect(wsRes.status).toBe(401);
    });
  });

  describe("Workspace subject binding and two-account data isolation", () => {
    it("isolates workspaces and resources between two independent user accounts", async () => {
      // Create Account A
      const signupA = await fetch(`${FIXTURE_URL}/auth/v1/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "userA@example.test",
          password: "Password123!",
        }),
      });
      const dataA = await signupA.json();
      const tokenA = dataA.access_token;

      // Create Account B
      const signupB = await fetch(`${FIXTURE_URL}/auth/v1/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "userB@example.test",
          password: "Password123!",
        }),
      });
      const dataB = await signupB.json();
      const tokenB = dataB.access_token;

      // User A resolves their workspace
      const resolveResA = await fetch(`${FIXTURE_URL}/v1/workspaces/resolve`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${tokenA}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });
      expect(resolveResA.status).toBe(200);
      const { workspace: wsA } = await resolveResA.json();
      expect(wsA).not.toBeNull();
      expect(wsA.id).toBeDefined();

      // User B resolves their workspace
      const resolveResB = await fetch(`${FIXTURE_URL}/v1/workspaces/resolve`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${tokenB}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });
      expect(resolveResB.status).toBe(200);
      const { workspace: wsB } = await resolveResB.json();
      expect(wsB).not.toBeNull();
      expect(wsB.id).toBeDefined();

      // Workspace IDs must be different
      expect(wsA.id).not.toBe(wsB.id);

      // User A lists workspaces: must see wsA but NOT wsB
      const listA = await fetch(`${FIXTURE_URL}/v1/workspaces`, {
        headers: { Authorization: `Bearer ${tokenA}` },
      });
      expect(listA.status).toBe(200);
      const listAData = await listA.json();
      const idsA = listAData.items.map((w: { id: string }) => w.id);
      expect(idsA).toContain(wsA.id);
      expect(idsA).not.toContain(wsB.id);

      // User B lists workspaces: must see wsB but NOT wsA
      const listB = await fetch(`${FIXTURE_URL}/v1/workspaces`, {
        headers: { Authorization: `Bearer ${tokenB}` },
      });
      expect(listB.status).toBe(200);
      const listBData = await listB.json();
      const idsB = listBData.items.map((w: { id: string }) => w.id);
      expect(idsB).toContain(wsB.id);
      expect(idsB).not.toContain(wsA.id);

      // Cross-account access: User A tries to access User B's workspace -> 403 Forbidden
      const crossWsGet = await fetch(`${FIXTURE_URL}/v1/workspaces/${wsB.id}`, {
        headers: { Authorization: `Bearer ${tokenA}` },
      });
      expect(crossWsGet.status).toBe(403);
      const crossWsData = await crossWsGet.json();
      expect(crossWsData.error?.code).toBe("WORKSPACE_ACCESS_DENIED");

      // Cross-account access: User A tries to read User B's documents -> 403 Forbidden
      const crossDocsGet = await fetch(
        `${FIXTURE_URL}/v1/workspaces/${wsB.id}/documents`,
        {
          headers: { Authorization: `Bearer ${tokenA}` },
        },
      );
      expect(crossDocsGet.status).toBe(403);
      const crossDocsData = await crossDocsGet.json();
      expect(crossDocsData.error?.code).toBe("WORKSPACE_ACCESS_DENIED");

      // Cross-account access: User A tries to create a conversation in User B's workspace -> 403 Forbidden
      const crossConvPost = await fetch(
        `${FIXTURE_URL}/v1/workspaces/${wsB.id}/conversations`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${tokenA}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}),
        },
      );
      expect(crossConvPost.status).toBe(403);
      const crossConvData = await crossConvPost.json();
      expect(crossConvData.error?.code).toBe("WORKSPACE_ACCESS_DENIED");

      // Legitimate access: User B accessing their own workspace -> 200 OK
      const selfWsGet = await fetch(`${FIXTURE_URL}/v1/workspaces/${wsB.id}`, {
        headers: { Authorization: `Bearer ${tokenB}` },
      });
      expect(selfWsGet.status).toBe(200);
    });
  });
});
