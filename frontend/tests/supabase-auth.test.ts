// @vitest-environment node
import { generateKeyPair, exportJWK, SignJWT } from "jose";
import { expect, it, vi, afterEach } from "vitest";
import {
  refreshSupabaseSession,
  signInWithPassword,
  registerWithPassword,
  signOutSupabaseSession,
  _resetJwksCache,
} from "@/lib/auth/supabase";

afterEach(() => {
  _resetJwksCache();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
import type { KnoraSession } from "@/lib/auth/session";

async function validSupabaseRefreshFixture() {
  const now = Math.floor(Date.now() / 1000);
  const issuer = "https://auth.example.test/auth/v1";
  const subject = "ca0af038-9a87-4e0c-9dd3-2f3d47fc6bf1";
  const providerSessionId = "06f727d9-702c-426b-aabb-89c823f7d01c";
  const { publicKey, privateKey } = await generateKeyPair("ES256");
  const jwk = {
    ...(await exportJWK(publicKey)),
    kid: "auth-test",
    alg: "ES256",
  };
  const accessToken = await new SignJWT({
    role: "authenticated",
    is_anonymous: false,
    session_id: providerSessionId,
  })
    .setProtectedHeader({ alg: "ES256", kid: "auth-test" })
    .setIssuer(issuer)
    .setAudience("authenticated")
    .setSubject(subject)
    .setIssuedAt(now)
    .setExpirationTime(now + 300)
    .sign(privateKey);
  const previous: KnoraSession = {
    provider: "supabase",
    providerSessionId,
    issuer,
    subject,
    accessToken: "expired-access-token",
    refreshToken: "old-refresh-token",
    expiresAt: now - 1,
    sessionExpiresAt: now + 8 * 3600,
    sessionId: "application-session",
    capabilities: [],
    workspaceIds: [],
  };
  const tokens = {
    access_token: accessToken,
    refresh_token: "new-refresh-token",
    expires_in: 300,
  };
  vi.stubEnv("KNORA_AUTH_PROVIDER", "supabase");
  vi.stubEnv("SUPABASE_URL", "https://auth.example.test");
  vi.stubEnv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key");
  vi.stubEnv("SUPABASE_JWT_ALGORITHM", "ES256");
  vi.stubEnv("KNORA_API_URL", "https://api.example.test");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      if (url.endsWith("/.well-known/jwks.json"))
        return Response.json({ keys: [jwk] });
      if (url.endsWith("/token?grant_type=refresh_token"))
        return Response.json(tokens);
      if (url.endsWith("/v1/auth/session"))
        return Response.json({
          issuer,
          subject,
          session_id: providerSessionId,
          capabilities: ["documents:read", "documents:write", "questions:ask"],
        });
      throw new Error(`Unexpected HTTP call in refresh test: ${url}`);
    }),
  );
  return {
    previous,
    tokens,
    publicKey,
    privateKey,
    jwk,
    issuer,
    subject,
    providerSessionId,
  };
}

it("accepts Supabase refresh without Keycloak-only fields", async () => {
  try {
    const fixture = await validSupabaseRefreshFixture();
    const renewed = await refreshSupabaseSession(fixture.previous);
    expect(renewed?.subject).toBe(fixture.previous.subject);
    expect(renewed?.accessToken).toBe(fixture.tokens.access_token);
    expect(renewed?.sessionExpiresAt).toBe(fixture.previous.sessionExpiresAt);
    expect(renewed?.capabilities).toEqual([
      "documents:read",
      "documents:write",
      "questions:ask",
    ]);
  } finally {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  }
});

