import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationView } from "@/components/conversations/ConversationView";

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
  revision: 1,
  updated_at: "2026-09-26T00:00:00Z",
};

const answered = {
  id: "t-1",
  conversation_id: "c-1",
  sequence: 1,
  question: "What does the guide say?",
  status: "answered",
  stage: null,
  error_code: null,
  result: {
    decision: "ANSWER",
    answer: "The guide says blue umbrellas.",
    citations: [],
    refusal_reason: null,
    trace_id: "trace-1",
    workspace_id: "w-1",
  },
};

describe("durable Conversation view", () => {
  it("locks the draft while a Turn submission is in flight", async () => {
    let complete: ((response: Response) => void) | undefined;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: null }), {
          status: 200,
        }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            complete = resolve;
          }),
      );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "turn-key") });
    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByLabelText("Question");
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Original question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("Question")).toHaveAttribute("readonly");
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    complete?.(
      new Response(JSON.stringify({ ...answered, id: "t-new" }), {
        status: 202,
      }),
    );
  });
  it("reloads exact persisted history without submitting a new Turn", async () => {
    const fetchMock = vi.fn(
      async (_url: string, _init?: RequestInit) =>
        new Response(JSON.stringify({ items: [answered], next_cursor: null }), {
          status: 200,
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<ConversationView workspaceId="w-1" conversation={conversation} />);

    await screen.findByText("The guide says blue umbrellas.");
    expect(screen.getByText("What does the guide say?")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toContain("/turns?limit=50");
    expect(fetchMock.mock.calls[0][1]?.method).not.toBe("POST");
  });

  it("keeps the draft on 409 busy and does not create another submission", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: null }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: { code: "CONVERSATION_BUSY" } }), {
          status: 409,
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: null }), {
          status: 200,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "stable-turn-key") });
    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByLabelText("Question");
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "A follow-up?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText("This conversation is processing a question");
    expect(
      (screen.getByLabelText("Question") as HTMLTextAreaElement).value,
    ).toBe("A follow-up?");
    expect(
      fetchMock.mock.calls.filter((call) => call[1]?.method === "POST"),
    ).toHaveLength(1);
  });

  it("reuses the same Turn key after an ambiguous network failure", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: null }), {
          status: 200,
        }),
      )
      .mockRejectedValueOnce(new Error("connection lost"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: null }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ ...answered, id: "t-2", question: "Follow-up" }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn().mockReturnValueOnce("turn-key-a"),
    });
    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByLabelText("Question");
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Follow-up" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByRole("alert");
    expect(screen.getByLabelText("Question")).toHaveAttribute("readonly");
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    const submits = fetchMock.mock.calls.filter(
      (call) => call[1]?.method === "POST",
    );
    expect(submits).toHaveLength(2);
    expect(new Headers(submits[0][1].headers).get("Idempotency-Key")).toBe(
      "turn-key-a",
    );
    expect(new Headers(submits[1][1].headers).get("Idempotency-Key")).toBe(
      "turn-key-a",
    );
  });

  it("does not misreport an idempotency conflict as a busy Conversation", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: null }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ error: { code: "IDEMPOTENCY_KEY_CONFLICT" } }),
          { status: 409 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "turn-key") });
    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByLabelText("Question");
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "New question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "IDEMPOTENCY_KEY_CONFLICT",
    );
    expect(
      screen.queryByText("This conversation is processing a question"),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  });

  it("switches to read-only when the backend rejects an archived Workspace", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: null }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ error: { code: "WORKSPACE_ARCHIVED" } }),
          { status: 409 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "turn-key") });
    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByLabelText("Question");
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "New question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText("This Conversation is read-only.");
    expect(
      screen.queryByRole("button", { name: "Ask" }),
    ).not.toBeInTheDocument();
  });

  it("shows a persisted refused Turn as a refusal, not an answer", async () => {
    const refused = {
      ...answered,
      id: "t-refused",
      status: "refused",
      result: {
        ...answered.result,
        decision: "REFUSE",
        answer: null,
        refusal_reason: "insufficient_evidence",
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ items: [refused], next_cursor: null }),
            { status: 200 },
          ),
      ),
    );
    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByText("Refused: insufficient_evidence");
    expect(
      screen.queryByText("The guide says blue umbrellas."),
    ).not.toBeInTheDocument();
  });

  it("keeps archived Conversation history readable and hides submission", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ items: [answered], next_cursor: null }),
            { status: 200 },
          ),
      ),
    );
    render(
      <ConversationView
        workspaceId="w-1"
        conversation={conversation}
        workspaceArchived
      />,
    );
    await screen.findByText("The guide says blue umbrellas.");
    expect(
      screen.getByText("This Conversation is read-only."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Ask" }),
    ).not.toBeInTheDocument();
  });

  it("paginates persisted Turns without posting a new question", async () => {
    const older = {
      ...answered,
      id: "t-2",
      sequence: 2,
      question: "Second question",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ items: [answered], next_cursor: "turn-next" }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [older], next_cursor: null }), {
          status: 200,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByText("What does the guide say?");
    fireEvent.click(screen.getByRole("button", { name: "Load more Turns" }));
    await screen.findByText("Second question");
    expect(fetchMock.mock.calls[1][0]).toContain("cursor=turn-next");
    expect(
      fetchMock.mock.calls.filter((call) => call[1]?.method === "POST"),
    ).toHaveLength(0);
  });

  it("resumes GET status after reconnect without a new POST", async () => {
    const processing = { ...answered, status: "pending", result: null };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ items: [processing], next_cursor: null }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(answered), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByText("The guide says blue umbrellas.");
    expect(fetchMock.mock.calls[1][0]).toContain("/turns/t-1");
    expect(
      fetchMock.mock.calls.filter((call) => call[1]?.method === "POST"),
    ).toHaveLength(0);
  });
});
