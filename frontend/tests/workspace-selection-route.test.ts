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
  KnoraApiError: class KnoraApiError extends Error {
    constructor(public status: number) {
      super(`HTTP ${status}`);
    }
  },
}));

import { DELETE, POST } from "@/app/api/workspace-selection/route";
import { knoraRequest, KnoraApiError } from "@/lib/api/client";

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

  it("uses the public Host when Next's internal request URL differs", async () => {
    const response = await POST(
      new Request("http://localhost:3000/api/workspace-selection", {
        method: "POST",
        headers: {
          host: "127.0.0.1:3000",
          origin: "http://127.0.0.1:3000",
          "x-forwarded-proto": "http",
          "sec-fetch-site": "same-origin",
        },
        body: JSON.stringify({ workspaceId: "workspace-a" }),
      }),
    );
    expect(response.status).toBe(200);
  });

  it("preserves backend ownership denial instead of reporting availability failure", async () => {
    vi.mocked(knoraRequest).mockRejectedValueOnce(new KnoraApiError(403, {}));
    const response = await POST(
      new Request("https://app.example/api/workspace-selection", {
        method: "POST",
        headers: { origin: "https://app.example" },
        body: JSON.stringify({ workspaceId: "foreign" }),
      }),
    );
    expect(response.status).toBe(403);
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("clears the identity-bound hint after all Workspaces are archived", async () => {
    const response = await DELETE(
      new Request("https://app.example/api/workspace-selection", {
        method: "DELETE",
        headers: { origin: "https://app.example" },
      }),
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("set-cookie")).toContain(
      "knora_workspace_preference=",
    );
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
  });
});
