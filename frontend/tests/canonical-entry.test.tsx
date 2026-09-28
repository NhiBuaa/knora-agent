// @vitest-environment node

import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(async () => ({
    issuer: "https://id.example/realm",
    subject: "alice",
    accessToken: "server-token",
  })),
}));
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => undefined })),
}));
vi.mock("@/lib/auth/workspace", () => ({
  readEntryWorkspace: vi.fn(async () => "workspace-a"),
  resolveCurrentWorkspace: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  redirect: vi.fn((path: string) => {
    throw new Error(`REDIRECT:${path}`);
  }),
}));

import HomePage from "@/app/page";
import { renderToStaticMarkup } from "react-dom/server";
import {
  readEntryWorkspace,
  resolveCurrentWorkspace,
} from "@/lib/auth/workspace";
import { getSession } from "@/lib/auth/session";

describe("canonical entry", () => {
  it("uses read-only owner selection for an authenticated user without provisioning", async () => {
    await expect(HomePage({})).rejects.toThrow(
      "REDIRECT:/workspaces/workspace-a",
    );
    expect(readEntryWorkspace).toHaveBeenCalledWith(
      expect.objectContaining({ accessToken: "server-token" }),
      null,
    );
    expect(resolveCurrentWorkspace).not.toHaveBeenCalled();
  });

  it("shows a signed-out state without silently starting a new login", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(null);
    const html = renderToStaticMarkup(
      await HomePage({ searchParams: Promise.resolve({ "signed-out": "1" }) }),
    );
    expect(html).toContain("Signed out");
    expect(html).toContain("/api/auth/login");
  });

  it("shows the signed-out state after Keycloak returns from RP logout", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(null);
    const html = renderToStaticMarkup(
      await HomePage({
        searchParams: Promise.resolve({ state: "knora-logout-complete" }),
      }),
    );
    expect(html).toContain("Signed out");
    expect(html).toContain("/api/auth/login");
  });

  it("does not claim a still-authenticated visitor has signed out", async () => {
    await expect(
      HomePage({ searchParams: Promise.resolve({ "signed-out": "1" }) }),
    ).rejects.toThrow("REDIRECT:/workspaces/workspace-a");
  });
});
