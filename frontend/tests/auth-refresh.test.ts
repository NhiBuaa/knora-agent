// @vitest-environment node
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { createLocalJWKSet, exportJWK, generateKeyPair, SignJWT } from "jose";

const state = vi.hoisted(() => ({
  cookie: "",
  set: vi.fn(),
  keys: undefined as any,
}));
vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: () => ({ value: state.cookie }),
    set: state.set,
  }),
}));
vi.mock("jose", async (original) => {
  const jose = await original<typeof import("jose")>();
  return {
    ...jose,
    createRemoteJWKSet: () => jose.createLocalJWKSet(state.keys),
  };
});
import { decodeSession, encodeSession, getSession } from "@/lib/auth/session";
import { POST } from "@/app/api/[...path]/route";
import { POST as logout } from "@/app/api/auth/logout/route";
import { NextRequest } from "next/server";
import { middleware } from "@/middleware";
import { renewSession } from "@/lib/auth/session-refresh";

let privateKey: any;
const issuer = "https://identity.test/realms/knora";
beforeAll(async () => {
  const keys = await generateKeyPair("RS256");
  privateKey = keys.privateKey;
  state.keys = {
    keys: [{ ...(await exportJWK(keys.publicKey)), kid: "test", alg: "RS256" }],
  };
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  state.set.mockClear();
});

async function expiredCookie(refreshToken = crypto.randomUUID()) {
  vi.stubEnv("KEYCLOAK_TOKEN_URL", `${issuer}/protocol/openid-connect/token`);
  vi.stubEnv("KEYCLOAK_JWKS_URL", `${issuer}/protocol/openid-connect/certs`);
  vi.stubEnv("KEYCLOAK_ISSUER", issuer);
  vi.stubEnv("KEYCLOAK_CLIENT_ID", "knora-web");
  state.cookie = await encodeSession({
    issuer,
    subject: "alice",
    accessToken: "old-access",
    refreshToken,
    refreshExpiresAt: Math.floor(Date.now() / 1000) + 600,
    expiresAt: Math.floor(Date.now() / 1000) - 1,
    workspaceIds: [],
    capabilities: [],
  });
  return refreshToken;
}
async function tokens(subject = "alice") {
  return {
    access_token: "new-access",
    refresh_token: "rotated-refresh",
    expires_in: 300,
    refresh_expires_in: 600,
    id_token: await new SignJWT({ capabilities: ["operator:read"] })
      .setProtectedHeader({ alg: "RS256", kid: "test" })
      .setIssuer(issuer)
      .setAudience("knora-web")
      .setSubject(subject)
      .setExpirationTime("5m")
      .sign(privateKey),
  };
}

