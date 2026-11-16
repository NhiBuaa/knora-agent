// @vitest-environment node

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { exportJWK, generateKeyPair, SignJWT } from "jose";
import {
  decodeRecoverySession,
  encodeRecoverySession,
  requestRecovery,
  verifyRecovery,
  updateRecoveredPassword,
} from "@/lib/auth/supabase-recovery";
import { _resetJwksCache } from "@/lib/auth/supabase";
import { decodeSession } from "@/lib/auth/session";
import type { KnoraSession } from "@/lib/auth/session";

describe("Supabase Recovery Operations", () => {
  const issuer = "https://auth.example.test/auth/v1";
  const subject = "ca0af038-9a87-4e0c-9dd3-2f3d47fc6bf1";
  const providerSessionId = "06f727d9-702c-426b-aabb-89c823f7d01c";
  let privateKey: any;
  let jwk: any;

  beforeEach(async () => {
    _resetJwksCache();
    const pair = await generateKeyPair("ES256");
    privateKey = pair.privateKey;
    jwk = {
      ...(await exportJWK(pair.publicKey)),
      kid: "recovery-key",
      alg: "ES256",
    };

    vi.stubEnv("KNORA_AUTH_PROVIDER", "supabase");
    vi.stubEnv("SUPABASE_URL", "https://auth.example.test");
    vi.stubEnv("SUPABASE_PUBLISHABLE_KEY", "test-key");
    vi.stubEnv("SUPABASE_JWT_ALGORITHM", "ES256");
    vi.stubEnv("KNORA_API_URL", "https://api.example.test");
  });

  afterEach(() => {
    _resetJwksCache();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  async function mockAccessToken() {
    const now = Math.floor(Date.now() / 1000);
    return new SignJWT({
      role: "authenticated",
      is_anonymous: false,
      session_id: providerSessionId,
    })
      .setProtectedHeader({ alg: "ES256", kid: "recovery-key" })
      .setIssuer(issuer)
      .setAudience("authenticated")
      .setSubject(subject)
      .setIssuedAt(now)
      .setExpirationTime(now + 300)
      .sign(privateKey);
  }

  it("requestRecovery returns uniform success for any email", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(requestRecovery("user@example.test")).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, opts] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("https://auth.example.test/auth/v1/recover");
    expect(JSON.parse(opts.body)).toEqual({ email: "user@example.test" });
  });

  it("requestRecovery throws on rate limit (429)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 429 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(requestRecovery("user@example.test")).rejects.toThrow(
      "RATE_LIMIT_EXCEEDED",
    );
  });

  it("verifyRecovery verifies code and caps session at 5 minutes", async () => {
    const token = await mockAccessToken();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/.well-known/jwks.json")) {
        return Response.json({ keys: [jwk] });
      }
      if (url.endsWith("/auth/v1/verify")) {
        return Response.json({
          access_token: token,
          refresh_token: "rec-refresh",
          expires_in: 300,
        });
      }
      if (url.endsWith("/v1/auth/session")) {
        return Response.json({
          issuer,
          subject,
          session_id: providerSessionId,
          capabilities: [],
        });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const session = await verifyRecovery("user@example.test", "123456");
    expect(session.subject).toBe(subject);
    expect(session.providerSessionId).toBe(providerSessionId);
    expect(session.provider).toBe("supabase");
    expect(session.sessionExpiresAt).toBeLessThanOrEqual(
      Math.floor(Date.now() / 1000) + 300,
    );
  });

  it("verifyRecovery rejects invalid or expired code", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error_description: "Token has expired" }), {
        status: 400,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(verifyRecovery("user@example.test", "000000")).rejects.toThrow(
      "Token has expired",
    );
  });

  it("encodeRecoverySession and decodeRecoverySession preserve recovery state", async () => {
    const session: KnoraSession = {
      provider: "supabase",
      providerSessionId,
      issuer,
      subject,
      accessToken: "recovery-token",
      workspaceIds: [],
      capabilities: [],
      expiresAt: Math.floor(Date.now() / 1000) + 300,
      sessionExpiresAt: Math.floor(Date.now() / 1000) + 300,
    };

    const encoded = await encodeRecoverySession(session, "user@example.test");
    const decoded = await decodeRecoverySession(encoded);
    expect(decoded).not.toBeNull();
    expect(decoded?.email).toBe("user@example.test");
    expect(decoded?.session.subject).toBe(subject);

    // Normal session decoder MUST reject recovery token
    const normalDecoded = await decodeSession(encoded);
    expect(normalDecoded).toBeNull();
  });

  it("updateRecoveredPassword verifies backend session, updates password and revokes globally", async () => {
    const token = await mockAccessToken();
    const calls: { url: string; method: string }[] = [];

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method || "GET";
        calls.push({ url, method });

        if (url.endsWith("/v1/auth/session")) {
          return Response.json({
            issuer,
            subject,
            session_id: providerSessionId,
            capabilities: [],
          });
        }
        if (url.endsWith("/auth/v1/user") && method === "PUT") {
          return Response.json({ id: subject });
        }
        if (url.endsWith("/auth/v1/logout?scope=global") && method === "POST") {
          return new Response(null, { status: 204 });
        }
        throw new Error(`Unexpected call: ${url} ${method}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    const recoverySession: KnoraSession = {
      provider: "supabase",
      providerSessionId,
      issuer,
      subject,
      accessToken: token,
      workspaceIds: [],
      capabilities: [],
      expiresAt: Math.floor(Date.now() / 1000) + 300,
      sessionExpiresAt: Math.floor(Date.now() / 1000) + 300,
    };

    await updateRecoveredPassword(recoverySession, "NewSecret123!");

    expect(calls.some((c) => c.url.endsWith("/v1/auth/session"))).toBe(true);
    expect(
      calls.some((c) => c.url.endsWith("/auth/v1/user") && c.method === "PUT"),
    ).toBe(true);
    expect(
      calls.some(
        (c) =>
          c.url.endsWith("/auth/v1/logout?scope=global") && c.method === "POST",
      ),
    ).toBe(true);
  });

  it("updateRecoveredPassword fails if backend session was already revoked", async () => {
    const token = await mockAccessToken();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/v1/auth/session")) {
        return new Response(JSON.stringify({ error: "Session revoked" }), {
          status: 401,
        });
      }
      throw new Error(`Should not reach here: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const recoverySession: KnoraSession = {
      provider: "supabase",
      providerSessionId,
      issuer,
      subject,
      accessToken: token,
      workspaceIds: [],
      capabilities: [],
      expiresAt: Math.floor(Date.now() / 1000) + 300,
      sessionExpiresAt: Math.floor(Date.now() / 1000) + 300,
    };

    await expect(
      updateRecoveredPassword(recoverySession, "NewSecret123!"),
    ).rejects.toThrow();
  });

  it("updateRecoveredPassword does not swallow revocation failure when provider returns HTTP error", async () => {
    const token = await mockAccessToken();
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method || "GET";
        if (url.endsWith("/v1/auth/session")) {
          return Response.json({
            issuer,
            subject,
            session_id: providerSessionId,
            capabilities: [],
          });
        }
        if (url.endsWith("/auth/v1/user") && method === "PUT") {
          return Response.json({ id: subject });
        }
        if (url.endsWith("/auth/v1/logout?scope=global") && method === "POST") {
          return new Response(
            JSON.stringify({ error: "Service unavailable" }),
            {
              status: 503,
            },
          );
        }
        throw new Error(`Unexpected call: ${url} ${method}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    const recoverySession: KnoraSession = {
      provider: "supabase",
      providerSessionId,
      issuer,
      subject,
      accessToken: token,
      workspaceIds: [],
      capabilities: [],
      expiresAt: Math.floor(Date.now() / 1000) + 300,
      sessionExpiresAt: Math.floor(Date.now() / 1000) + 300,
    };

    let caughtError: any = null;
    try {
      await updateRecoveredPassword(recoverySession, "NewSecret123!");
    } catch (err) {
      caughtError = err;
    }

    expect(caughtError).not.toBeNull();
    expect(caughtError.status).toBe(503);
    expect(caughtError.message).toContain("revoke active sessions");
  });

  it("updateRecoveredPassword does not swallow revocation failure on network timeout", async () => {
    const token = await mockAccessToken();
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method || "GET";
        if (url.endsWith("/v1/auth/session")) {
          return Response.json({
            issuer,
            subject,
            session_id: providerSessionId,
            capabilities: [],
          });
        }
        if (url.endsWith("/auth/v1/user") && method === "PUT") {
          return Response.json({ id: subject });
        }
        if (url.endsWith("/auth/v1/logout?scope=global") && method === "POST") {
          throw new Error("Network timeout during revocation");
        }
        throw new Error(`Unexpected call: ${url} ${method}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    const recoverySession: KnoraSession = {
      provider: "supabase",
      providerSessionId,
      issuer,
      subject,
      accessToken: token,
      workspaceIds: [],
      capabilities: [],
      expiresAt: Math.floor(Date.now() / 1000) + 300,
      sessionExpiresAt: Math.floor(Date.now() / 1000) + 300,
    };

    let caughtError: any = null;
    try {
      await updateRecoveredPassword(recoverySession, "NewSecret123!");
    } catch (err) {
      caughtError = err;
    }

    expect(caughtError).not.toBeNull();
    expect(caughtError.status).toBe(503);
    expect(caughtError.message).toContain("revoke active sessions");
  });
});
