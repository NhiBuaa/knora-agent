import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { spawn, type ChildProcess } from "node:child_process";
import http from "node:http";
import net from "node:net";
import path from "node:path";

function getAvailablePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => {
      const port = (srv.address() as net.AddressInfo).port;
      srv.close((err) => (err ? reject(err) : resolve(port)));
    });
    srv.on("error", reject);
  });
}

function checkPortPreoccupied(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.setTimeout(200);
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("error", () => {
      socket.destroy();
      resolve(false);
    });
    socket.once("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.connect(port, "127.0.0.1");
  });
}

async function spawnFixtureServer(port: number): Promise<{
  process: ChildProcess;
  url: string;
}> {
  const preoccupied = await checkPortPreoccupied(port);
  if (preoccupied) {
    throw new Error(`Port ${port} is already preoccupied by another server`);
  }

  const fixtureScript = path.resolve(
    __dirname,
    "e2e/support/supabase-fixture-server.mjs",
  );

  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [fixtureScript], {
      env: {
        ...process.env,
        SUPABASE_FIXTURE_PORT: String(port),
      },
      stdio: ["ignore", "pipe", "pipe"],
    });

    let settled = false;
    let stderr = "";

    child.stderr?.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", (err) => {
      if (!settled) {
        settled = true;
        reject(err);
      }
    });

    child.on("exit", (code) => {
      if (!settled) {
        settled = true;
        reject(
          new Error(
            `Fixture server child exited early with code ${code}. Stderr: ${stderr}`,
          ),
        );
      }
    });

    const url = `http://127.0.0.1:${port}`;
    const pollInterval = setInterval(async () => {
      if (settled) {
        clearInterval(pollInterval);
        return;
      }
      try {
        const res = await fetch(`${url}/auth/v1/health`);
        if (res.ok) {
          settled = true;
          clearInterval(pollInterval);
          resolve({ process: child, url });
        }
      } catch {
        // Retry polling
      }
    }, 50);

    setTimeout(() => {
      if (!settled) {
        settled = true;
        clearInterval(pollInterval);
        child.kill();
        reject(
          new Error(
            `Timed out waiting for fixture server on port ${port}. Stderr: ${stderr}`,
          ),
        );
      }
    }, 10_000);
  });
}

async function stopFixtureServer(child: ChildProcess | undefined) {
  if (!child || child.killed || child.exitCode !== null) return;
  const exitPromise = new Promise((resolve) => child.once("exit", resolve));
  child.kill();
  await exitPromise;
}

