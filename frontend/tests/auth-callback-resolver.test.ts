// @vitest-environment node

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) =>
      name === "knora_oidc_transaction" ? { value: "transaction" } : undefined,
  })),
}));
vi.mock("@/lib/auth/session", () => ({
  AUTH_TRANSACTION_COOKIE_NAME: "knora_oidc_transaction",
  decodeAuthorizationTransaction: vi.fn(async () => ({
    state: "valid-state",
    redirectUri: "https://app.example/api/auth/callback",
    codeVerifier: "verifier",
    nonce: "nonce",
  })),
  exchangeCode: vi.fn(async () => ({
    issuer: "https://id.example/realm",
    subject: "alice",
    accessToken: "server-token",
    workspaceIds: [],
    capabilities: [],
    expiresAt: 2000000000,
  })),
  encodeSession: vi.fn(async () => "signed-session"),
  sessionCookie: vi.fn(() => ({
    name: "knora_session",
    value: "signed-session",
    options: { httpOnly: true, path: "/" },
  })),
  clearAuthorizationTransactionCookie: vi.fn(() => ({
    name: "knora_oidc_transaction",
    value: "",
    options: { maxAge: 0, path: "/api/auth" },
  })),
}));
vi.mock("@/lib/auth/workspace", () => ({
  resolveCurrentWorkspace: vi.fn(async () => {
    throw new Error("backend unavailable");
  }),
}));

import { GET } from "@/app/api/auth/callback/route";
import {
  decodeAuthorizationTransaction,
  exchangeCode,
} from "@/lib/auth/session";
import { resolveCurrentWorkspace } from "@/lib/auth/workspace";

describe("safe browser callback failures", () => {
  beforeEach(() => vi.clearAllMocks());
  it.each([
    "?error=private-provider-error&error_description=private-detail&state=private-state",
    "?code=private-code",
    "?code=private-code&state=wrong-state",
    "?code=private-code&state=valid-state&error=untrusted",
  ])(
    "redirects invalid callback %s without exposing inputs and consumes its transaction",
    async (query) => {
      const response = await GET(
        new Request(`https://app.example/api/auth/callback${query}`),
      );
      expect(response.status).toBe(307);
      expect(response.headers.get("location")).toBe(
        "https://app.example/auth/failed",
      );
      expect(response.cookies.get("knora_oidc_transaction")?.value).toBe("");
      expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
      expect(response.cookies.get("knora_session")).toBeUndefined();
      expect(exchangeCode).not.toHaveBeenCalled();
      expect(resolveCurrentWorkspace).not.toHaveBeenCalled();
    },
  );

  it("clears a rejected signed transaction before returning to sign-in", async () => {
    vi.mocked(decodeAuthorizationTransaction).mockResolvedValueOnce(null);
    const response = await GET(
      new Request(
        "https://app.example/api/auth/callback?code=private-code&state=valid-state",
      ),
    );
    expect(response.headers.get("location")).toBe(
      "https://app.example/auth/failed",
    );
    expect(response.cookies.get("knora_oidc_transaction")?.value).toBe("");
  });

  it("clears a failed exchange without leaking its error", async () => {
    vi.mocked(exchangeCode).mockRejectedValueOnce(
      new Error("private-code private-token"),
    );
    const response = await GET(
      new Request(
        "https://app.example/api/auth/callback?code=private-code&state=valid-state",
      ),
    );
    expect(response.headers.get("location")).toBe(
      "https://app.example/auth/failed",
    );
    expect(response.cookies.get("knora_oidc_transaction")?.value).toBe("");
    expect(await response.text()).not.toContain("private-");
  });
});

describe("OIDC callback Workspace resolution", () => {
  it("lands a resolved active owner in the backend-selected Workspace", async () => {
    vi.mocked(resolveCurrentWorkspace).mockResolvedValueOnce({
      state: "ACTIVE",
      workspace: {
        id: "owned-workspace",
        name: "My Workspace",
        archived: false,
        revision: 1,
        created_at: "2026-10-06T00:00:00Z",
      },
    });
    const response = await GET(
      new Request(
        "https://app.example/api/auth/callback?code=one-time-code&state=valid-state",
      ),
    );
    expect(response.headers.get("location")).toBe(
      "https://app.example/workspaces/owned-workspace",
    );
    expect(exchangeCode).toHaveBeenLastCalledWith(
      "one-time-code",
      "https://app.example/api/auth/callback",
      "verifier",
      "nonce",
    );
    expect(response.cookies.get("knora_oidc_transaction")?.value).toBe("");
  });
  it("redirects on the signed callback origin even if an ambient app origin differs", async () => {
    const previous = process.env.NEXT_PUBLIC_APP_ORIGIN;
    process.env.NEXT_PUBLIC_APP_ORIGIN = "https://wrong.example";
    try {
      const response = await GET(
        new Request(
          "https://app.example/api/auth/callback?code=one-time-code&state=valid-state",
        ),
      );
      expect(response.headers.get("location")).toBe(
        "https://app.example/workspaces?retry=1",
      );
    } finally {
      if (previous === undefined) delete process.env.NEXT_PUBLIC_APP_ORIGIN;
      else process.env.NEXT_PUBLIC_APP_ORIGIN = previous;
    }
  });
  it("preserves the validated session for a retry when backend resolution fails", async () => {
    const response = await GET(
      new Request(
        "https://app.example/api/auth/callback?code=one-time-code&state=valid-state",
      ),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://app.example/workspaces?retry=1",
    );
    expect(response.headers.get("set-cookie")).toContain("knora_session=");
  });
});
