// @vitest-environment node

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(async () => ({
    issuer: "https://id.example/realm",
    subject: "operator",
    workspaceIds: [],
    accessToken: "server-token",
    capabilities: ["operator:read"],
  })),
}));
vi.mock("@/lib/auth/workspace-preference", () => ({
  WORKSPACE_PREFERENCE_COOKIE: "knora_workspace_preference",
  decodePreference: vi.fn(async () => "workspace-a"),
}));
vi.mock("@/lib/api/client", () => ({
  KnoraApiError: class KnoraApiError extends Error {
    constructor(public status: number) {
      super(String(status));
    }
  },
  knoraRequest: vi.fn(async (path: string) =>
    path.includes("limit=20")
      ? { items: [], next_cursor: null }
      : { id: "workspace-a", name: "Workspace A", archived: false },
  ),
}));
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => ({ value: "dark" }) })),
}));

import OperatorLayout from "@/app/operator/layout";
import { knoraRequest, KnoraApiError } from "@/lib/api/client";

describe("operator theme access", () => {
  it("retains one Appearance control after root theme control moves into product shells", async () => {
    const markup = renderToStaticMarkup(
      await OperatorLayout({ children: <p>Operations</p> }),
    );
    expect(markup).toContain("Appearance");
    expect(markup).toContain('value="dark" selected=""');
  });

  it("keeps Workspace selection available when a signed hint is no longer owned", async () => {
    vi.mocked(knoraRequest).mockImplementation(async (path) => {
      if (path.includes("limit=20"))
        return { items: [], next_cursor: null } as never;
      throw new KnoraApiError(403, null);
    });
    const markup = renderToStaticMarkup(
      await OperatorLayout({ children: <p>Operations</p> }),
    );
    expect(markup).toContain("Select a workspace");
    expect(markup).toContain("Appearance");
  });
});