it("rejects refresh if replacement token changes subject", async () => {
  try {
    const fixture = await validSupabaseRefreshFixture();
    const now = Math.floor(Date.now() / 1000);
    // Token with altered subject
    const rogueToken = await new SignJWT({
      role: "authenticated",
      is_anonymous: false,
      session_id: fixture.providerSessionId,
    })
      .setProtectedHeader({ alg: "ES256", kid: "auth-test" })
      .setIssuer(fixture.issuer)
      .setAudience("authenticated")
      .setSubject("different-user-subject")
      .setIssuedAt(now)
      .setExpirationTime(now + 300)
      .sign(fixture.privateKey);

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        if (url.endsWith("/.well-known/jwks.json"))
          return Response.json({ keys: [fixture.jwk] });
        if (url.endsWith("/token?grant_type=refresh_token")) {
          return Response.json({
            access_token: rogueToken,
            refresh_token: "new-refresh-token",
            expires_in: 300,
          });
        }
        if (url.endsWith("/v1/auth/session")) {
          return Response.json({
            issuer: fixture.issuer,
            subject: "different-user-subject",
            session_id: fixture.providerSessionId,
            capabilities: [],
          });
        }
        throw new Error(`Unexpected HTTP call: ${url}`);
      }),
    );

    const renewed = await refreshSupabaseSession(fixture.previous);
    expect(renewed).toBeNull();
  } finally {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  }
});

it("rejects refresh if replacement token changes session_id", async () => {
  try {
    const fixture = await validSupabaseRefreshFixture();
    const now = Math.floor(Date.now() / 1000);
    // Token with altered session_id
    const rogueToken = await new SignJWT({
      role: "authenticated",
      is_anonymous: false,
      session_id: "changed-session-id-1234",
    })
      .setProtectedHeader({ alg: "ES256", kid: "auth-test" })
      .setIssuer(fixture.issuer)
      .setAudience("authenticated")
      .setSubject(fixture.subject)
      .setIssuedAt(now)
      .setExpirationTime(now + 300)
      .sign(fixture.privateKey);

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        if (url.endsWith("/.well-known/jwks.json"))
          return Response.json({ keys: [fixture.jwk] });
        if (url.endsWith("/token?grant_type=refresh_token")) {
          return Response.json({
            access_token: rogueToken,
            refresh_token: "new-refresh-token",
            expires_in: 300,
          });
        }
        if (url.endsWith("/v1/auth/session")) {
          return Response.json({
            issuer: fixture.issuer,
            subject: fixture.subject,
            session_id: "changed-session-id-1234",
            capabilities: [],
          });
        }
        throw new Error(`Unexpected HTTP call: ${url}`);
      }),
    );

    const renewed = await refreshSupabaseSession(fixture.previous);
    expect(renewed).toBeNull();
  } finally {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  }
});

it("signs in with password and validates session", async () => {
  try {
    const fixture = await validSupabaseRefreshFixture();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        if (url.endsWith("/.well-known/jwks.json"))
          return Response.json({ keys: [fixture.jwk] });
        if (url.endsWith("/token?grant_type=password")) {
          return Response.json({
            access_token: fixture.tokens.access_token,
            refresh_token: fixture.tokens.refresh_token,
            expires_in: 300,
            user: { id: fixture.subject },
          });
        }
        if (url.endsWith("/v1/auth/session")) {
          return Response.json({
            issuer: fixture.issuer,
            subject: fixture.subject,
            session_id: fixture.providerSessionId,
            capabilities: [
              "documents:read",
              "documents:write",
              "questions:ask",
            ],
          });
        }
        throw new Error(`Unexpected HTTP call: ${url}`);
      }),
    );

    const session = await signInWithPassword(
      "test@example.com",
      "valid-password",
    );
    expect(session.subject).toBe(fixture.subject);
    expect(session.provider).toBe("supabase");
    expect(session.providerSessionId).toBe(fixture.providerSessionId);
    expect(session.capabilities).toEqual([
      "documents:read",
      "documents:write",
      "questions:ask",
    ]);
  } finally {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  }
});

it("signs out supabase session with scope local", async () => {
  try {
    const fixture = await validSupabaseRefreshFixture();
    let logoutCalled = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        if (url.endsWith("/logout?scope=local")) {
          logoutCalled = true;
          return new Response(null, { status: 204 });
        }
        throw new Error(`Unexpected HTTP call: ${url}`);
      }),
    );

    await signOutSupabaseSession(fixture.previous, "local");
    expect(logoutCalled).toBe(true);
  } finally {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  }
});
