import { describe, expect, it, vi } from "vitest";
import { forwardOperatorRequest } from "../../lib/operator/api";

describe("operator BFF boundary", () => {
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
