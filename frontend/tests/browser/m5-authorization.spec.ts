import { describe, expect, it, vi } from "vitest";
import { forwardOperatorRequest, sessionFromCookies } from "@/lib/operator/api";

describe("M5 browser authorization boundary", () => {
  it("does not invent success for an unauthenticated or expired-session denial", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response('{"error":{"code":"UNAUTHENTICATED"}}', { status: 401 }),
    );
    const response = await forwardOperatorRequest(
      "http://backend.local/v1/workspaces/workspace-a/operator/tool-lifecycle",
      { accessToken: "expired-token" },
      fetcher,
    );

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ error: { code: "UNAUTHENTICATED" } });
    expect((fetcher.mock.calls[0]?.[1]?.headers as Headers).get("Authorization")).toBe(
      "Bearer expired-token",
    );
  });

  it("forwards workspace denial for an opaque resource without existence leakage", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response('{"error":{"code":"WORKSPACE_ACCESS_DENIED"}}', { status: 403 }),
    );
    const response = await forwardOperatorRequest(
      "http://backend.local/v1/workspaces/workspace-b/operator/traces/opaque-trace-id",
      { accessToken: "workspace-a-token" },
      fetcher,
    );

    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: { code: "WORKSPACE_ACCESS_DENIED" } });
    expect(fetcher).toHaveBeenCalledWith(
      "http://backend.local/v1/workspaces/workspace-b/operator/traces/opaque-trace-id",
      expect.objectContaining({ body: undefined }),
    );
  });

  it("requires both session values before a browser request can be formed", () => {
    expect(sessionFromCookies({ accessToken: "token" })).toBeNull();
    expect(sessionFromCookies({ workspaceId: "workspace-a" })).toBeNull();
    expect(sessionFromCookies({ accessToken: "token", workspaceId: "workspace-a" })).toEqual({
      accessToken: "token",
      workspaceId: "workspace-a",
    });
  });
});
