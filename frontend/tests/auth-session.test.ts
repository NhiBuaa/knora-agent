import { describe, expect, it } from "vitest";
import {
  createAuthorizationTransaction,
  decodeAuthorizationTransaction,
  encodeAuthorizationTransaction,
} from "@/lib/auth/session";

describe("OIDC authorization transaction", () => {
  it("creates a state, nonce, and PKCE verifier bound to one callback", async () => {
    const transaction = createAuthorizationTransaction("https://app.test/callback");

    expect(transaction.state).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(transaction.nonce).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(transaction.codeVerifier).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(transaction.codeChallenge).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(transaction.redirectUri).toBe("https://app.test/callback");
    expect(transaction.state).not.toBe(transaction.nonce);
  });

  it("rejects a tampered or expired callback transaction", async () => {
    const transaction = createAuthorizationTransaction("https://app.test/callback");
    const encoded = await encodeAuthorizationTransaction(transaction);
    await expect(decodeAuthorizationTransaction(encoded)).resolves.toMatchObject(transaction);

    const tampered = `${encoded.slice(0, -1)}${encoded.endsWith("a") ? "b" : "a"}`;
    await expect(decodeAuthorizationTransaction(tampered)).resolves.toBeNull();

    await expect(decodeAuthorizationTransaction(undefined)).resolves.toBeNull();
  });
});
