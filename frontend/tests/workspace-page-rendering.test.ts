// @vitest-environment node

import { spawn, type ChildProcess } from "node:child_process";
import path from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { encodeSession, SESSION_COOKIE_NAME } from "@/lib/auth/session";

const port = 34_000 + (process.pid % 1_000);
const origin = `http://127.0.0.1:${port}`;
const sessionSecret = "workspace-page-request-test-secret";
let server: ChildProcess | undefined;
let previousSessionSecret: string | undefined;

function runNext(args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const nextCli = path.join(process.cwd(), "node_modules", "next", "dist", "bin", "next");
    const nextProcess = spawn(process.execPath, [nextCli, ...args], {
      cwd: process.cwd(),
      env: { ...globalThis.process.env, SESSION_SECRET: sessionSecret },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let output = "";
    nextProcess.stdout?.on("data", (chunk) => { output += chunk; });
    nextProcess.stderr?.on("data", (chunk) => { output += chunk; });
    nextProcess.on("error", reject);
    nextProcess.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`next ${args.join(" ")} exited with ${code}: ${output}`));
    });
  });
}

async function waitForServer(): Promise<void> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const response = await fetch(origin, { signal: AbortSignal.timeout(250) });
      if (response.ok) return;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw lastError ?? new Error("Next server did not become ready");
}

beforeAll(async () => {
  previousSessionSecret = process.env.SESSION_SECRET;
  process.env.SESSION_SECRET = sessionSecret;
  await runNext(["build"]);
  const nextCli = path.join(process.cwd(), "node_modules", "next", "dist", "bin", "next");
  server = spawn(process.execPath, [nextCli, "start", "--port", String(port)], {
    cwd: process.cwd(),
    env: { ...process.env, SESSION_SECRET: sessionSecret },
    stdio: "ignore",
  });
  await waitForServer();
}, 30_000);

afterAll(() => {
  server?.kill();
  if (previousSessionSecret === undefined) delete process.env.SESSION_SECRET;
  else process.env.SESSION_SECRET = previousSessionSecret;
});

describe("workspace page rendering", () => {
  it("renders each request from its current session cookie", async () => {
    const unavailable = await fetch(`${origin}/app`);

    expect(unavailable.status).toBe(200);
    await expect(unavailable.text()).resolves.toContain("No workspace is available for this session.");

    const session = await encodeSession({
      subject: "user-1",
      accessToken: "access-token",
      workspaceIds: ["workspace-after-callback"],
      capabilities: [],
      expiresAt: 1_800_000_000,
    });

    const response = await fetch(`${origin}/app`, {
      headers: { cookie: `${SESSION_COOKIE_NAME}=${session}` },
    });

    expect(response.status).toBe(200);
    const html = (await response.text()).replaceAll("<!-- -->", "");
    expect(html).toContain("Selected workspace: workspace-after-callback");
  });
});
