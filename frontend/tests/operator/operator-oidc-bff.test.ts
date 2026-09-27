import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/session", () => ({ getSession: vi.fn() }));
vi.mock("@/lib/auth/workspace", () => ({ readEntryWorkspace: vi.fn() }));
vi.mock("@/lib/operator/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/operator/api")>();
  return { ...actual, forwardOperatorRequest: vi.fn() };
});

import { proxyOperatorPath } from "@/app/api/operator/_proxy";
import { getSession } from "@/lib/auth/session";
import { readEntryWorkspace } from "@/lib/auth/workspace";
import { forwardOperatorRequest } from "@/lib/operator/api";

describe("operator OIDC BFF authentication", () => {
  afterEach(() => vi.resetAllMocks());

  it("uses a backend-authorized owner Workspace rather than token Workspace claims", async () => {
    vi.mocked(getSession).mockResolvedValue({
      issuer: "https://id.example/realm",
      subject: "operator-1",
      accessToken: "oidc-access-token",
      workspaceIds: [],
      capabilities: ["operator.read"],
      expiresAt: 1_800_000_000,
    });
    vi.mocked(readEntryWorkspace).mockResolvedValue("workspace-a");
    vi.mocked(forwardOperatorRequest).mockResolvedValue(
      new Response("{}", { status: 200 }),
    );

    const response = await proxyOperatorPath(
      (workspaceId) => `/v1/workspaces/${workspaceId}/operator/operations`,
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

  it("denies a session with no backend-owned Workspace before attempting an operator request", async () => {
    vi.mocked(getSession).mockResolvedValue({
      issuer: "https://id.example/realm",
      subject: "operator-1",
      accessToken: "oidc-access-token",
      workspaceIds: [],
      capabilities: ["operator.read"],
      expiresAt: 1_800_000_000,
    });
    vi.mocked(readEntryWorkspace).mockResolvedValue(null);

    const response = await proxyOperatorPath(
      (workspaceId) => `/v1/workspaces/${workspaceId}/operator/operations`,
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      detail: "WORKSPACE_ACCESS_DENIED",
    });
    expect(forwardOperatorRequest).not.toHaveBeenCalled();
  });
});
