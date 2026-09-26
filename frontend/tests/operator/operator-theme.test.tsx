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
vi.mock("@/lib/auth/workspace", () => ({
  readEntryWorkspace: vi.fn(async () => "workspace-a"),
}));
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => ({ value: "dark" }) })),
}));

import OperatorLayout from "@/app/operator/layout";

describe("operator theme access", () => {
  it("retains one Appearance control after root theme control moves into product shells", async () => {
    const markup = renderToStaticMarkup(
      await OperatorLayout({ children: <p>Operations</p> }),
    );
    expect(markup).toContain("Appearance");
    expect(markup).toContain('value="dark" selected=""');
  });
});
