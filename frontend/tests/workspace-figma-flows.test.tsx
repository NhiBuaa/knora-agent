import React from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
const { push, refresh, pathname } = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
  pathname: vi.fn(() => "/workspaces/ws"),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
  usePathname: pathname,
}));
import { WorkspaceManagement } from "@/components/workspaces/WorkspaceManagement";
import { WorkspaceHome } from "@/components/workspaces/WorkspaceHome";
import { WorkspaceSelector } from "@/components/workspaces/WorkspaceSelector";
import { ArchivedWorkspaceList } from "@/components/workspaces/ArchivedWorkspaceList";
import { WorkspaceShell } from "@/components/workspaces/WorkspaceShell";

const workspace = {
  id: "ws",
  name: "Research workspace",
  archived: false,
  revision: 4,
  created_at: "2026-10-05T00:00:00Z",
};
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  pathname.mockReturnValue("/workspaces/ws");
});

it.each([
  ["/operator/operations", "/operator/operations"],
  ["/operator/traces/old-trace", "/operator/traces"],
  ["/operator/evaluations/old-report", "/operator/evaluations"],
  ["/operator/unknown/old-id", "/operator"],
  ["/workspaces/ws/documents/old-document", "/workspaces/new/documents"],
])(
  "selects useful context from %s without carrying a stale detail identity",
  async (path, destination) => {
    pathname.mockReturnValue(path);
    vi.stubGlobal("fetch", async (url: string) =>
      url.endsWith("/ws")
        ? json(workspace)
        : url === "/api/workspace-selection"
          ? json({ ok: true })
          : json({
              items: [{ ...workspace, id: "new", name: "New workspace" }],
              next_cursor: null,
            }),
    );
    render(
      <WorkspaceSelector workspaceId="ws" workspaceName={workspace.name} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /switch workspace/i }));
    fireEvent.click(
      await screen.findByRole("button", { name: "New workspace" }),
    );
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    if (destination) expect(push).toHaveBeenCalledWith(destination);
    else expect(push).not.toHaveBeenCalled();
  },
);

it("confirms archive in a dialog and cancels without a mutation", async () => {
  const user = userEvent.setup();
  const request = vi.fn();
  vi.stubGlobal("fetch", request);
  render(<WorkspaceManagement initialWorkspaces={[workspace]} />);
  await user.click(screen.getByRole("button", { name: /archive workspace/i }));
  expect(
    screen.getByRole("dialog", { name: /archive workspace/i }),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: /cancel/i }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(request).not.toHaveBeenCalled();
});

it("opens creation explicitly from the no-active state and Escape returns focus", async () => {
  const user = userEvent.setup();
  render(<WorkspaceManagement initialWorkspaces={[]} />);
  expect(
    screen.getByRole("heading", { name: "No active workspace" }),
  ).toBeVisible();
  const trigger = screen.getByRole("button", { name: /create workspace/i });
  await user.click(trigger);
  const dialog = screen.getByRole("dialog", { name: /create workspace/i });
  expect(within(dialog).getByLabelText("Workspace name")).toHaveFocus();
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
  expect(
    screen.getByRole("link", { name: /restore workspace/i }),
  ).toHaveAttribute("href", "/workspaces/archived");
});

it("offers restore and retained navigation for archived read-only workspaces", () => {
  render(<WorkspaceHome workspace={{ ...workspace, archived: true }} />);
  expect(screen.getByText(/Archived workspace · Read-only/i)).toBeVisible();
  expect(
    screen.queryByRole("button", { name: /new conversation/i }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /restore workspace/i }),
  ).toBeVisible();
  expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute(
    "href",
    "/workspaces/ws/documents",
  );
});

