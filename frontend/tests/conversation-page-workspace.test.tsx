// @vitest-environment node
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
const { request, session } = vi.hoisted(() => ({
  request: vi.fn(),
  session: vi.fn(),
}));
vi.mock("@/lib/auth/session", () => ({ getSession: session }));
vi.mock("@/lib/api/client", () => ({ knoraRequest: request }));
vi.mock("next/navigation", () => ({
  redirect: (path: string) => {
    throw new Error(`redirect:${path}`);
  },
}));
const Surface = ({
  workspaceRevision,
  workspaceArchived,
}: {
  workspaceRevision?: number;
  workspaceArchived?: boolean;
}) => (
  <span>{`revision:${workspaceRevision};archived:${workspaceArchived}`}</span>
);
vi.mock("@/components/conversations/ConversationView", () => ({
  ConversationView: (props: React.ComponentProps<typeof Surface>) => (
    <Surface {...props} />
  ),
}));
vi.mock("@/components/conversations/ConversationPanels", () => ({
  ConversationHub: (props: React.ComponentProps<typeof Surface>) => (
    <Surface {...props} />
  ),
}));
import ConversationsPage from "@/app/workspaces/[workspaceId]/conversations/page";
import ConversationPage from "@/app/workspaces/[workspaceId]/conversations/[conversationId]/page";
beforeEach(() => {
  vi.clearAllMocks();
  session.mockResolvedValue({
    accessToken: "server-only",
    issuer: "test",
    subject: "owner",
  });
  request.mockImplementation(async (path: string) =>
    path === "/v1/workspaces/authorized"
      ? { id: "authorized", archived: true, name: "Authorized", revision: 23 }
      : path.includes("?")
        ? { items: [], next_cursor: null }
        : { id: "c", workspace_id: "authorized", archived: true, revision: 3 },
  );
});
describe("authorized Conversation route Workspace projection", () => {
  const routes = [
    () =>
      ConversationsPage({
        params: Promise.resolve({ workspaceId: "authorized" }),
        searchParams: Promise.resolve({}),
      }),
    () =>
      ConversationPage({
        params: Promise.resolve({
          workspaceId: "authorized",
          conversationId: "c",
        }),
      }),
  ];
  it.each([0, 1])(
    "route %s carries only the authorized Workspace revision",
    async (index) => {
      const html = renderToStaticMarkup(await routes[index]());
      expect(html).toContain("revision:23;archived:true");
      expect(request).toHaveBeenCalledWith("/v1/workspaces/authorized", {
        accessToken: "server-only",
      });
      request.mockImplementation(async (path: string) =>
        path === "/v1/workspaces/authorized"
          ? {
              id: "authorized",
              archived: false,
              name: "Authorized",
              revision: 29,
            }
          : path.includes("?")
            ? { items: [], next_cursor: null }
            : { id: "c" },
      );
      expect(renderToStaticMarkup(await routes[index]())).toContain(
        "revision:29;archived:false",
      );
    },
  );
  it.each([0, 1])(
    "route %s does not expose restore authority without a session",
    async (index) => {
      session.mockResolvedValue(null);
      await expect(routes[index]()).rejects.toThrow("redirect:/api/auth/login");
      expect(request).not.toHaveBeenCalled();
    },
  );
  it.each([0, 1])(
    "route %s does not render controls after backend denial",
    async (index) => {
      request.mockRejectedValue(new Error("denied"));
      expect(renderToStaticMarkup(await routes[index]())).not.toContain(
        "revision:",
      );
    },
  );
});
