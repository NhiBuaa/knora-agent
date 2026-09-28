import { beforeEach, describe, expect, it, vi } from "vitest";
import { forwardOperatorRequest } from "../../lib/operator/api";
import { proxyOperatorPath } from "../../app/api/operator/_proxy";
import { getSession } from "../../lib/auth/session";
import { decodePreference } from "../../lib/auth/workspace-preference";
import { cookies } from "next/headers";

vi.mock("../../lib/auth/session", () => ({ getSession: vi.fn() }));
vi.mock("../../lib/auth/workspace-preference", () => ({
  decodePreference: vi.fn(),
  WORKSPACE_PREFERENCE_COOKIE: "knora_workspace_preference",
}));
vi.mock("next/headers", () => ({
  cookies: vi.fn().mockResolvedValue({ get: () => ({ value: "signed-hint" }) }),
}));

const session = {
  issuer: "https://identity.example/realm",
  subject: "owner-1",
  accessToken: "secret-token",
  workspaceIds: [],
  capabilities: ["operator:read"],
  expiresAt: 9999999999,
};

beforeEach(() => vi.clearAllMocks());

describe("operator BFF boundary", () => {
  it("denies a session without operator capability before resolving a Workspace", async () => {
    vi.mocked(getSession).mockResolvedValue({ ...session, capabilities: [] });
    const response = await proxyOperatorPath(
      (workspaceId) => `/v1/workspaces/${workspaceId}/operator/operations`,
    );

    expect(response.status).toBe(403);
    expect(decodePreference).not.toHaveBeenCalled();
  });

  it("preserves backend owner denial for a selected Workspace", async () => {
    vi.mocked(getSession).mockResolvedValue(session);
    vi.mocked(decodePreference).mockResolvedValue("foreign-ws");
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response('{"detail":"WORKSPACE_ACCESS_DENIED"}', { status: 403 }),
      );
    const response = await proxyOperatorPath(
      (workspaceId) => `/v1/workspaces/${workspaceId}/operator/operations`,
    );

    expect(response.status).toBe(403);
    expect(upstream).toHaveBeenCalledTimes(1);
    upstream.mockRestore();
  });

  it("does not select the first Workspace when there is no current context", async () => {
    vi.mocked(getSession).mockResolvedValue(session);
    vi.mocked(decodePreference).mockResolvedValue(null);
    const response = await proxyOperatorPath(
      (workspaceId) => `/v1/workspaces/${workspaceId}/operator/operations`,
    );
    expect(response.status).toBe(409);
  });

  it("forwards an explicit archived Workspace target as a hint for backend authorization", async () => {
    vi.mocked(getSession).mockResolvedValue(session);
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}", { status: 200 }));
    const response = await proxyOperatorPath(
      (workspaceId) => `/v1/workspaces/${workspaceId}/operator/operations`,
      "archived-ws",
    );
    expect(response.status).toBe(200);
    expect(upstream.mock.calls[0][0]).toContain(
      "/v1/workspaces/archived-ws/operator/operations",
    );
    expect(cookies).not.toHaveBeenCalled();
    upstream.mockRestore();
  });
  it("forwards the bearer token and workspace path without exposing the token in the body", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response('{"workspace_id":"ws-1"}', { status: 200 }),
      );

    const response = await forwardOperatorRequest(
      "http://backend.local/v1/workspaces/ws-1/operator/operations",
      { accessToken: "secret-token" },
      fetcher,
    );

    expect(response.status).toBe(200);
    const [, init] = fetcher.mock.calls[0];
    expect(init?.headers).toBeInstanceOf(Headers);
    expect((init?.headers as Headers).get("Authorization")).toBe(
      "Bearer secret-token",
    );
  });

  it("preserves backend denial responses rather than converting them to success", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response('{"detail":"FORBIDDEN"}', { status: 403 }),
      );

    const response = await forwardOperatorRequest(
      "http://backend.local/v1/workspaces/ws-1/operator/traces/t-1",
      { accessToken: "secret-token" },
      fetcher,
    );

    expect(response.status).toBe(403);
    expect(await response.text()).toContain("FORBIDDEN");
  });
});
