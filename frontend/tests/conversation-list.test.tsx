import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationList } from "@/components/conversations/ConversationList";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  usePathname: () => "/workspaces/w-1/conversations/c-1",
}));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const conversation = {
  id: "c-1",
  workspace_id: "w-1",
  title: "Earlier conversation",
  title_source: "manual",
  archived: false,
  revision: 3,
  updated_at: "2026-09-26T00:00:00Z",
};

describe("Conversation lifecycle controls", () => {
  it("opens an unsaved conversation from the collapsed rail without writing", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ConversationList
        workspaceId="w-1"
        initialConversations={[conversation]}
        presentation="collapsed"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "New Conversation" }));
    expect(push).toHaveBeenCalledWith("/workspaces/w-1/conversations");
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("renames with the loaded revision and keeps history link", async () => {
    const fetchMock = vi.fn(
      async (_url: string, _init: RequestInit) =>
        new Response(
          JSON.stringify({ ...conversation, title: "Renamed", revision: 4 }),
          {
            status: 200,
          },
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ConversationList
        workspaceId="w-1"
        initialConversations={[conversation]}
      />,
    );
    fireEvent.change(screen.getByLabelText("Rename Earlier conversation"), {
      target: { value: "Renamed" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save Earlier conversation title" }),
    );
    await screen.findByRole("link", { name: "Renamed" });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/workspaces/w-1/conversations/c-1",
    );
    expect(fetchMock.mock.calls[0][1].method).toBe("PATCH");
    expect(
      new Headers(fetchMock.mock.calls[0][1].headers).get("If-Match"),
    ).toBe("3");
  });

  it("restores an archived Conversation only through explicit mutation", async () => {
    const archived = { ...conversation, archived: true };
    const fetchMock = vi.fn(
      async (_url: string, _init: RequestInit) =>
        new Response(
          JSON.stringify({ ...archived, archived: false, revision: 4 }),
          {
            status: 200,
          },
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ConversationList
        workspaceId="w-1"
        initialConversations={[archived]}
        archived
      />,
    );
    expect(fetchMock).not.toHaveBeenCalled();
    expect(
      screen.getByRole("link", { name: "Earlier conversation" }),
    ).toHaveAttribute("href", "/workspaces/w-1/conversations/c-1");
    fireEvent.click(
      screen.getByRole("button", { name: "Restore Earlier conversation" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(
      new Headers(fetchMock.mock.calls[0][1].headers).get("If-Match"),
    ).toBe("3");
  });
});

describe("backend conversation search", () => {
  it("debounces backend q and keeps query-bound pagination", async () => {
    const searched = {
      ...conversation,
      id: "c-search",
      title: "Remote result",
    };
    const fetchMock = vi.fn(
      async (url: string) =>
        new Response(
          JSON.stringify({
            items: url.includes("cursor=")
              ? [{ ...searched, id: "c-page", title: "Remote next" }]
              : [searched],
            next_cursor: url.includes("cursor=") ? null : "q-next",
          }),
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ConversationList
        workspaceId="w-1"
        initialConversations={[conversation]}
      />,
    );
    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search conversations" }),
      { target: { value: "  remote & policy  " } },
    );
    expect(fetchMock).not.toHaveBeenCalled();
    await screen.findByRole("link", { name: "Remote result" });
    expect(fetchMock.mock.calls[0][0]).toContain("q=remote%20%26%20policy");
    fireEvent.click(
      screen.getByRole("button", { name: "Load more Conversations" }),
    );
    await screen.findByRole("link", { name: "Remote next" });
    expect(fetchMock.mock.calls[1][0]).toContain("q=remote%20%26%20policy");
    expect(fetchMock.mock.calls[1][0]).toContain("cursor=q-next");
  });
});