describe("Supabase Fixture Server Guards & Subject Isolation", () => {
  let mainFixture: { process: ChildProcess; url: string };

  beforeAll(async () => {
    const port = await getAvailablePort();
    mainFixture = await spawnFixtureServer(port);
  });

  afterAll(async () => {
    await stopFixtureServer(mainFixture?.process);
  });

  describe("Preoccupied port handling", () => {
    it("fails startup and refuses mutation when port is preoccupied by another server", async () => {
      const dummyPort = await getAvailablePort();
      let dummyMutated = false;

      const dummyServer = http.createServer((req, res) => {
        if (req.method !== "GET") {
          dummyMutated = true;
        }
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            service: "dummy-preoccupied",
            mutated: dummyMutated,
          }),
        );
      });

      await new Promise<void>((resolve) =>
        dummyServer.listen(dummyPort, "127.0.0.1", () => resolve()),
      );

      try {
        // Attempting to spawn fixture server on the occupied port must fail
        await expect(spawnFixtureServer(dummyPort)).rejects.toThrow(
          /preoccupied|already/i,
        );

        // Verify the existing dummy server was NOT mutated or killed
        const checkRes = await fetch(`http://127.0.0.1:${dummyPort}`);
        expect(checkRes.status).toBe(200);
        const checkBody = await checkRes.json();
        expect(checkBody.service).toBe("dummy-preoccupied");
        expect(checkBody.mutated).toBe(false);
      } finally {
        await new Promise<void>((resolve) =>
          dummyServer.close(() => resolve()),
        );
      }
    });
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
        const res = await fetch(`${mainFixture.url}${endpoint.path}`, {
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
      const res = await fetch(`${mainFixture.url}/v1/workspaces`, {
        headers: { Authorization: "Bearer invalid.fake.token" },
      });
      expect(res.status).toBe(401);
      const data = await res.json();
      expect(data.error?.code).toBe("UNAUTHENTICATED");
    });

    it("rejects revoked sessions with 401", async () => {
      // 1. Sign up a new user to obtain token and session
      const signupRes = await fetch(`${mainFixture.url}/auth/v1/signup`, {
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
      const beforeRes = await fetch(`${mainFixture.url}/v1/auth/session`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      expect(beforeRes.status).toBe(200);

      // 3. Logout to revoke session
      const logoutRes = await fetch(`${mainFixture.url}/auth/v1/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${access_token}` },
      });
      expect(logoutRes.status).toBe(204);

      // 4. Resource access is now rejected with 401
      const afterRes = await fetch(`${mainFixture.url}/v1/auth/session`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      expect(afterRes.status).toBe(401);
      const afterData = await afterRes.json();
      expect(afterData.error?.code).toBe("UNAUTHENTICATED");

      // Workspaces access with revoked session is also rejected with 401
      const wsRes = await fetch(`${mainFixture.url}/v1/workspaces`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      expect(wsRes.status).toBe(401);
    });
  });

  describe("Workspace subject binding and cross-account isolation", () => {
    it("isolates workspaces and resources between two independent user accounts", async () => {
      // Create Account A
      const signupA = await fetch(`${mainFixture.url}/auth/v1/signup`, {
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
      const signupB = await fetch(`${mainFixture.url}/auth/v1/signup`, {
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
      const resolveResA = await fetch(
        `${mainFixture.url}/v1/workspaces/resolve`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${tokenA}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}),
        },
      );
      expect(resolveResA.status).toBe(200);
      const { workspace: wsA } = await resolveResA.json();
      expect(wsA).not.toBeNull();
      expect(wsA.id).toBeDefined();

      // User B resolves their workspace
      const resolveResB = await fetch(
        `${mainFixture.url}/v1/workspaces/resolve`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${tokenB}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}),
        },
      );
      expect(resolveResB.status).toBe(200);
      const { workspace: wsB } = await resolveResB.json();
      expect(wsB).not.toBeNull();
      expect(wsB.id).toBeDefined();

      // Workspace IDs must be different
      expect(wsA.id).not.toBe(wsB.id);

      // User A lists workspaces: must see wsA but NOT wsB
      const listA = await fetch(`${mainFixture.url}/v1/workspaces`, {
        headers: { Authorization: `Bearer ${tokenA}` },
      });
      expect(listA.status).toBe(200);
      const listAData = await listA.json();
      const idsA = listAData.items.map((w: { id: string }) => w.id);
      expect(idsA).toContain(wsA.id);
      expect(idsA).not.toContain(wsB.id);

      // User B lists workspaces: must see wsB but NOT wsA
      const listB = await fetch(`${mainFixture.url}/v1/workspaces`, {
        headers: { Authorization: `Bearer ${tokenB}` },
      });
      expect(listB.status).toBe(200);
      const listBData = await listB.json();
      const idsB = listBData.items.map((w: { id: string }) => w.id);
      expect(idsB).toContain(wsB.id);
      expect(idsB).not.toContain(wsA.id);

      // Cross-account access: User A tries to access User B's workspace -> 403 Forbidden
      const crossWsGet = await fetch(
        `${mainFixture.url}/v1/workspaces/${wsB.id}`,
        {
          headers: { Authorization: `Bearer ${tokenA}` },
        },
      );
      expect(crossWsGet.status).toBe(403);
      const crossWsData = await crossWsGet.json();
      expect(crossWsData.error?.code).toBe("WORKSPACE_ACCESS_DENIED");

      // Cross-account access: User A tries to read User B's documents -> 403 Forbidden
      const crossDocsGet = await fetch(
        `${mainFixture.url}/v1/workspaces/${wsB.id}/documents`,
        {
          headers: { Authorization: `Bearer ${tokenA}` },
        },
      );
      expect(crossDocsGet.status).toBe(403);
      const crossDocsData = await crossDocsGet.json();
      expect(crossDocsData.error?.code).toBe("WORKSPACE_ACCESS_DENIED");
    });

    it("rejects spliced workspace and conversation IDs with 404 and preserves target data", async () => {
      // 1. Account A
      const signupA = await fetch(`${mainFixture.url}/auth/v1/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "splicerA@example.test",
          password: "Password123!",
        }),
      });
      const { access_token: tokenA } = await signupA.json();
      const resA = await fetch(`${mainFixture.url}/v1/workspaces/resolve`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${tokenA}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });
      const { workspace: wsA } = await resA.json();

      // 2. Account B
      const signupB = await fetch(`${mainFixture.url}/auth/v1/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "targetB@example.test",
          password: "Password123!",
        }),
      });
      const { access_token: tokenB } = await signupB.json();
      const resB = await fetch(`${mainFixture.url}/v1/workspaces/resolve`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${tokenB}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });
      const { workspace: wsB } = await resB.json();

      // User B creates a legitimate conversation in wsB
      const createConvB = await fetch(
        `${mainFixture.url}/v1/workspaces/${wsB.id}/conversations`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${tokenB}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}),
        },
      );
      expect(createConvB.status).toBe(201);
      const convB = await createConvB.json();

      // User B adds a legitimate turn in convB
      const createTurnB = await fetch(
        `${mainFixture.url}/v1/workspaces/${wsB.id}/conversations/${convB.id}/turns`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${tokenB}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question: "Legitimate question from User B",
          }),
        },
      );
      expect(createTurnB.status).toBe(201);
      const turnB = await createTurnB.json();

      // --- Splicing Attacks by User A using wsA and convB ---

      // Attack 1: User A GETs single conversation using wsA with convB ID -> 404
      const spliceConvGet = await fetch(
        `${mainFixture.url}/v1/workspaces/${wsA.id}/conversations/${convB.id}`,
        {
          headers: { Authorization: `Bearer ${tokenA}` },
        },
      );
      expect(spliceConvGet.status).toBe(404);
      const spliceConvBody = await spliceConvGet.json();
      expect(spliceConvBody.error?.code).toBe("CONVERSATION_NOT_FOUND");

      // Attack 2: User A GETs turns list using wsA with convB ID -> 404
      const spliceTurnsGet = await fetch(
        `${mainFixture.url}/v1/workspaces/${wsA.id}/conversations/${convB.id}/turns`,
        {
          headers: { Authorization: `Bearer ${tokenA}` },
        },
      );
      expect(spliceTurnsGet.status).toBe(404);
      const spliceTurnsBody = await spliceTurnsGet.json();
      expect(spliceTurnsBody.error?.code).toBe("CONVERSATION_NOT_FOUND");

      // Attack 3: User A GETs single turn detail using wsA, convB ID, and turnB ID -> 404
      const spliceTurnDetail = await fetch(
        `${mainFixture.url}/v1/workspaces/${wsA.id}/conversations/${convB.id}/turns/${turnB.id}`,
        {
          headers: { Authorization: `Bearer ${tokenA}` },
        },
      );
      expect(spliceTurnDetail.status).toBe(404);
      const spliceTurnDetailBody = await spliceTurnDetail.json();
      expect(spliceTurnDetailBody.error?.code).toBe("CONVERSATION_NOT_FOUND");

      // Attack 4: User A attempts to inject a turn via POST using wsA with convB ID -> 404
      const spliceTurnPost = await fetch(
        `${mainFixture.url}/v1/workspaces/${wsA.id}/conversations/${convB.id}/turns`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${tokenA}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ question: "Malicious injection by User A" }),
        },
      );
      expect(spliceTurnPost.status).toBe(404);
      const spliceTurnPostBody = await spliceTurnPost.json();
      expect(spliceTurnPostBody.error?.code).toBe("CONVERSATION_NOT_FOUND");

      // --- Verify User B's data is completely preserved ---
      const verifyTurnsB = await fetch(
        `${mainFixture.url}/v1/workspaces/${wsB.id}/conversations/${convB.id}/turns`,
        {
          headers: { Authorization: `Bearer ${tokenB}` },
        },
      );
      expect(verifyTurnsB.status).toBe(200);
      const turnsDataB = await verifyTurnsB.json();
      // Must contain exactly 1 turn (turnB)
      expect(turnsDataB.items).toHaveLength(1);
      expect(turnsDataB.items[0].id).toBe(turnB.id);
      expect(turnsDataB.items[0].question).toBe(
        "Legitimate question from User B",
      );

      // Verify conversation B title was not altered
      const verifyConvB = await fetch(
        `${mainFixture.url}/v1/workspaces/${wsB.id}/conversations/${convB.id}`,
        {
          headers: { Authorization: `Bearer ${tokenB}` },
        },
      );
      expect(verifyConvB.status).toBe(200);
      const convDataB = await verifyConvB.json();
      expect(convDataB.title).toBe("Legitimate question from User B");
    });
  });
});
