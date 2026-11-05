// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { SignJWT } from "jose";
import { GET as login } from "@/app/api/auth/login/route";
import {
  createAuthorizationTransaction,
  decodeAuthorizationTransaction,
  encodeAuthorizationTransaction,
  encodeSession,
  decodeSession,
  sessionCookie,
  clearSessionCookie,
  clearLegacySessionCookie,
  SESSION_COOKIE_NAME,
  LEGACY_SESSION_COOKIE_NAME,
  KnoraSession,
} from "@/lib/auth/session";

describe("OIDC authorization transaction", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
  });

  it("sends an unconfigured browser to the fixed public unavailable page", async () => {
    vi.stubEnv("KEYCLOAK_AUTHORIZATION_URL", "");
    const response = await login(
      new Request("https://app.test/api/auth/login?redirect=https://evil.test"),
    );
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://app.test/auth/unavailable",
    );
  });

  it("accepts only prompt=login and ignores arbitrary redirect inputs", async () => {
    vi.stubEnv("KEYCLOAK_AUTHORIZATION_URL", "https://id.test/auth");
    vi.stubEnv("KEYCLOAK_REDIRECT_URI", "https://app.test/api/auth/callback");
    for (const [prompt, expected] of [
      ["login", "login"],
      ["none", null],
      ["login consent", null],
      ["https://evil.test", null],
    ] as const) {
      const response = await login(
        new Request(
          `https://app.test/api/auth/login?prompt=${encodeURIComponent(prompt)}&redirect_uri=https://evil.test&returnTo=https://evil.test`,
        ),
      );
      const target = new URL(response.headers.get("location")!);
      expect(target.origin).toBe("https://id.test");
      expect(target.searchParams.get("prompt")).toBe(expected);
      expect(target.searchParams.get("redirect_uri")).toBe(
        "https://app.test/api/auth/callback",
      );
      expect(target.searchParams.has("returnTo")).toBe(false);
    }
  });

  it.each(["not-a-url", "javascript:alert(1)"])(
    "returns a safe unavailable page for invalid authorization configuration %s",
    async (authorize) => {
      vi.stubEnv("KEYCLOAK_AUTHORIZATION_URL", authorize);
      const response = await login(
        new Request("https://app.test/api/auth/login"),
      );
      expect(response.headers.get("location")).toBe(
        "https://app.test/auth/unavailable",
      );
      expect(response.cookies.get("knora_oidc_transaction")).toBeUndefined();
    },
  );

  it("starts a fresh signed state, nonce and PKCE transaction on each retry", async () => {
    vi.stubEnv("KEYCLOAK_AUTHORIZATION_URL", "https://id.test/auth");
    const attempts = [];
    for (let attempt = 0; attempt < 2; attempt++) {
      const response = await login(
        new Request("https://app.test/api/auth/login?prompt=login"),
      );
      const cookie = response.cookies.get("knora_oidc_transaction");
      const transaction = await decodeAuthorizationTransaction(cookie?.value);
      expect(transaction).not.toBeNull();
      const target = new URL(response.headers.get("location")!);
      expect(target.searchParams.get("state")).toBe(transaction!.state);
      expect(target.searchParams.get("nonce")).toBe(transaction!.nonce);
      expect(target.searchParams.get("code_challenge")).toBe(
        transaction!.codeChallenge,
      );
      expect(target.searchParams.get("code_challenge_method")).toBe("S256");
      expect(target.searchParams.has("code_verifier")).toBe(false);
      attempts.push(transaction!);
    }
    for (const key of [
      "state",
      "nonce",
      "codeVerifier",
      "codeChallenge",
    ] as const) {
      expect(attempts[0][key]).not.toBe(attempts[1][key]);
    }
  });

  it("keeps the validated issuer with the server-only session", async () => {
    const now = Math.floor(Date.now() / 1000);
    const encoded = await encodeSession({
      policyVersion: 1,
      rememberMe: false,
      sessionStartedAt: now,
      sessionExpiresAt: now + 28800,
      issuer: "https://id.example/realm",
      subject: "alice",
      accessToken: "private-token",
      refreshToken: "refresh-token",
      sessionId: "session-1",
      expiresAt: now + 300,
      refreshExpiresAt: now + 1800,
      workspaceIds: [],
      capabilities: [],
    });
    const decoded = await decodeSession(encoded);
    expect(decoded?.issuer).toBe("https://id.example/realm");
    expect(decoded?.accessToken).toBe("private-token");
    expect(decoded?.rememberMe).toBe(false);
    expect(decoded?.policyVersion).toBe(1);
  });

  it("creates a state, nonce, and PKCE verifier bound to one callback", async () => {
    const transaction = createAuthorizationTransaction(
      "https://app.test/callback",
    );

    expect(transaction.state).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(transaction.nonce).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(transaction.codeVerifier).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(transaction.codeChallenge).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(transaction.redirectUri).toBe("https://app.test/callback");
    expect(transaction.state).not.toBe(transaction.nonce);
  });

  it("rejects a tampered or expired callback transaction", async () => {
    const transaction = createAuthorizationTransaction(
      "https://app.test/callback",
    );
    const encoded = await encodeAuthorizationTransaction(transaction);
    await expect(
      decodeAuthorizationTransaction(encoded),
    ).resolves.toMatchObject(transaction);

    const [payload, signature] = encoded.split(".");
    const alphabet =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    const lastIndex = alphabet.indexOf(signature.at(-1) ?? "");
    const nonCanonicalAlias = alphabet[(lastIndex & 0b110000) | 1];
    const tampered = `${payload}.${signature.slice(0, -1)}${nonCanonicalAlias}`;
    await expect(decodeAuthorizationTransaction(tampered)).resolves.toBeNull();

    vi.setSystemTime((transaction.expiresAt + 1) * 1000);
    await expect(decodeAuthorizationTransaction(encoded)).resolves.toBeNull();

    await expect(decodeAuthorizationTransaction(undefined)).resolves.toBeNull();
  });
});