describe("server session renewal", () => {
  it("does not forward an access token that expires while refresh is failing", async () => {
    await expiredCookie();
    const initial = Date.now();
    state.cookie = await encodeSession({
      ...(await decodeSession(state.cookie))!,
      expiresAt: Math.floor(initial / 1000) + 5,
    });
    let fail: (reason: Error) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((_resolve, reject) => {
            fail = reject;
          }),
      ),
    );
    const renewing = getSession(true);
    await vi.waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1));
    vi.setSystemTime(initial + 11000);
    fail(new Error("timed out"));
    await expect(renewing).rejects.toThrow("SESSION_REFRESH_UNAVAILABLE");
  });
  it("shares refresh coordination across separate middleware and route module loads", async () => {
    await expiredCookie();
    const session = (await decodeSession(state.cookie))!;
    vi.resetModules();
    const separatelyLoaded = await import("@/lib/auth/session-refresh");
    const tokenResponse = JSON.stringify(await tokens());
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(tokenResponse)),
    );
    const results = await Promise.all([
      renewSession(session),
      separatelyLoaded.renewSession(session),
    ]);
    expect(results.map((value) => value?.accessToken)).toEqual([
      "new-access",
      "new-access",
    ]);
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
  });
  it("honors logout even when proactive refresh fails while the old access token is still valid", async () => {
    await expiredCookie();
    const previous = (await decodeSession(state.cookie))!;
    state.cookie = await encodeSession({
      ...previous,
      expiresAt: Math.floor(Date.now() / 1000) + 10,
    });
    let fail: (reason: Error) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((_resolve, reject) => {
            fail = reject;
          }),
      ),
    );
    const renewing = getSession(true);
    await vi.waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1));
    await logout(
      new Request("http://app.test/api/auth/logout", {
        method: "POST",
        headers: {
          origin: "http://app.test",
          cookie: `knora_session=${state.cookie}`,
        },
      }),
    );
    fail(new Error("temporary failure"));
    expect(await renewing).toBeNull();
  });
  it("persists rotation before rendering a protected page and supplies the new cookie to SSR", async () => {
    await expiredCookie();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(await tokens()))),
    );
    const response = await middleware(
      new NextRequest("http://app.test/workspaces", {
        headers: { cookie: `knora_session=${state.cookie}` },
      }),
    );
    const saved = response.cookies.get("knora_session")?.value;
    expect(saved).toBeTruthy();
    expect(await decodeSession(saved)).toMatchObject({
      accessToken: "new-access",
      refreshToken: "rotated-refresh",
    });
    expect(response.headers.get("x-middleware-request-cookie")).toContain(
      saved,
    );
  });
  it("does not resurrect a session when logout wins a concurrent refresh", async () => {
    await expiredCookie();
    let finish: (response: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      ),
    );
    const renewing = getSession(true);
    await vi.waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1));
    await logout(
      new Request("http://app.test/api/auth/logout", {
        method: "POST",
        headers: {
          origin: "http://app.test",
          cookie: `knora_session=${state.cookie}`,
        },
      }),
    );
    finish(new Response(JSON.stringify(await tokens())));
    expect(await renewing).toBeNull();
  });
  it("refreshes before forwarding a Turn exactly once with its unchanged draft and key", async () => {
    await expiredCookie();
    const refreshed = await tokens();
    const fetchMock = vi.fn(async (url: string, init: RequestInit) =>
      url === `${issuer}/protocol/openid-connect/token`
        ? new Response(JSON.stringify(refreshed))
        : new Response(JSON.stringify({ id: "turn-one" }), { status: 202 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const request = new Request("http://app.test/api/v1/turns", {
      method: "POST",
      headers: { cookie: "private-cookie", "Idempotency-Key": "stable-key" },
      body: JSON.stringify({ question: "Keep my draft" }),
    });
    const response = await POST(request, {
      params: Promise.resolve({ path: ["v1", "turns"] }),
    });
    expect(response.status).toBe(202);
    const forwards = fetchMock.mock.calls.filter(
      (call) => call[0] !== `${issuer}/protocol/openid-connect/token`,
    );
    expect(forwards).toHaveLength(1);
    expect(new Headers(forwards[0][1].headers).get("authorization")).toBe(
      "Bearer new-access",
    );
    expect(new Headers(forwards[0][1].headers).get("cookie")).toBeNull();
    expect(new Headers(forwards[0][1].headers).get("Idempotency-Key")).toBe(
      "stable-key",
    );
    expect(new TextDecoder().decode(forwards[0][1].body as ArrayBuffer)).toBe(
      '{"question":"Keep my draft"}',
    );
  });
  it("returns a retryable503 without forwarding when refresh is temporarily unavailable", async () => {
    await expiredCookie();
    const fetchMock = vi.fn().mockRejectedValue(new Error("network down"));
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      new Request("http://app.test/api/v1/turns", {
        method: "POST",
        body: "draft",
      }),
      { params: Promise.resolve({ path: ["v1", "turns"] }) },
    );
    expect(response.status).toBe(503);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("keeps an expired access token recoverable in an encrypted session cookie", async () => {
    await expiredCookie();
    expect(state.cookie.split(".")).toHaveLength(5);
    expect(await decodeSession(state.cookie)).toMatchObject({
      subject: "alice",
      accessToken: "old-access",
    });
  });
  it("renews concurrent requests once and persists the rotated token without exposing it", async () => {
    const refreshToken = await expiredCookie();
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(await tokens())));
    vi.stubGlobal("fetch", fetchMock);
    const sessions = await Promise.all([getSession(true), getSession(true)]);
    expect(sessions.map((s) => s?.accessToken)).toEqual([
      "new-access",
      "new-access",
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(
      new URLSearchParams(fetchMock.mock.calls[0][1].body).get("refresh_token"),
    ).toBe(refreshToken);
    expect(
      new URLSearchParams(fetchMock.mock.calls[0][1].body).get("grant_type"),
    ).toBe("refresh_token");
    expect(state.set).toHaveBeenCalled();
    const saved = state.set.mock.calls[0];
    expect(saved[2]).toMatchObject({ httpOnly: true, sameSite: "lax" });
    expect(await decodeSession(saved[1])).toMatchObject({
      refreshToken: "rotated-refresh",
      accessToken: "new-access",
    });
  });
  it("requires login only when refresh is rejected, not on a network outage", async () => {
    await expiredCookie();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: "invalid_grant" }), {
          status: 400,
        }),
      ),
    );
    expect(await getSession(true)).toBeNull();
    await expiredCookie();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network unavailable")),
    );
    await expect(getSession(true)).rejects.toThrow(
      "SESSION_REFRESH_UNAVAILABLE",
    );
  });
  it("rejects a refreshed identity that differs from the login", async () => {
    await expiredCookie();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(new Response(JSON.stringify(await tokens("bob")))),
    );
    await expect(getSession(true)).rejects.toThrow(
      "SESSION_REFRESH_UNAVAILABLE",
    );
    expect(state.set).not.toHaveBeenCalled();
  });
  it("never refreshes a tampered cookie or an expired refresh session", async () => {
    await expiredCookie();
    state.cookie = `${state.cookie.slice(0, -8)}xxxxxxxx`;
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect(await getSession(true)).toBeNull();
    state.cookie = await encodeSession({
      subject: "alice",
      accessToken: "old",
      refreshToken: "expired",
      expiresAt: 1,
      refreshExpiresAt: 2,
      workspaceIds: [],
      capabilities: [],
    });
    expect(await getSession(true)).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
