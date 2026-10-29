// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  sessionResult: null as any,
  throwError: false,
}));

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(async (_persist?: boolean) => {
    if (state.throwError) {
      throw new Error("SESSION_REFRESH_UNAVAILABLE");
    }
    return state.sessionResult;
  }),
}));

import { GET } from "@/app/api/auth/session/route";

describe("GET /api/auth/session", () => {
  afterEach(() => {
    state.sessionResult = null;
    state.throwError = false;
    vi.clearAllMocks();
  });

  it("returns session: null with no-store when there is no active session", async () => {
    state.sessionResult = null;
    const response = await GET();
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const body = await response.json();
    expect(body).toEqual({ session: null });
  });

  it("returns sanitized session with issuer, subject, workspaceIds, capabilities and no secrets/tokens", async () => {
    state.sessionResult = {
      policyVersion: 1,
      rememberMe: true,
      sessionStartedAt: 1_800_000_000,
      sessionExpiresAt: 1_800_000_000 + 2_592_000,
      issuer: "https://id.example/realms/knora",
      subject: "user-123",
      accessToken: "secret-access-token",
      refreshToken: "secret-refresh-token",
      workspaceIds: ["ws-1", "ws-2"],
      capabilities: ["chat:read", "chat:write"],
      expiresAt: 1_800_000_300,
      refreshExpiresAt: 1_800_604_800,
      sessionId: "session-uuid-1",
    };

    const response = await GET();
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const body = await response.json();
    expect(body).toEqual({
      session: {
        issuer: "https://id.example/realms/knora",
        subject: "user-123",
        workspaceIds: ["ws-1", "ws-2"],
        capabilities: ["chat:read", "chat:write"],
      },
    });
    // Ensure no sensitive fields leaked
    expect(body.session.accessToken).toBeUndefined();
    expect(body.session.refreshToken).toBeUndefined();
    expect(body.session.sessionId).toBeUndefined();
    expect(body.session.expiresAt).toBeUndefined();
    expect(body.session.refreshExpiresAt).toBeUndefined();
  });

  it("returns 503 with no-store and does NOT return session: null when refresh is unavailable", async () => {
    state.throwError = true;
    const response = await GET();
    expect(response.status).toBe(503);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const body = await response.json();
    expect(body).toEqual({ error: "SESSION_REFRESH_UNAVAILABLE" });
    expect(body.session).toBeUndefined();
  });
});
