// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { GET as login } from "@/app/api/auth/login/route";
import {
  createAuthorizationTransaction,
  decodeAuthorizationTransaction,
  encodeAuthorizationTransaction,
  encodeSession,
  decodeSession,
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
    const encoded = await encodeSession({
      issuer: "https://id.example/realm",
      subject: "alice",
      accessToken: "private-token",
      workspaceIds: [],
      capabilities: [],
    });
    const decoded = await decodeSession(encoded);
    expect(decoded?.issuer).toBe("https://id.example/realm");
    expect(decoded?.accessToken).toBe("private-token");
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
