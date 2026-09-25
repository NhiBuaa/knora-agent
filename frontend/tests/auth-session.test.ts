import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createAuthorizationTransaction,
  decodeAuthorizationTransaction,
  encodeAuthorizationTransaction,
} from "@/lib/auth/session";

describe("OIDC authorization transaction", () => {
  afterEach(() => vi.useRealTimers());

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
