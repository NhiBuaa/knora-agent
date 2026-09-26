// @vitest-environment node

import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(async () => ({
    issuer: "https://id.example/realm",
    subject: "alice",
    accessToken: "server-token",
  })),
}));
vi.mock("@/lib/api/client", () => ({
  knoraRequest: vi.fn(async () => ({ id: "workspace-a", archived: false })),
}));

import { POST } from "@/app/api/workspace-selection/route";
import { knoraRequest } from "@/lib/api/client";

describe("Workspace preference mutation", () => {
  it("denies a cross-origin browser request before backend lookup", async () => {
    const response = await POST(
      new Request("https://app.example/api/workspace-selection", {
        method: "POST",
        headers: { origin: "https://evil.example" },
        body: JSON.stringify({ workspaceId: "workspace-a" }),
      }),
    );
    expect(response.status).toBe(403);
    expect(knoraRequest).not.toHaveBeenCalled();
  });

  it("sets a signed cookie only after backend confirms an active Workspace", async () => {
    const response = await POST(
      new Request("https://app.example/api/workspace-selection", {
        method: "POST",
        headers: { origin: "https://app.example" },
        body: JSON.stringify({ workspaceId: "workspace-a" }),
      }),
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("set-cookie")).toContain(
      "knora_workspace_preference=",
    );
    expect(knoraRequest).toHaveBeenCalledWith(
      "/v1/workspaces/workspace-a",
      expect.objectContaining({ accessToken: "server-token" }),
    );
  });
});
