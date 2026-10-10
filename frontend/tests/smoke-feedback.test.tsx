import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationHub } from "@/components/conversations/ConversationPanels";
import { ConversationList } from "@/components/conversations/ConversationList";
import { ConversationComposer } from "@/components/conversations/ConversationComposer";
import { ConversationView } from "@/components/conversations/ConversationView";
const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/workspaces/w/conversations",
}));
const conversation = {
  id: "c",
  workspace_id: "w",
  title: "First question",
  title_source: "auto",
  archived: false,
  revision: 1,
  updated_at: "2026-10-10T00:00:00Z",
};
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  push.mockReset();
});
describe("smoke feedback", () => {
  it("opens an unsaved draft immediately without fetching history or creating records", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ConversationHub
        workspaceId="w"
        workspaceName="Workspace"
        initialConversations={[]}
      />,
    );
    expect(
      screen.getByText("Grounded answers from your workspace"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: "Question" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "New Conversation" }));
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes("/conversations"),
      ),
    ).toBe(false);
    expect(push).not.toHaveBeenCalled();
  });
  it("creates one conversation on first send then submits the question", async () => {
    const fetchMock = vi.fn(
      async (url: string, init?: RequestInit) =>
        new Response(
          JSON.stringify(
            init?.method === "POST"
              ? url.endsWith("/turns")
                ? {
                    id: "t",
                    conversation_id: "c",
                    sequence: 1,
                    question: "Nội dung là gì?",
                    status: "answered",
                    stage: null,
                    error_code: null,
                    result: {
                      decision: "ANSWER",
                      answer: "Nội dung",
                      citations: [],
                      refusal_reason: null,
                    },
                  }
                : conversation
              : { items: [], next_cursor: null },
          ),
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ConversationHub
        workspaceId="w"
        workspaceName="Workspace"
        initialConversations={[]}
      />,
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Question" }), {
      target: { value: "Nội dung là gì?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([, i]) => i?.method === "POST"),
      ).toHaveLength(2),
    );
    const posts = fetchMock.mock.calls.filter(([, i]) => i?.method === "POST");
    expect(posts[0][0]).toBe("/api/v1/workspaces/w/conversations");
    expect(posts[1][0]).toBe("/api/v1/workspaces/w/conversations/c/turns");
    expect(JSON.parse(posts[1][1]!.body as string).question).toBe(
      "Nội dung là gì?",
    );
  });
  it("Enter submits while Shift+Enter keeps a newline and composition does not submit", () => {
    const submit = vi.fn((e) => e.preventDefault());
    render(
      <ConversationComposer
        draft="Hello"
        onChange={vi.fn()}
        onSubmit={submit}
        readOnly={false}
        disabled={false}
        archived={false}
        restoreDisabled={false}
      />,
    );
    const input = screen.getByRole("textbox", { name: "Question" });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
    expect(submit).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "Enter", isComposing: true });
    expect(submit).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(submit).toHaveBeenCalledTimes(1);
  });
  it("archive requires a Knora dialog then removes the last selected conversation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ ...conversation, archived: true, revision: 2 }),
          ),
      ),
    );
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(
      <ConversationList
        workspaceId="w"
        initialConversations={[conversation]}
        selectedId="c"
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Archive First question" }),
    );
    const dialog = screen.getByRole("dialog", { name: "Archive conversation" });
    expect(confirm).not.toHaveBeenCalled();
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Archive conversation" }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("link", { name: "First question" }),
      ).not.toBeInTheDocument(),
    );
    expect(push).toHaveBeenCalledWith("/workspaces/w/conversations");
    confirm.mockRestore();
  });
  it("uses Vietnamese follow-up suggestions and submits when clicked", async () => {
    const turn = {
      id: "t",
      conversation_id: "c",
      sequence: 1,
      question: "Báo cáo có bao nhiêu chương?",
      status: "answered",
      stage: null,
      error_code: null,
      result: {
        decision: "ANSWER",
        answer: "Bảy chương.",
        citations: [],
        refusal_reason: null,
      },
    };
    const fetchMock = vi.fn(
      async (_u: string, i?: RequestInit) =>
        new Response(
          JSON.stringify(
            i?.method === "POST"
              ? { ...turn, id: "t2", sequence: 2 }
              : { items: [turn], next_cursor: null },
          ),
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Tìm bằng chứng hỗ trợ" }),
    );
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([, i]) => i?.method === "POST")).toBe(
        true,
      ),
    );
  });
  it("retains one conversation creation key after a lost response", async () => {
    const keys: (string | null)[] = [];
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST" && url.endsWith("/conversations")) {
        keys.push(new Headers(init.headers).get("Idempotency-Key"));
        if (keys.length === 1) throw new Error("response lost");
        return new Response(JSON.stringify(conversation));
      }
      if (init?.method === "POST")
        return new Response(
          JSON.stringify({
            id: "t",
            conversation_id: "c",
            sequence: 1,
            question: "Hello",
            status: "answered",
            stage: null,
            error_code: null,
            result: { decision: "ANSWER", answer: "Hello", citations: [] },
          }),
        );
      return new Response(JSON.stringify({ items: [], next_cursor: null }));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ConversationHub
        workspaceId="w"
        workspaceName="Workspace"
        initialConversations={[]}
      />,
    );
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText(/Submission status is uncertain/);
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(keys).toHaveLength(2));
    expect(keys[0]).toBeTruthy();
    expect(keys[1]).toBe(keys[0]);
  });
  it("recovers a draft authentication failure with an authorized read before retry", async () => {
    let expired = true;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === "POST" && expired)
          return new Response("{}", { status: 401 });
        return new Response(JSON.stringify({ id: "w", archived: false }));
      }),
    );
    render(
      <ConversationHub
        workspaceId="w"
        workspaceName="Workspace"
        initialConversations={[]}
      />,
    );
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText(/Your session has expired/);
    expired = false;
    fireEvent.click(screen.getByRole("button", { name: "Reload history" }));
    await waitFor(() =>
      expect(
        screen.queryByText(/Your session has expired/),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled();
  });
  it("keeps an older selected conversation behind newer entries", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ items: [], next_cursor: null })),
      ),
    );
    const newer = {
      ...conversation,
      id: "newer",
      title: "Newer question",
      updated_at: "2026-10-11T00:00:00Z",
    };
    render(
      <ConversationView
        workspaceId="w"
        conversation={conversation}
        initialConversations={[newer]}
      />,
    );
    const links = within(
      screen.getByRole("navigation", { name: "Conversations" }),
    )
      .getAllByRole("link")
      .filter((link) => link.getAttribute("href")?.includes("/conversations/"));
    expect(links.map((link) => link.textContent)).toEqual([
      "Newer question",
      "First question",
    ]);
  });
  it("polls the first queued turn using the newly created conversation ID", async () => {
    const queued = {
      id: "t",
      conversation_id: "c",
      sequence: 1,
      question: "Hello",
      status: "queued",
      stage: null,
      error_code: null,
      result: null,
    };
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push(url);
        return new Response(
          JSON.stringify(
            url.endsWith("/conversations")
              ? conversation
              : url.includes("/turns?")
                ? { items: [queued], next_cursor: null }
                : queued,
          ),
        );
      }),
    );
    render(
      <ConversationHub
        workspaceId="w"
        workspaceName="Workspace"
        initialConversations={[]}
      />,
    );
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() =>
      expect(calls).toContain("/api/v1/workspaces/w/conversations/c/turns/t"),
    );
    expect(calls.some((url) => url.includes("/conversations//"))).toBe(false);
  });
});
