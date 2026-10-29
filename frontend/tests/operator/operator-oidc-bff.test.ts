import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/session", () => ({ getSession: vi.fn() }));
vi.mock("@/lib/operator/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/operator/api")>();
  return { ...actual, forwardOperatorRequest: vi.fn() };
});

import { proxyOperatorPath } from "@/app/api/operator/_proxy";
import { getSession, KnoraSession } from "@/lib/auth/session";
import { forwardOperatorRequest } from "@/lib/operator/api";

const baseSession: KnoraSession = {
  policyVersion: 1,
  rememberMe: false,
  sessionStartedAt: 1_800_000_000,
  sessionExpiresAt: 1_800_000_000 + 28_800,
  issuer: "https://id.example/realm",
  subject: "operator-1",
  accessToken: "oidc-access-token",
  refreshToken: "oidc-refresh-token",
  sessionId: "session-uuid",
  workspaceIds: [],
  capabilities: ["operator:read"],
  expiresAt: 1_800_000_300,
  refreshExpiresAt: 1_800_001_800,
};

describe("operator OIDC BFF authentication", () => {
  afterEach(() => vi.resetAllMocks());

  it("uses a backend-authorized owner Workspace rather than token Workspace claims", async () => {
    vi.mocked(getSession).mockResolvedValue(baseSession);
    vi.mocked(forwardOperatorRequest).mockResolvedValue(
      new Response("{}", { status: 200 }),
    );

    const response = await proxyOperatorPath(
      (workspaceId) => `/v1/workspaces/${workspaceId}/operator/operations`,
      "workspace-a",
    );

    expect(response.status).toBe(200);
    expect(forwardOperatorRequest).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/v1/workspaces/workspace-a/operator/operations",
      { accessToken: "oidc-access-token" },
    );
  });

  it("denies an absent session before attempting an operator backend request", async () => {
    vi.mocked(getSession).mockResolvedValue(null);

    const response = await proxyOperatorPath(
      (workspaceId) => `/v1/workspaces/${workspaceId}/operator/operations`,
    );

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      detail: "UNAUTHENTICATED",
    });
    expect(forwardOperatorRequest).not.toHaveBeenCalled();
  });

  it("denies a session without operator capability before attempting an operator request", async () => {
    vi.mocked(getSession).mockResolvedValue({
      ...baseSession,
      capabilities: [],
    });

    const response = await proxyOperatorPath(
      (workspaceId) => `/v1/workspaces/${workspaceId}/operator/operations`,
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      detail: "FORBIDDEN",
    });
    expect(forwardOperatorRequest).not.toHaveBeenCalled();
  });
});
