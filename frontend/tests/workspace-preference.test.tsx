import { afterEach, describe, expect, it, vi } from "vitest";
import {
  decodePreference,
  encodePreference,
} from "@/lib/auth/workspace-preference";
import { resolveCurrentWorkspace } from "@/lib/auth/workspace";

const alice = { issuer: "https://id.example/realm", subject: "alice" };

describe("signed Workspace preference", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("binds a hint to the validated identity and rejects tampering", async () => {
    const value = await encodePreference("workspace-a", alice);
    expect(await decodePreference(value, alice)).toBe("workspace-a");
    expect(
      await decodePreference(value, { ...alice, subject: "bob" }),
    ).toBeNull();
    expect(await decodePreference(value + "x", alice)).toBeNull();
  });

  it("asks the backend to resolve an active owner Workspace without provisioning", async () => {
    const calls: Array<[string, RequestInit]> = [];
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
      calls.push([url, init]);
      return new Response(
        JSON.stringify({ state: "NO_ACTIVE_WORKSPACE", workspace: null }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    });

    const resolution = await resolveCurrentWorkspace(
      {
        issuer: alice.issuer,
        subject: alice.subject,
        accessToken: "server-token",
      },
      "stale-workspace",
    );

    expect(resolution.state).toBe("NO_ACTIVE_WORKSPACE");
    expect(calls).toHaveLength(1);
    expect(calls[0][0]).toMatch(/\/v1\/workspaces\/resolve$/);
    expect(calls[0][1].method).toBe("POST");
    expect(calls[0][1].body).toBe(
      JSON.stringify({ hint_id: "stale-workspace" }),
    );
  });
});
