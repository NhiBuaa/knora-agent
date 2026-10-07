import React from "react";
import {
  cleanup,
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConversationView } from "@/components/conversations/ConversationView";
import { ConversationHub } from "@/components/conversations/ConversationPanels";
import { EvidenceInspector } from "@/components/citations/EvidenceInspector";
import type { TurnResponse } from "@/generated/knora-openapi";
import userEvent from "@testing-library/user-event";
const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  usePathname: () => "/workspaces/w/conversations",
}));
beforeEach(() => push.mockReset());

const conversation = {
  id: "c",
  workspace_id: "w",
  title: "Annual reporting structure",
  title_source: "manual",
  archived: false,
  revision: 3,
  updated_at: "2026-09-26T00:00:00Z",
};
const citation = {
  evidence_id: "E1",
  document_id: "doc",
  document_version_id: "historical-v1",
  source_key: "guide",
  source_name: "Guide",
  heading_path: ["Report structure"],
  start_line: 12,
  end_line: 18,
  excerpt: "Historical excerpt from the selected turn",
  content_checksum: "sha-old",
  page_start: 12,
  page_end: 12,
  start_offset: 4,
  end_offset: 42,
};
const answered = {
  id: "t",
  conversation_id: "c",
  sequence: 1,
  question: "How many chapters?",
  status: "answered",
  stage: null,
  error_code: null,
  result: {
    decision: "ANSWER",
    answer: "Seven chapters are required.",
    citations: [citation],
    refusal_reason: null,
    trace_id: "trace",
    workspace_id: "w",
  },
};
function history(items: (typeof answered)[] = [answered]) {
  Object.defineProperty(window, "innerWidth", {
    value: 1440,
    writable: true,
    configurable: true,
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () => new Response(JSON.stringify({ items, next_cursor: null })),
    ),
  );
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
describe("Conversation panel interactions", () => {
  it("uses the retained context minimum only for an archived Workspace unselected answer", () => {
    const view = render(
      <EvidenceInspector
        workspaceId="w"
        workspaceArchived
        turn={answered as TurnResponse}
      />,
    );
    const context = screen.getByText("VERIFY THE ANSWER").closest("blockquote");
    expect(context).toHaveClass("min-h-[96px]");
    expect(context).not.toHaveClass("min-h-[146px]");
    expect(
      screen.getByText(
        "Choose a citation in the answer to inspect the exact supporting passage and its source context.",
      ),
    ).toBeVisible();
    view.rerender(
      <EvidenceInspector workspaceId="w" turn={answered as TurnResponse} />,
    );
    expect(context).toHaveClass("min-h-[146px]");
    expect(context).not.toHaveClass("min-h-[96px]");
  });
  it.each([
    { state: "empty", turn: null },
    {
      state: "pending",
      turn: { ...answered, status: "pending", result: null },
    },
    {
      state: "interrupted",
      turn: { ...answered, status: "interrupted", result: null },
    },
    {
      state: "refused",
      turn: {
        ...answered,
        status: "refused",
        result: {
          ...answered.result,
          decision: "REFUSAL",
          answer: null,
          citations: [],
          refusal_reason: "INSUFFICIENT_EVIDENCE",
        },
      },
    },
  ])(
    "keeps the full evidence minimum for archived $state context",
    ({ turn }) => {
      render(
        <EvidenceInspector
          workspaceId="w"
          workspaceArchived
          turn={turn as TurnResponse | null}
        />,
      );
      const inspector = screen.getByRole("complementary", {
        name: /evidence/i,
      });
      const context = inspector.querySelector("blockquote");
      expect(context).toHaveClass("min-h-[146px]");
      expect(context).not.toHaveClass("min-h-[96px]");
    },
  );
  it("shows the archived Workspace notice beside selected historical evidence without changing provenance", async () => {
    history();
    const view = render(
      <ConversationView
        workspaceId="w"
        conversation={conversation}
        workspaceArchived
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: /citation 1/i }));
    const inspector = screen.getByRole("complementary", { name: /evidence/i });
    expect(within(inspector).getByText("READ-ONLY WORKSPACE")).toBeVisible();
    expect(
      within(inspector).getByText(
        "Workspace archived. Restore it to ask new questions or make changes.",
      ),
    ).toBeVisible();
    expect(within(inspector).getByText(citation.excerpt)).toBeVisible();
    expect(
      within(inspector).getByText(citation.excerpt).closest("blockquote"),
    ).toHaveClass("min-h-[146px]");
    expect(within(inspector).getByText("historical-v1")).toBeVisible();
    expect(
      within(inspector).getByRole("link", { name: /open document/i }),
    ).toHaveAttribute("href", "/workspaces/w/documents/doc");
    fireEvent.click(within(inspector).getByText("Provenance"));
    for (const value of ["E1", "guide", "sha-old", "4–42"])
      expect(within(inspector).getByText(value)).toBeVisible();
    expect(
      within(inspector).queryByRole("button", { name: /restore/i }),
    ).not.toBeInTheDocument();
    view.rerender(
      <ConversationView workspaceId="w" conversation={conversation} />,
    );
    expect(screen.queryByText("READ-ONLY WORKSPACE")).not.toBeInTheDocument();
    view.rerender(
      <ConversationView
        workspaceId="w"
        conversation={{ ...conversation, archived: true }}
      />,
    );
    expect(screen.queryByText("READ-ONLY WORKSPACE")).not.toBeInTheDocument();
    expect(screen.getByText(citation.excerpt)).toBeVisible();
  });
  it("shows the Workspace notice in the archived list Hub and removes it after authoritative active props", () => {
    const hub = render(
      <ConversationHub
        workspaceId="w"
        workspaceName="Workspace"
        initialConversations={[]}
        workspaceArchived
      />,
    );
    expect(screen.getByText("READ-ONLY WORKSPACE")).toBeVisible();
    hub.rerender(
      <ConversationHub
        workspaceId="w"
        workspaceName="Workspace"
        initialConversations={[]}
        archived
      />,
    );
    expect(screen.queryByText("READ-ONLY WORKSPACE")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Evidence will appear here" }),
    ).toBeVisible();
  });
  it.each([
    ["processing", null, "Processing question"],
    ["interrupted", null, "Evidence unavailable"],
    [
      "refused",
      {
        ...answered.result,
        decision: "REFUSAL",
        answer: null,
        citations: [],
        refusal_reason: "INSUFFICIENT_EVIDENCE",
      },
      "No supporting citation",
    ],
  ])(
    "keeps %s evidence presentation separate from the Workspace notice",
    (status, result, heading) => {
      render(
        <EvidenceInspector
          workspaceId="w"
          workspaceArchived
          turn={{ ...answered, status, result } as any}
        />,
      );
      expect(
        screen.getByRole("heading", { name: heading as string }),
      ).toBeVisible();
      expect(screen.getByText("READ-ONLY WORKSPACE")).toBeVisible();
      expect(screen.queryByText(citation.excerpt)).not.toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name: /open document/i }),
      ).not.toBeInTheDocument();
    },
  );
  it("selects another citation on the same Turn and clears a citation removed by history reload", async () => {
    history();
    const response = {
      ...answered,
      result: {
        ...answered.result,
        citations: [
          citation,
          { ...citation, evidence_id: "E2", excerpt: "Second exact passage" },
        ],
      },
    };
    const interrupted = {
      ...answered,
      id: "interrupted",
      sequence: 2,
      status: "interrupted",
      result: null,
    };
    let loads = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              items: loads++ === 0 ? [response, interrupted] : [],
              next_cursor: null,
            }),
          ),
      ),
    );
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    const first = await screen.findByRole("button", { name: /citation 1/i });
    const second = screen.getByRole("button", { name: /citation 2/i });
    fireEvent.click(first);
    fireEvent.click(second);
    expect(first).toHaveAttribute("aria-pressed", "false");
    expect(second).toHaveAttribute("aria-pressed", "true");
    expect(
      within(
        screen.getByRole("complementary", { name: /evidence/i }),
      ).getByText("Second exact passage"),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() =>
      expect(
        screen.queryByText("Second exact passage"),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getByRole("heading", { name: "Evidence will appear here" }),
    ).toBeVisible();
  });
  it("toggles the same Turn citation by mouse and keyboard without changing another Turn", async () => {
    const later = {
      ...answered,
      id: "later",
      sequence: 2,
      result: {
        ...answered.result,
        citations: [{ ...citation, excerpt: "Later Turn evidence" }],
      },
    };
    history([answered, later]);
    const user = userEvent.setup();
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    const earlier = within(
      await screen.findByRole("listitem", { name: "Question 1" }),
    ).getByRole("button", { name: /citation 1/i });
    const second = within(
      screen.getByRole("listitem", { name: "Question 2" }),
    ).getByRole("button", { name: /citation 1/i });
    await user.click(earlier);
    expect(earlier).toHaveAttribute("aria-pressed", "true");
    await user.click(earlier);
    expect(earlier).toHaveAttribute("aria-pressed", "false");
    expect(
      screen.getByRole("heading", { name: "Select a citation" }),
    ).toBeVisible();
    earlier.focus();
    await user.keyboard("{Enter}");
    await user.click(second);
    expect(earlier).toHaveAttribute("aria-pressed", "false");
    expect(second).toHaveAttribute("aria-pressed", "true");
    expect(
      within(
        screen.getByRole("complementary", { name: /evidence/i }),
      ).getByText("Later Turn evidence"),
    ).toBeVisible();
    second.focus();
    await user.keyboard(" ");
    expect(second).toHaveAttribute("aria-pressed", "false");
  });
  it.each(["desktop", "narrow"])(
    "preserves an uncertain creation request across %s rail dismissal",
    async (mode) => {
      history();
      if (mode === "narrow") window.innerWidth = 390;
      const keys: (string | null)[] = [];
      vi.stubGlobal(
        "fetch",
        vi.fn(async (_url: string, init: RequestInit = {}) => {
          if (init.method === "POST") {
            keys.push(new Headers(init.headers).get("Idempotency-Key"));
            throw new Error("Response lost after accepted creation");
          }
          return new Response(
            JSON.stringify({ items: [answered], next_cursor: null }),
          );
        }),
      );
      render(<ConversationView workspaceId="w" conversation={conversation} />);
      await screen.findByText(answered.result.answer);
      if (mode === "narrow")
        fireEvent.click(
          screen.getByRole("button", { name: "Show conversations" }),
        );
      fireEvent.click(screen.getByRole("button", { name: "New Conversation" }));
      await screen.findByText(/Unable to confirm Conversation creation/);
      if (mode === "narrow") fireEvent.keyDown(document, { key: "Escape" });
      else fireEvent.click(screen.getByRole("button", { name: "Hide rail" }));
      fireEvent.click(
        screen.getByRole("button", { name: "Show conversations" }),
      );
      fireEvent.click(screen.getByRole("button", { name: "New Conversation" }));
      await waitFor(() => expect(keys).toHaveLength(2));
      expect(keys[0]).toBeTruthy();
      expect(keys[1]).toBe(keys[0]);
    },
  );
  it("returns focus to the selected citation when desktop evidence closes", async () => {
    history();
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    const source = await screen.findByRole("button", { name: /citation 1/i });
    source.focus();
    fireEvent.click(source);
    expect(
      screen.getByRole("complementary", { name: /evidence/i }).parentElement,
    ).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Close evidence" }));
    expect(
      screen.queryByRole("complementary", { name: /evidence/i }),
    ).not.toBeInTheDocument();
    expect(source).toHaveFocus();
  });
  it("opens the selected historical citation and clears it when the conversation changes", async () => {
    history();
    const view = render(
      <ConversationView workspaceId="w" conversation={conversation} />,
    );
    fireEvent.click(await screen.findByRole("button", { name: /citation 1/i }));
    const inspector = screen.getByRole("complementary", { name: /evidence/i });
    expect(within(inspector).getByText(citation.excerpt)).toBeVisible();
    expect(within(inspector).getByText("historical-v1")).toBeVisible();
    expect(
      within(inspector).getByRole("link", { name: /open document/i }),
    ).toHaveAttribute("href", "/workspaces/w/documents/doc");
    view.rerender(
      <ConversationView
        workspaceId="w"
        conversation={{ ...conversation, id: "other" }}
      />,
    );
    expect(
      within(
        screen.getByRole("complementary", { name: /evidence/i }),
      ).queryByText(citation.excerpt),
    ).not.toBeInTheDocument();
  });
  it("supports all five rail and inspector combinations without moving the composer", async () => {
    history();
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    await screen.findByText(answered.result.answer);
    const center = screen.getByRole("region", {
      name: "Conversation workspace",
    });
    expect(
      within(center).getByRole("form", { name: "Question composer" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close evidence" }));
    expect(
      screen.queryByRole("complementary", { name: /evidence/i }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Collapse rail" }));
    expect(
      screen.getByRole("navigation", { name: "Conversations" }),
    ).toHaveAttribute("data-rail", "collapsed");
    fireEvent.click(screen.getByRole("button", { name: "Open evidence" }));
    fireEvent.click(screen.getByRole("button", { name: "Hide rail" }));
    expect(
      screen.queryByRole("navigation", { name: "Conversations" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show conversations" }));
    expect(
      screen.getByRole("navigation", { name: "Conversations" }),
    ).toHaveAttribute("data-rail", "expanded");
    expect(
      within(center).getByRole("form", { name: "Question composer" }),
    ).toBeInTheDocument();
  });
  it("resizes with keyboard, resets, restores session preferences and isolates identities", async () => {
    history();
    const props = {
      workspaceId: "w",
      conversation,
      identityScope: {
        issuer: "https://id.example/realms/knora",
        subject: "alice",
      },
    };
    const view = render(<ConversationView {...props} />);
    await screen.findByText(answered.result.answer);
    const divider = screen.getByRole("separator", {
      name: "Resize conversation rail",
    });
    fireEvent.keyDown(divider, { key: "ArrowRight" });
    expect(Number(divider.getAttribute("aria-valuenow"))).toBeGreaterThan(252);
    fireEvent.doubleClick(divider);
    expect(divider).toHaveAttribute("aria-valuenow", "252");
    fireEvent.click(screen.getByRole("button", { name: "Collapse rail" }));
    view.unmount();
    const restored = render(<ConversationView {...props} />);
    expect(
      screen.getByRole("navigation", { name: "Conversations" }),
    ).toHaveAttribute("data-rail", "collapsed");
    restored.rerender(
      <ConversationView
        {...props}
        identityScope={{ ...props.identityScope, subject: "bob" }}
      />,
    );
    expect(
      screen.getByRole("navigation", { name: "Conversations" }),
    ).toHaveAttribute("data-rail", "expanded");
    expect(Object.values(sessionStorage)).not.toContain(citation.excerpt);
  });
  it("fills a suggested draft without sending until explicit Ask", async () => {
    history([]);
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Summarize this workspace" }),
    );
    expect(screen.getByLabelText("Question")).toHaveValue(
      "Summarize this workspace",
    );
    expect(
      (fetch as any).mock.calls.filter(
        (call: any[]) => call[1]?.method === "POST",
      ),
    ).toHaveLength(0);
  });
  it.each([
    ["processing", "retrieving", "Retrieving evidence…"],
    ["processing", "future-stage", "Processing question…"],
    ["interrupted", null, "The answer was interrupted."],
    ["failed", null, "System error"],
  ])("renders truthful %s %s state", async (status, stage, label) => {
    const turn = {
      ...answered,
      status,
      stage,
      result: null,
      error_code: status === "failed" ? "SYSTEM_FAILURE" : null,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async (url: string) =>
          new Response(
            JSON.stringify(
              url.includes("?limit")
                ? { items: [turn], next_cursor: null }
                : turn,
            ),
          ),
      ),
    );
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    expect(await screen.findByText(label)).toBeInTheDocument();
    expect(screen.queryByText(answered.result.answer)).not.toBeInTheDocument();
  });
  it("restores an archived conversation with its revision but blocks an archived workspace", async () => {
    const archived = { ...conversation, archived: true };
    const requests: any[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit = {}) => {
        requests.push([url, init]);
        return new Response(
          JSON.stringify(
            url.endsWith("/restore")
              ? { ...conversation, revision: 4 }
              : { items: [answered], next_cursor: null },
          ),
        );
      }),
    );
    const view = render(
      <ConversationView workspaceId="w" conversation={archived} />,
    );
    const restore = await screen.findByRole("button", {
      name: "Restore conversation",
    });
    expect(
      screen.getByText("Archived conversation · Read-only"),
    ).toHaveAttribute("role", "status");
    expect(screen.queryByLabelText("Question")).not.toBeInTheDocument();
    expect(screen.getByText(answered.result.answer)).toBeVisible();
    const user = userEvent.setup();
    restore.focus();
    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(screen.getByLabelText("Question")).toBeInTheDocument(),
    );
    expect(
      new Headers(
        requests.find(([url]) => url.endsWith("/restore"))[1].headers,
      ).get("If-Match"),
    ).toBe("3");
    view.unmount();
    render(
      <ConversationView
        workspaceId="w"
        conversation={archived}
        workspaceArchived
      />,
    );
    expect(
      screen.getByRole("button", { name: "Restore workspace" }),
    ).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Restore conversation" }),
    ).not.toBeInTheDocument();
  });
  it.each(["WORKSPACE_ARCHIVED", "CONVERSATION_ARCHIVED"])(
    "keeps generic read-only copy after %s rejection without archive authority",
    async (code) => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async (_url: string, init: RequestInit = {}) =>
          init.method === "POST"
            ? new Response(JSON.stringify({ error: { code } }), { status: 409 })
            : new Response(
                JSON.stringify({ items: [answered], next_cursor: null }),
              ),
        ),
      );
      render(<ConversationView workspaceId="w" conversation={conversation} />);
      await screen.findByText(answered.result.answer);
      fireEvent.change(screen.getByLabelText("Question"), {
        target: { value: "New question" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Ask" }));
      expect(
        await screen.findByText("This Conversation is read-only."),
      ).toHaveAttribute("role", "status");
      expect(
        screen.queryByText("Archived conversation · Read-only"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /restore/i }),
      ).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Question")).not.toBeInTheDocument();
      expect(screen.getByText(answered.result.answer)).toBeVisible();
    },
  );
});