it("states limited document management access from capabilities without inventing a role", () => {
  render(<WorkspaceHome workspace={workspace} capabilities={[]} />);
  expect(screen.getByText("Limited permissions")).toBeVisible();
});

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status });
}
it("searches the entire workspace corpus through q and changes the signed selection only on action", async () => {
  const later = { ...workspace, id: "later", name: "Later-page workspace" };
  const requests: Array<[string, RequestInit | undefined]> = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    requests.push([url, init]);
    if (url === "/api/v1/workspaces/ws") return json(workspace);
    if (url === "/api/workspace-selection") return json({ ok: true });
    return json({
      items: url.includes("q=Later") ? [later] : [workspace],
      next_cursor: "more",
    });
  });
  render(<WorkspaceSelector workspaceId="ws" workspaceName={workspace.name} />);
  fireEvent.click(screen.getByRole("button", { name: /switch workspace/i }));
  fireEvent.change(
    screen.getByRole("searchbox", { name: /search workspaces/i }),
    { target: { value: "Later" } },
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "Later-page workspace" }),
  );
  await waitFor(() => expect(push).toHaveBeenCalledWith("/workspaces/later"));
  expect(requests.some(([url]) => url.includes("q=Later"))).toBe(true);
  expect(
    requests.find(([url]) => url === "/api/workspace-selection")?.[1]?.body,
  ).toBe(JSON.stringify({ workspaceId: "later" }));
});

it("ignores a stale search response after a newer query", async () => {
  let oldResponse!: (response: Response) => void;
  vi.stubGlobal("fetch", async (url: string) => {
    if (url === "/api/v1/workspaces/ws") return json(workspace);
    if (url.includes("q=old"))
      return new Promise<Response>((resolve) => {
        oldResponse = resolve;
      });
    return json({
      items: url.includes("q=new")
        ? [{ ...workspace, id: "new", name: "New match" }]
        : [workspace],
      next_cursor: null,
    });
  });
  render(<WorkspaceSelector workspaceId="ws" workspaceName={workspace.name} />);
  fireEvent.click(screen.getByRole("button", { name: /switch workspace/i }));
  const search = screen.getByRole("searchbox", { name: /search workspaces/i });
  fireEvent.change(search, { target: { value: "old" } });
  await waitFor(() => expect(oldResponse).toBeDefined());
  fireEvent.change(search, { target: { value: "new" } });
  await screen.findByRole("button", { name: "New match" });
  await act(async () =>
    oldResponse(
      json({ items: [{ ...workspace, name: "Old match" }], next_cursor: null }),
    ),
  );
  expect(
    screen.queryByRole("button", { name: "Old match" }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "New match" })).toBeVisible();
});

it("resolves an authorized name absent from page one and suppresses a denied cached name", async () => {
  vi.stubGlobal("fetch", async () => json(workspace));
  const view = render(
    <WorkspaceShell
      workspaces={[]}
      nextCursor="more"
      capabilities={[]}
      subject="alice"
      themePreference="light"
    >
      <p>Content</p>
    </WorkspaceShell>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Menu" }));
  await screen.findAllByText(workspace.name);
  view.unmount();
  vi.stubGlobal("fetch", async () => json({}, 403));
  render(
    <WorkspaceSelector workspaceId="ws" workspaceName="Private cached name" />,
  );
  await screen.findByText("Workspace unavailable");
  expect(screen.queryByText("Private cached name")).not.toBeInTheDocument();
});

it("distinguishes empty archives from no search results and searches later pages", async () => {
  const older = {
    ...workspace,
    id: "older",
    archived: true,
    name: "Older workspace",
  };
  vi.stubGlobal("fetch", async (url: string) =>
    json({ items: url.includes("q=Older") ? [older] : [], next_cursor: null }),
  );
  const view = render(<ArchivedWorkspaceList initialWorkspaces={[]} />);
  expect(
    screen.getByRole("heading", { name: "No archived workspaces" }),
  ).toBeVisible();
  const search = screen.getByRole("searchbox", {
    name: /search archived workspaces/i,
  });
  fireEvent.change(search, { target: { value: "missing" } });
  await screen.findByRole("heading", { name: "No archived workspaces found" });
  fireEvent.change(search, { target: { value: "Older" } });
  await screen.findByRole("link", { name: "Older workspace" });
  expect(screen.queryByText(/3 archived/)).not.toBeInTheDocument();
  view.unmount();
});

it("restores with the authoritative revision and uses resolver before navigation", async () => {
  const calls: Array<[string, RequestInit]> = [];
  vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
    calls.push([url, init]);
    if (url.endsWith("/restore")) return json({ ...workspace, revision: 5 });
    if (url.endsWith("/resolve")) return json({ state: "ACTIVE", workspace });
    return json({ ok: true });
  });
  render(
    <ArchivedWorkspaceList
      initialWorkspaces={[{ ...workspace, archived: true }]}
    />,
  );
  fireEvent.click(
    screen.getByRole("button", { name: /restore research workspace/i }),
  );
  await waitFor(() => expect(push).toHaveBeenCalledWith("/workspaces/ws"));
  expect(new Headers(calls[0][1].headers).get("If-Match")).toBe("4");
  expect(calls[1][0]).toBe("/api/v1/workspaces/resolve");
  expect(calls[2][0]).toBe("/api/workspace-selection");
});

