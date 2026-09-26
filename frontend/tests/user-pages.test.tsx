import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));
import { WorkspaceManagement } from "@/components/workspaces/WorkspaceManagement";
import { WorkspaceHome } from "@/components/workspaces/WorkspaceHome";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  refresh.mockClear();
});

const archived = {
  id: "ws-archived",
  name: "Archived Workspace",
  archived: true,
  revision: 2,
  created_at: "2026-09-26T00:00:00Z",
};

describe("Workspace management", () => {
  it("shows create and restore when every Workspace is archived", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [archived], next_cursor: null }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ ...archived, archived: false, revision: 3 }),
          {
            status: 200,
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: null }), {
          status: 200,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspaceManagement initialWorkspaces={[]} />);
    await screen.findByText("No active Workspace");
    expect(
      screen.getByRole("button", { name: "Create Workspace" }),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Show archived Workspaces" }),
    );
    await screen.findByText("Archived Workspace");
    expect(
      screen.getByRole("link", { name: "Archived Workspace" }),
    ).toHaveAttribute("href", "/workspaces/ws-archived");
    fireEvent.click(
      screen.getByRole("button", { name: "Restore Archived Workspace" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(
      new Headers(fetchMock.mock.calls[1][1].headers).get("If-Match"),
    ).toBe("2");
    expect(refresh).toHaveBeenCalled();
  });

  it("sends revision on rename and explains archive before mutation", async () => {
    const active = { ...archived, archived: false, name: "Team", revision: 4 };
    const fetchMock = vi.fn(
      async (_url: string, _init: RequestInit) =>
        new Response(
          JSON.stringify({ ...active, name: "Renamed", revision: 5 }),
          {
            status: 200,
          },
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal(
      "confirm",
      vi.fn(() => false),
    );
    render(<WorkspaceManagement initialWorkspaces={[active]} />);

    fireEvent.change(screen.getByLabelText("Rename Team"), {
      target: { value: "Renamed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Team name" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock.mock.calls[0][1].method).toBe("PATCH");
    expect(
      new Headers(fetchMock.mock.calls[0][1].headers).get("If-Match"),
    ).toBe("4");
    fireEvent.click(screen.getByRole("button", { name: "Archive Renamed" }));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("read-only"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("loads another active Workspace page with the backend cursor", async () => {
    const second = { ...archived, id: "ws-2", name: "Second", archived: false };
    const fetchMock = vi.fn(
      async (_url: string) =>
        new Response(JSON.stringify({ items: [second], next_cursor: null }), {
          status: 200,
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <WorkspaceManagement initialWorkspaces={[]} nextCursor="next-page" />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Load more Workspaces" }),
    );
    await screen.findByRole("link", { name: "Second" });
    expect(fetchMock.mock.calls[0][0]).toContain("cursor=next-page");
  });

  it("paginates archived Workspaces without loading them on navigation", async () => {
    const older = { ...archived, id: "ws-older", name: "Older Workspace" };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ items: [archived], next_cursor: "archive-next" }),
          {
            status: 200,
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [older], next_cursor: null }), {
          status: 200,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<WorkspaceManagement initialWorkspaces={[]} />);
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Show archived Workspaces" }),
    );
    await screen.findByText("Archived Workspace");
    fireEvent.click(
      screen.getByRole("button", { name: "Load more archived Workspaces" }),
    );
    await screen.findByText("Older Workspace");
    expect(fetchMock.mock.calls[1][0]).toContain("cursor=archive-next");
  });

  it("resolves the next active Workspace after an archive mutation", async () => {
    const active = {
      ...archived,
      id: "ws-active",
      name: "Active",
      archived: false,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ ...active, archived: true, revision: 3 }),
          {
            status: 200,
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ state: "NO_ACTIVE_WORKSPACE", workspace: null }),
          {
            status: 200,
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true),
    );
    render(<WorkspaceManagement initialWorkspaces={[active]} />);
    fireEvent.click(screen.getByRole("button", { name: "Archive Active" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/workspaces/resolve");
    expect(fetchMock.mock.calls[1][1].body).toBe(
      JSON.stringify({ hint_id: null }),
    );
    expect(fetchMock.mock.calls[2][0]).toBe("/api/workspace-selection");
    expect(fetchMock.mock.calls[2][1].method).toBe("DELETE");
    expect(screen.getByText("No active Workspace")).toBeInTheDocument();
  });

  it("keeps a successful archive truthful if the follow-up resolver fails", async () => {
    const active = {
      ...archived,
      id: "ws-active",
      name: "Active",
      archived: false,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ ...active, archived: true, revision: 3 }),
          {
            status: 200,
          },
        ),
      )
      .mockRejectedValueOnce(new Error("network failure"));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true),
    );
    render(<WorkspaceManagement initialWorkspaces={[active]} />);
    fireEvent.click(screen.getByRole("button", { name: "Archive Active" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Workspace archived. Reload to select another active Workspace.",
    );
  });

  it("uses a new creation key if the proposed Workspace name changes after failure", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 503 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ ...archived, archived: false, name: "Second" }),
          { status: 201 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", {
      randomUUID: vi
        .fn()
        .mockReturnValueOnce("key-first")
        .mockReturnValueOnce("key-second"),
    });
    render(<WorkspaceManagement initialWorkspaces={[]} />);
    fireEvent.change(screen.getByLabelText("Workspace name"), {
      target: { value: "First" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Workspace" }));
    await screen.findByRole("alert");
    fireEvent.change(screen.getByLabelText("Workspace name"), {
      target: { value: "Second" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Workspace" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(
      new Headers(fetchMock.mock.calls[0][1].headers).get("Idempotency-Key"),
    ).toBe("key-first");
    expect(
      new Headers(fetchMock.mock.calls[1][1].headers).get("Idempotency-Key"),
    ).toBe("key-second");
  });

  it("updates management rows when a server refresh returns new owner data", () => {
    const active = {
      ...archived,
      id: "ws-active",
      name: "Active",
      archived: false,
    };
    const view = render(<WorkspaceManagement initialWorkspaces={[active]} />);
    expect(screen.getByRole("link", { name: "Active" })).toBeInTheDocument();
    view.rerender(<WorkspaceManagement initialWorkspaces={[]} />);
    expect(
      screen.queryByRole("link", { name: "Active" }),
    ).not.toBeInTheDocument();
  });
});

describe("Workspace Home", () => {
  it("starts a Conversation only on explicit action and navigates to its ID", async () => {
    const navigate = vi.fn();
    const fetchMock = vi.fn(
      async (_url: string, _init: RequestInit) =>
        new Response(JSON.stringify({ id: "conversation-new" }), {
          status: 201,
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <WorkspaceHome
        workspace={{ ...archived, archived: false }}
        onNavigate={navigate}
      />,
    );
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "New Conversation" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/workspaces/ws-archived/conversations",
    );
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(navigate).toHaveBeenCalledWith(
      "/workspaces/ws-archived/conversations/conversation-new",
    );
  });
});