describe("session v2 cookie and encryption policy", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
  });

  function makeSession(rememberMe: boolean): KnoraSession {
    const now = Math.floor(Date.now() / 1000);
    const max = rememberMe ? 2_592_000 : 28_800;
    const idle = rememberMe ? 604_800 : 1_800;
    return {
      policyVersion: 1,
      rememberMe,
      sessionStartedAt: now,
      sessionExpiresAt: now + max,
      issuer: "https://id.example/realm",
      subject: "alice",
      accessToken: "secret-access",
      refreshToken: "secret-refresh",
      sessionId: "session-uuid-1",
      expiresAt: now + 300,
      refreshExpiresAt: now + idle,
      workspaceIds: ["ws-1"],
      capabilities: ["op:read"],
    };
  }

  it("sets normal session cookie without Max-Age or Expires", () => {
    const session = makeSession(false);
    const cookie = sessionCookie("mock-token", session);
    expect(cookie.name).toBe(SESSION_COOKIE_NAME);
    expect(cookie.name).toBe("knora_session_v2");
    expect(cookie.options.maxAge).toBeUndefined();
    expect(cookie.options.expires).toBeUndefined();
    expect(cookie.options.httpOnly).toBe(true);
    expect(cookie.options.sameSite).toBe("lax");
    expect(cookie.options.path).toBe("/");
  });

  it("sets remembered cookie with clamped maxAge", () => {
    const session = makeSession(true);
    const now = Math.floor(Date.now() / 1000);
    const cookie = sessionCookie("mock-token", session);
    expect(cookie.name).toBe("knora_session_v2");
    expect(typeof cookie.options.maxAge).toBe("number");
    expect(cookie.options.maxAge).toBeLessThanOrEqual(604_800);
    expect(cookie.options.maxAge).toBeGreaterThanOrEqual(604_790);
  });

  it("encodes session into 5-part JWE and never exposes token in plaintext", async () => {
    const session = makeSession(false);
    const encoded = await encodeSession(session);
    const parts = encoded.split(".");
    expect(parts).toHaveLength(5);
    expect(encoded).not.toContain("secret-access");
    expect(encoded).not.toContain("secret-refresh");
    expect(encoded).not.toContain("alice");

    // Cookie representation remains well under 4096 bytes
    const cookie = sessionCookie(encoded, session);
    const cookieHeader = `${cookie.name}=${cookie.value}; Path=/; HttpOnly; SameSite=Lax`;
    expect(Buffer.byteLength(cookieHeader, "utf8")).toBeLessThan(4096);
  });

  it("rejects legacy HS256 tokens and non-v2 JWE without policy", async () => {
    // HS256 JWT
    const secret = new TextEncoder().encode(
      "development-only-session-secret-change-me",
    );
    const legacyHS256 = await new SignJWT({
      sub: "alice",
      accessToken: "old",
      workspaceIds: [],
      capabilities: [],
    })
      .setProtectedHeader({ alg: "HS256" })
      .setExpirationTime("1h")
      .sign(secret);

    expect(await decodeSession(legacyHS256)).toBeNull();

    // JWE with invalid policy
    expect(await decodeSession("not.a.valid.jwe.token")).toBeNull();
  });

  it("rejects cookie when configured issuer mismatches token issuer", async () => {
    const session = makeSession(false);
    const encoded = await encodeSession(session);

    vi.stubEnv("KEYCLOAK_ISSUER", "https://different-issuer.example");
    expect(await decodeSession(encoded)).toBeNull();

    vi.stubEnv("KEYCLOAK_ISSUER", "https://id.example/realm");
    expect(await decodeSession(encoded)).not.toBeNull();
  });

  it("clearSessionCookie and clearLegacySessionCookie produce maxAge: 0", () => {
    const v2Clear = clearSessionCookie();
    expect(v2Clear.name).toBe("knora_session_v2");
    expect(v2Clear.value).toBe("");
    expect(v2Clear.options.maxAge).toBe(0);

    const legacyClear = clearLegacySessionCookie();
    expect(legacyClear.name).toBe(LEGACY_SESSION_COOKIE_NAME);
    expect(legacyClear.name).toBe("knora_session");
    expect(legacyClear.value).toBe("");
    expect(legacyClear.options.maxAge).toBe(0);
  });
});