it("retains the creation key for a retry of the same proposed name", async () => {
  const calls: RequestInit[] = [];
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    calls.push(init);
    return json({}, 503);
  });
  render(<WorkspaceManagement initialWorkspaces={[]} />);
  fireEvent.click(screen.getByRole("button", { name: /create workspace/i }));
  fireEvent.change(screen.getByLabelText("Workspace name"), {
    target: { value: "Literature review" },
  });
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: /^create workspace$/i,
    }),
  );
  await screen.findByRole("alert");
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: /^create workspace$/i,
    }),
  );
  await waitFor(() => expect(calls).toHaveLength(2));
  expect(new Headers(calls[0].headers).get("Idempotency-Key")).toBe(
    new Headers(calls[1].headers).get("Idempotency-Key"),
  );
});

it("selects a newly created workspace through the validated preference endpoint", async () => {
  const calls: Array<[string, RequestInit]> = [];
  vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
    calls.push([url, init]);
    return url === "/api/v1/workspaces"
      ? json(workspace, 201)
      : json({ ok: true });
  });
  render(<WorkspaceManagement initialWorkspaces={[]} />);
  fireEvent.click(screen.getByRole("button", { name: /^create workspace$/i }));
  fireEvent.change(screen.getByLabelText("Workspace name"), {
    target: { value: "Research workspace" },
  });
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: /^create workspace$/i,
    }),
  );
  await waitFor(() => expect(push).toHaveBeenCalledWith("/workspaces/ws"));
  expect(calls[1][0]).toBe("/api/workspace-selection");
});

it("keeps restored state truthful when resolution fails", async () => {
  let count = 0;
  vi.stubGlobal("fetch", async () =>
    ++count === 1 ? json(workspace) : json({}, 503),
  );
  render(
    <ArchivedWorkspaceList
      initialWorkspaces={[{ ...workspace, archived: true }]}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: /restore research/i }));
  await screen.findByRole("alert");
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Workspace restored. Reload to select an active Workspace.",
  );
  expect(
    screen.queryByRole("button", { name: /restore research/i }),
  ).not.toBeInTheDocument();
  expect(push).not.toHaveBeenCalled();
});

it("opens the backend-resolved next workspace after confirmed archive", async () => {
  const next = { ...workspace, id: "next" };
  vi.stubGlobal("fetch", async (url: string) =>
    url.endsWith("/archive")
      ? json({ ...workspace, archived: true })
      : url.endsWith("/resolve")
        ? json({ state: "ACTIVE", workspace: next })
        : json({ ok: true }),
  );
  render(<WorkspaceManagement initialWorkspaces={[workspace]} />);
  fireEvent.click(screen.getByRole("button", { name: /archive workspace/i }));
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: /^archive workspace$/i,
    }),
  );
  await waitFor(() => expect(push).toHaveBeenCalledWith("/workspaces/next"));
});
