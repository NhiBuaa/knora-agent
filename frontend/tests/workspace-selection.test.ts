import { afterEach, describe, expect, it, vi } from "vitest";
import { readEntryWorkspace } from "@/lib/auth/workspace";

const identity = {
  issuer: "https://id.example/realm",
  subject: "alice",
  accessToken: "server-token",
};

afterEach(() => vi.unstubAllGlobals());

describe("read-only owner Workspace selection", () => {
  it("uses the backend owner list without provisioning", async () => {
    const fetchMock = vi.fn(
      async (_url: string, _init?: RequestInit) =>
        new Response(
          JSON.stringify({ items: [{ id: "workspace-a" }], next_cursor: null }),
          {
            status: 200,
          },
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(readEntryWorkspace(identity, null)).resolves.toBe(
      "workspace-a",
    );
    expect(fetchMock.mock.calls[0][0]).toContain("archived=false&limit=1");
    expect(fetchMock.mock.calls[0][1]?.method).not.toBe("POST");
  });

  it("ignores a stale or foreign hint and falls back to an owned active Workspace", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 403 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ items: [{ id: "workspace-b" }], next_cursor: null }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    await expect(readEntryWorkspace(identity, "foreign")).resolves.toBe(
      "workspace-b",
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("surfaces backend unavailability instead of selecting another Workspace", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 503 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [{ id: "workspace-b" }] }), {
          status: 200,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    await expect(readEntryWorkspace(identity, "workspace-a")).rejects.toThrow();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
