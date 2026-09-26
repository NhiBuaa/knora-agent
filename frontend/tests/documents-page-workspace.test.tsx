// @vitest-environment node

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(async () => ({
    workspaceIds: ["ws-1"],
    capabilities: ["documents:write"],
    accessToken: "server-token",
  })),
}));
vi.mock("@/lib/api/client", () => ({
  knoraRequest: vi.fn(async () => ({ archived: true })),
}));
vi.mock("@/components/documents/DocumentList", () => ({
  DocumentList: ({ workspaceArchived }: { workspaceArchived: boolean }) => (
    <span>
      {workspaceArchived ? "Read-only Workspace" : "Writable Workspace"}
    </span>
  ),
}));

import DocumentsPage from "@/app/workspaces/[workspaceId]/documents/page";

describe("document route Workspace state", () => {
  it("uses the backend archived projection before rendering write controls", async () => {
    const html = renderToStaticMarkup(
      await DocumentsPage({ params: Promise.resolve({ workspaceId: "ws-1" }) }),
    );
    expect(html).toContain("Read-only Workspace");
  });
});
