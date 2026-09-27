// @vitest-environment node

import { describe, expect, it, vi } from "vitest";

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

describe("OIDC callback Workspace resolution", () => {
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
