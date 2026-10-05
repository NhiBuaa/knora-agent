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
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  knoraRequest: vi.fn(),
}));

import HomePage from "@/app/page";
import { renderToStaticMarkup } from "react-dom/server";
import {
  readEntryWorkspace,
  resolveCurrentWorkspace,
} from "@/lib/auth/workspace";
import { getSession } from "@/lib/auth/session";
import WorkspacePage from "@/app/workspaces/[workspaceId]/page";
import { KnoraApiError, knoraRequest } from "@/lib/api/client";

describe("canonical entry", () => {
  it("renders denied workspace recovery without disclosing the requested ID or name", async () => {
    vi.mocked(knoraRequest).mockRejectedValueOnce(
      new KnoraApiError(403, { name: "Private name" }),
    );
    const html = renderToStaticMarkup(
      await WorkspacePage({
        params: Promise.resolve({ workspaceId: "private-id" }),
      }),
    );
    expect(html).toContain("Workspace unavailable");
    expect(html).toContain("Choose another workspace");
    expect(html).not.toContain("Private name");
    expect(html).not.toContain("private-id");
  });
  it("keeps a transient failure distinct from denied workspace access", async () => {
    vi.mocked(knoraRequest).mockRejectedValueOnce(new KnoraApiError(503, {}));
    const html = renderToStaticMarkup(
      await WorkspacePage({ params: Promise.resolve({ workspaceId: "ws" }) }),
    );
    expect(html).toContain("Unable to load this Workspace.");
    expect(html).not.toContain("Workspace unavailable");
  });
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