describe("narrow panel and citation recovery", () => {
  it("keeps workspace mutation dialogs outside the narrow rail and retains canonical navigation", async () => {
    history();
    window.innerWidth = 390;
    render(
      <ConversationView
        workspaceId="w"
        workspaceName="Authorized workspace"
        conversation={conversation}
        workspaceSelector={<button>Switch workspace</button>}
      />,
    );
    await screen.findByText(answered.result.answer);
    fireEvent.click(screen.getByRole("button", { name: "Show conversations" }));
    const dialog = screen.getByRole("dialog", { name: "Conversations" });
    expect(
      within(dialog).queryByRole("button", { name: "Switch workspace" }),
    ).not.toBeInTheDocument();
    expect(within(dialog).getByText("Authorized workspace")).toBeVisible();
    expect(
      within(dialog).getByRole("link", { name: "Manage workspaces" }),
    ).toHaveAttribute("href", "/workspaces");
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
  });
  it("focuses a reopened desktop inspector after choosing a citation", async () => {
    history();
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    const citationButton = await screen.findByRole("button", {
      name: /citation 1/i,
    });
    fireEvent.click(screen.getByRole("button", { name: "Close evidence" }));
    citationButton.focus();
    fireEvent.click(citationButton);
    expect(
      screen.getByRole("complementary", { name: /evidence/i }).parentElement,
    ).toHaveFocus();
  });
  it("reopens a dismissed citation in a single narrow sheet and returns keyboard focus", async () => {
    history();
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    const source = await screen.findByRole("button", { name: /citation 1/i });
    window.innerWidth = 390;
    fireEvent(window, new Event("resize"));
    source.focus();
    fireEvent.click(source);
    const dialog = screen.getByRole("dialog", { name: "Evidence" });
    expect(within(dialog).getByText(citation.excerpt)).toBeVisible();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(source).toHaveFocus();
    fireEvent.click(source);
    expect(source).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(source);
    expect(screen.getByRole("dialog", { name: "Evidence" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Close evidence" }));
    fireEvent.click(screen.getByRole("button", { name: "Show conversations" }));
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(screen.getByRole("dialog", { name: "Conversations" })).toBeVisible();
    expect(
      screen.getByRole("form", { name: "Question composer" }),
    ).toBeInTheDocument();
  });
  it("drags either divider within bounds and resets sizes with Enter", async () => {
    history();
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    await screen.findByText(answered.result.answer);
    const rail = screen.getByRole("separator", {
      name: "Resize conversation rail",
    });
    const pointer = (target: HTMLElement, type: string, x: number) => {
      const event = new Event(type, { bubbles: true });
      Object.assign(event, { clientX: x, pointerId: 7, button: 0 });
      fireEvent(target, event);
    };
    pointer(rail, "pointerdown", 252);
    pointer(rail, "pointermove", 350);
    pointer(rail, "pointerup", 350);
    expect(rail).toHaveAttribute("aria-valuenow", "350");
    const evidence = screen.getByRole("separator", {
      name: "Resize evidence inspector",
    });
    pointer(evidence, "pointerdown", 1064);
    pointer(evidence, "pointermove", 1100);
    pointer(evidence, "pointerup", 1100);
    expect(evidence).toHaveAttribute("aria-valuenow", "340");
    fireEvent.keyDown(evidence, { key: "Enter" });
    expect(evidence).toHaveAttribute("aria-valuenow", "376");
    fireEvent.keyDown(rail, { key: "End" });
    expect(rail).toHaveAttribute("aria-valuenow", "400");
  });
  it("does not persist preferences without a validated identity scope", async () => {
    history();
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    await screen.findByText(answered.result.answer);
    sessionStorage.setItem("unrelated-feature", "keep");
    fireEvent.click(screen.getByRole("button", { name: "Collapse rail" }));
    expect(sessionStorage.length).toBe(1);
    expect(sessionStorage.getItem("unrelated-feature")).toBe("keep");
  });
  it("selects the exact citation array of an earlier turn even when a later version is in history", async () => {
    const newer = {
      ...answered,
      id: "new",
      sequence: 2,
      result: {
        ...answered.result,
        citations: [
          {
            ...citation,
            document_version_id: "current-v2",
            excerpt: "Replacement excerpt from newer version",
          },
        ],
      },
    };
    history([answered, newer]);
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    const earlier = await screen.findByRole("listitem", { name: "Question 1" });
    fireEvent.click(
      within(earlier).getByRole("button", { name: /citation 1/i }),
    );
    const inspector = screen.getByRole("complementary", { name: /evidence/i });
    expect(within(inspector).getByText(citation.excerpt)).toBeVisible();
    expect(
      within(inspector).queryByText("Replacement excerpt from newer version"),
    ).not.toBeInTheDocument();
  });
});

describe("rail mutations and stale scope", () => {
  it.each([undefined, -1, NaN, 1.5])(
    "does not authorize Workspace restoration with revision %s",
    async (revision) => {
      history();
      render(
        <ConversationView
          workspaceId="w"
          workspaceArchived
          workspaceRevision={revision}
          conversation={conversation}
        />,
      );
      const button = screen.getByRole("button", { name: "Restore workspace" });
      expect(button).toBeDisabled();
      fireEvent.click(button);
      expect(
        vi.mocked(fetch).mock.calls.some(([, init]) => init?.method === "POST"),
      ).toBe(false);
    },
  );
  it.each([401, 403, 409, 412])(
    "keeps the archived Workspace on restore response %s",
    async (status) => {
      history();
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string) =>
          url.endsWith("/restore")
            ? new Response("{}", { status })
            : new Response(
                JSON.stringify({ items: [answered], next_cursor: null }),
              ),
        ),
      );
      render(
        <ConversationView
          workspaceId="w"
          workspaceArchived
          workspaceRevision={17}
          conversation={conversation}
        />,
      );
      await screen.findByText(answered.result.answer);
      fireEvent.click(
        screen.getByRole("button", { name: "Restore workspace" }),
      );
      await screen.findByText(
        status === 401
          ? "Your session has expired. Sign in again, then reload this page."
          : "Unable to restore Workspace. Reload and retry.",
      );
      expect(screen.getByText("Archived workspace · Read-only")).toBeVisible();
      expect(screen.queryByLabelText("Question")).not.toBeInTheDocument();
      expect(push).not.toHaveBeenCalled();
      expect(
        vi
          .mocked(fetch)
          .mock.calls.filter(
            ([url]) =>
              String(url).includes("/conversations/") &&
              String(url).endsWith("/restore"),
          ),
      ).toHaveLength(0);
      if (status === 401)
        expect(
          screen.getByRole("button", { name: "Restore workspace" }),
        ).toBeDisabled();
    },
  );
  it("explains recovery after successful Workspace restore when resolution fails", async () => {
    history();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.endsWith("/restore")
          ? new Response(
              JSON.stringify({ id: "w", archived: false, revision: 18 }),
            )
          : url.endsWith("/resolve")
            ? new Response("{}", { status: 503 })
            : new Response(
                JSON.stringify({ items: [answered], next_cursor: null }),
              ),
      ),
    );
    render(
      <ConversationView
        workspaceId="w"
        workspaceArchived
        workspaceRevision={17}
        conversation={conversation}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Restore workspace" }));
    await screen.findByText(
      "Workspace restored. Reload to select an active Workspace.",
    );
    expect(
      screen.getByRole("button", { name: "Restore workspace" }),
    ).toBeDisabled();
    expect(screen.queryByLabelText("Question")).not.toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
  it("keeps the Conversation archived after the Workspace is authoritatively restored", async () => {
    history();
    const archived = { ...conversation, archived: true };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url === "/api/v1/workspaces/w/restore"
          ? new Response(
              JSON.stringify({ id: "w", archived: false, revision: 18 }),
            )
          : url.endsWith("/resolve")
            ? new Response(
                JSON.stringify({ state: "ACTIVE", workspace: { id: "w" } }),
              )
            : url === "/api/workspace-selection"
              ? new Response("{}")
              : url.endsWith("/restore")
                ? new Response(JSON.stringify({ ...conversation, revision: 4 }))
                : new Response(
                    JSON.stringify({ items: [answered], next_cursor: null }),
                  ),
      ),
    );
    const view = render(
      <ConversationView
        workspaceId="w"
        workspaceArchived
        workspaceRevision={17}
        conversation={archived}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Restore workspace" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/workspaces/w"));
    expect(screen.queryByLabelText("Question")).not.toBeInTheDocument();
    view.rerender(
      <ConversationView
        workspaceId="w"
        workspaceArchived={false}
        workspaceRevision={18}
        conversation={archived}
      />,
    );
    expect(screen.getByText("Archived conversation · Read-only")).toBeVisible();
    expect(screen.queryByLabelText("Question")).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Restore conversation" }),
    );
    await screen.findByLabelText("Question");
    expect(
      vi
        .mocked(fetch)
        .mock.calls.filter(([url]) =>
          String(url).endsWith("/conversations/c/restore"),
        ),
    ).toHaveLength(1);
  });
  it("renders the same revision-based Workspace restore control in the list hub", () => {
    history();
    render(
      <ConversationHub
        workspaceId="w"
        workspaceName="Authorized"
        workspaceArchived
        workspaceRevision={17}
        initialConversations={[]}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Restore workspace" }),
    ).toBeEnabled();
  });
  it("accepts a server-validated zero Workspace revision", () => {
    history();
    render(
      <ConversationHub
        workspaceId="w"
        workspaceName="Authorized"
        workspaceArchived
        workspaceRevision={0}
        initialConversations={[]}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Restore workspace" }),
    ).toBeEnabled();
  });
  it("ignores the previous Hub Workspace restore after switching scope", async () => {
    history();
    let complete!: (response: Response) => void;
    const requests: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        requests.push(url);
        if (url.endsWith("/restore"))
          return new Promise<Response>((resolve) => {
            complete = resolve;
          });
        return new Response(JSON.stringify({ items: [], next_cursor: null }));
      }),
    );
    const view = render(
      <ConversationHub
        workspaceId="w"
        workspaceName="Old"
        workspaceArchived
        workspaceRevision={17}
        initialConversations={[]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Restore workspace" }));
    view.rerender(
      <ConversationHub
        workspaceId="new"
        workspaceName="New"
        workspaceArchived
        workspaceRevision={3}
        initialConversations={[]}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Restore workspace" }),
    ).toBeEnabled();
    await act(async () =>
      complete(
        new Response(
          JSON.stringify({ id: "w", archived: false, revision: 18 }),
        ),
      ),
    );
    expect(push).not.toHaveBeenCalled();
    expect(requests).not.toContain("/api/v1/workspaces/resolve");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
  it("resets Hub restore state on a new validated Workspace revision", async () => {
    history();
    let complete!: (response: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.endsWith("/restore")
          ? new Promise<Response>((resolve) => {
              complete = resolve;
            })
          : new Response(JSON.stringify({ items: [], next_cursor: null })),
      ),
    );
    const view = render(
      <ConversationHub
        workspaceId="w"
        workspaceName="Old"
        workspaceArchived
        workspaceRevision={17}
        initialConversations={[]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Restore workspace" }));
    view.rerender(
      <ConversationHub
        workspaceId="w"
        workspaceName="Old"
        workspaceArchived
        workspaceRevision={20}
        initialConversations={[]}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Restore workspace" }),
    ).toBeEnabled();
    await act(async () =>
      complete(
        new Response(
          JSON.stringify({ id: "w", archived: false, revision: 18 }),
        ),
      ),
    );
    expect(push).not.toHaveBeenCalled();
  });
  it.each([
    { id: "other", archived: false, revision: 18 },
    { id: "w", archived: true, revision: 18 },
    { id: "w", archived: false, revision: 17 },
  ])(
    "rejects an invalid restored Workspace projection %j",
    async (projection) => {
      history();
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string) =>
          url.endsWith("/restore")
            ? new Response(JSON.stringify(projection))
            : new Response(
                JSON.stringify({ items: [answered], next_cursor: null }),
              ),
        ),
      );
      render(
        <ConversationView
          workspaceId="w"
          workspaceArchived
          workspaceRevision={17}
          conversation={conversation}
        />,
      );
      fireEvent.click(
        screen.getByRole("button", { name: "Restore workspace" }),
      );
      await screen.findByText("Unable to restore Workspace. Reload and retry.");
      expect(push).not.toHaveBeenCalled();
      expect(screen.queryByLabelText("Question")).not.toBeInTheDocument();
    },
  );
  it("blocks restore when history has expired the session", async () => {
    history();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 401 })),
    );
    render(
      <ConversationView
        workspaceId="w"
        workspaceArchived
        workspaceRevision={17}
        conversation={conversation}
      />,
    );
    await screen.findByRole("link", { name: "Sign in again" });
    const button = screen.getByRole("button", { name: "Restore workspace" });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(vi.mocked(fetch).mock.calls).toHaveLength(1);
  });
  it("restores the archived Workspace with its revision and waits for authoritative selection", async () => {
    history();
    let complete!: (response: Response) => void;
    const calls: { url: string; init: RequestInit }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit = {}) => {
        calls.push({ url, init });
        if (url === "/api/v1/workspaces/w/restore")
          return new Promise<Response>((resolve) => {
            complete = resolve;
          });
        if (url === "/api/v1/workspaces/resolve")
          return new Response(
            JSON.stringify({
              state: "ACTIVE",
              workspace: { id: "w", archived: false },
            }),
          );
        if (url === "/api/workspace-selection") return new Response("{}");
        return new Response(
          JSON.stringify({ items: [answered], next_cursor: null }),
        );
      }),
    );
    render(
      <ConversationView
        workspaceId="w"
        workspaceArchived
        workspaceRevision={17}
        conversation={conversation}
      />,
    );
    await screen.findByText(answered.result.answer);
    expect(screen.getByText("Archived workspace · Read-only")).toBeVisible();
    expect(
      screen.getByText("Restore the workspace to make changes again."),
    ).toBeVisible();
    const restore = screen.getByRole("button", { name: "Restore workspace" });
    fireEvent.click(restore);
    fireEvent.click(restore);
    expect(restore).toBeDisabled();
    expect(calls.filter((call) => call.url.endsWith("/restore"))).toHaveLength(
      1,
    );
    expect(
      new Headers(
        calls.find((call) => call.url.endsWith("/restore"))!.init.headers,
      ).get("If-Match"),
    ).toBe("17");
    expect(push).not.toHaveBeenCalled();
    await act(async () =>
      complete(
        new Response(
          JSON.stringify({ id: "w", archived: false, revision: 18 }),
        ),
      ),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/workspaces/w"));
    expect(
      JSON.parse(
        String(
          calls.find((call) => call.url === "/api/v1/workspaces/resolve")!.init
            .body,
        ),
      ),
    ).toEqual({ hint_id: "w" });
    expect(
      JSON.parse(
        String(
          calls.find((call) => call.url === "/api/workspace-selection")!.init
            .body,
        ),
      ),
    ).toEqual({ workspaceId: "w" });
    expect(screen.queryByLabelText("Question")).not.toBeInTheDocument();
  });
  it("updates the current conversation to read-only when its rail action archives it", async () => {
    history();
    vi.stubGlobal("confirm", () => true);
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async (url: string, init: RequestInit = {}) =>
          new Response(
            JSON.stringify(
              url.endsWith("/archive")
                ? { ...conversation, archived: true, revision: 4 }
                : { items: [answered], next_cursor: null },
            ),
          ),
      ),
    );
    render(<ConversationView workspaceId="w" conversation={conversation} />);
    await screen.findByText(answered.result.answer);
    fireEvent.click(
      screen.getByRole("button", {
        name: "Actions for Annual reporting structure",
      }),
    );
    fireEvent.click(screen.getByRole("menuitem", { name: "Archive" }));
    await screen.findByText("Archived conversation · Read-only");
    expect(screen.queryByLabelText("Question")).not.toBeInTheDocument();
  });
  it("ignores a pending poll from a previous conversation after switching routes", async () => {
    let finish: (response: Response) => void = () => {};
    const pending = { ...answered, status: "pending", result: null };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/other/"))
          return new Response(JSON.stringify({ items: [], next_cursor: null }));
        if (url.endsWith("/turns/t"))
          return new Promise<Response>((resolve) => {
            finish = resolve;
          });
        return new Response(
          JSON.stringify({ items: [pending], next_cursor: null }),
        );
      }),
    );
    const view = render(
      <ConversationView workspaceId="w" conversation={conversation} />,
    );
    await screen.findByText("Processing question…");
    view.rerender(
      <ConversationView
        workspaceId="w"
        conversation={{ ...conversation, id: "other" }}
      />,
    );
    await screen.findByRole("button", { name: "Summarize this workspace" });
    finish(new Response(JSON.stringify(answered)));
    await waitFor(() =>
      expect(
        screen.queryByText(answered.result.answer),
      ).not.toBeInTheDocument(),
    );
  });
});
