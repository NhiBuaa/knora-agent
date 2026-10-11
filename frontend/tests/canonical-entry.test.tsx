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
  it("always opens workspace management after login even with existing workspaces", async () => {
    await expect(HomePage({})).rejects.toThrow("REDIRECT:/workspaces");
    expect(readEntryWorkspace).not.toHaveBeenCalled();
    expect(resolveCurrentWorkspace).not.toHaveBeenCalled();
  });
  it.each([{ "signed-out": "1" }, { state: "knora-logout-complete" }])(
    "opens sign-in after logout",
    async (query) => {
      vi.mocked(getSession).mockResolvedValueOnce(null);
      await expect(
        HomePage({ searchParams: Promise.resolve(query) }),
      ).rejects.toThrow("REDIRECT:/api/auth/login");
    },
  );
});
