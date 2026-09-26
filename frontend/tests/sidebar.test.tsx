import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkspaceSidebar } from "@/components/shell/WorkspaceSidebar";
import { MobileDrawer } from "@/components/shell/MobileDrawer";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const workspace = {
  id: "ws-a",
  name: "Workspace A",
  archived: false,
  revision: 1,
  created_at: "2026-09-26T00:00:00Z",
};

describe("Workspace sidebar", () => {
  it("expands independently and fetches only five recent Conversations", async () => {
    const fetchMock = vi.fn(
      async (_url: string) =>
        new Response(
          JSON.stringify({
            items: Array.from({ length: 5 }, (_, index) => ({
              id: `c-${index}`,
              workspace_id: "ws-a",
              title: `Conversation ${index}`,
              archived: false,
              revision: 0,
              title_source: "auto",
              updated_at: "2026-09-26T00:00:00Z",
            })),
            next_cursor: "more",
          }),
          { status: 200 },
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<WorkspaceSidebar workspaces={[workspace]} capabilities={[]} />);

    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Expand Workspace A" }));
    await waitFor(() =>
      expect(screen.getAllByTestId("recent-conversation")).toHaveLength(5),
    );
    expect(fetchMock.mock.calls[0][0]).toContain("limit=5");
    expect(screen.getByRole("link", { name: "Workspace A" })).toHaveAttribute(
      "href",
      "/workspaces/ws-a",
    );
    expect(screen.getByRole("link", { name: "View all" })).toHaveAttribute(
      "href",
      "/workspaces/ws-a/conversations",
    );
    expect(
      screen.queryByRole("link", { name: "Operator" }),
    ).not.toBeInTheDocument();
  });

  it("loads the next owned Workspace page only after an explicit click", async () => {
    const next = { ...workspace, id: "ws-b", name: "Workspace B" };
    const fetchMock = vi.fn(
      async (_url: string) =>
        new Response(JSON.stringify({ items: [next], next_cursor: null }), {
          status: 200,
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <WorkspaceSidebar
        workspaces={[workspace]}
        nextCursor="page-two"
        capabilities={[]}
      />,
    );

    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Load more Workspaces" }),
    );
    await screen.findByRole("link", { name: "Workspace B" });
    expect(fetchMock.mock.calls[0][0]).toContain("cursor=page-two");
  });

  it("creates a Conversation only when New Conversation is clicked", async () => {
    const navigate = vi.fn();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: null }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "conversation-new" }), {
          status: 201,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <WorkspaceSidebar
        workspaces={[workspace]}
        capabilities={[]}
        onNavigate={navigate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Expand Workspace A" }));
    await screen.findByRole("button", { name: "New Conversation" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "New Conversation" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/v1/workspaces/ws-a/conversations",
    );
    expect(fetchMock.mock.calls[1][1].method).toBe("POST");
    expect(navigate).toHaveBeenCalledWith(
      "/workspaces/ws-a/conversations/conversation-new",
    );
  });

  it("returns focus to the menu trigger when Escape closes the drawer", () => {
    render(
      <MobileDrawer>
        <a href="/workspaces">Workspaces</a>
      </MobileDrawer>,
    );
    const trigger = screen.getByRole("button", { name: "Menu" });
    fireEvent.click(trigger);
    expect(
      screen.getByRole("dialog", { name: "Workspace navigation" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close menu" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("reuses one creation key after an ambiguous Conversation response", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: null }), {
          status: 200,
        }),
      )
      .mockRejectedValueOnce(new Error("connection lost"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "conversation-new" }), {
          status: 200,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn().mockReturnValueOnce("stable-key"),
    });
    render(
      <WorkspaceSidebar
        workspaces={[workspace]}
        capabilities={[]}
        onNavigate={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Expand Workspace A" }));
    const create = await screen.findByRole("button", {
      name: "New Conversation",
    });
    fireEvent.click(create);
    await screen.findByRole("alert");
    fireEvent.click(create);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const first = new Headers(fetchMock.mock.calls[1][1].headers);
    const second = new Headers(fetchMock.mock.calls[2][1].headers);
    expect(first.get("Idempotency-Key")).toBe("stable-key");
    expect(second.get("Idempotency-Key")).toBe("stable-key");
  });

  it("closes the mobile drawer after a navigation link is selected", () => {
    render(
      <MobileDrawer>
        <a href="/workspaces/ws-a">Workspace A</a>
      </MobileDrawer>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));
    const link = screen.getByRole("link", { name: "Workspace A" });
    link.addEventListener("click", (event) => event.preventDefault());
    fireEvent.click(link);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("removes an archived Workspace when refreshed owner data changes", () => {
    const view = render(
      <WorkspaceSidebar workspaces={[workspace]} capabilities={[]} />,
    );
    expect(
      screen.getByRole("link", { name: "Workspace A" }),
    ).toBeInTheDocument();
    view.rerender(<WorkspaceSidebar workspaces={[]} capabilities={[]} />);
    expect(
      screen.queryByRole("link", { name: "Workspace A" }),
    ).not.toBeInTheDocument();
  });
});
