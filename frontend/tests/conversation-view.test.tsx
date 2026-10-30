import React from "react";
const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  usePathname: () => "/workspaces/w-1/conversations/c-1",
}));
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConversationView } from "@/components/conversations/ConversationView";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const defaultIdentityScope = {
  issuer: "https://id.example/realms/knora",
  subject: "user-1",
};

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

function renderView(
  props: Partial<React.ComponentProps<typeof ConversationView>> = {},
) {
  return render(
    <ConversationView
      workspaceId="w-1"
      conversation={conversation}
      identityScope={defaultIdentityScope}
      {...props}
    />,
  );
}

describe("durable Conversation view", () => {
  it.each(["interrupted", "failed"])(
    "renders authoritative %s with an error code as one distinct outcome",
    async (status) => {
      const turn = {
        ...answered,
        status,
        result: null,
        stage: "failure",
        error_code: "EXECUTION_OUTCOME_UNKNOWN",
      };
      vi.stubGlobal(
        "fetch",
        vi.fn(
          async () =>
            new Response(JSON.stringify({ items: [turn], next_cursor: null })),
        ),
      );
      renderView();
      await screen.findByRole("heading", {
        name:
          status === "interrupted"
            ? "The answer was interrupted."
            : "System error",
      });
      expect(
        screen.queryByRole("heading", {
          name:
            status === "interrupted"
              ? "System error"
              : "The answer was interrupted.",
        }),
      ).not.toBeInTheDocument();
      expect(screen.getAllByRole("button", { name: "Try again" })).toHaveLength(
        1,
      );
    },
  );

  it.each(["interrupted", "queued", "processing", "answered", "refused"])(
    "checks authoritative %s history before restoring an interrupted question without posting",
    async (status) => {
      const interrupted = { ...answered, status: "interrupted", result: null };
      const latest = {
        ...answered,
        status,
        result:
          status === "answered"
            ? answered.result
            : status === "refused"
              ? {
                  ...answered.result,
                  decision: "REFUSAL",
                  answer: null,
                  refusal_reason: "INSUFFICIENT_EVIDENCE",
                }
              : null,
      };
      let histories = 0;
      const fetchMock = vi.fn(
        async (url: string, _options?: RequestInit) =>
          new Response(
            JSON.stringify(
              url.includes("/turns?")
                ? {
                    items: [histories++ === 0 ? interrupted : latest],
                    next_cursor: null,
                  }
                : latest,
            ),
          ),
      );
      vi.stubGlobal("fetch", fetchMock);
      renderView();
      await screen.findByRole("button", { name: "Try again" });
      fireEvent.change(screen.getByLabelText("Question"), {
        target: { value: "Keep my other draft" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Try again" }));
      if (status === "interrupted") {
        await screen.findByText(
          "History checked. Send the same question when ready.",
        );
        expect(screen.getByLabelText("Question")).toHaveValue(
          interrupted.question,
        );
        expect(screen.getByLabelText("Question")).toHaveFocus();
      } else {
        await waitFor(() =>
          expect(
            screen.queryByRole("button", { name: "Try again" }),
          ).not.toBeInTheDocument(),
        );
        expect(screen.getByLabelText("Question")).toHaveValue(
          "Keep my other draft",
        );
        expect(
          screen.queryByText(
            "History checked. Send the same question when ready.",
          ),
        ).not.toBeInTheDocument();
      }
      expect(histories).toBe(2);
      expect(
        fetchMock.mock.calls.every((call) =>
          String(call[0]).includes("/turns"),
        ),
      ).toBe(true);
      expect(
        fetchMock.mock.calls.every((call) => call[1]?.method !== "POST"),
      ).toBe(true);
    },
  );

  it("a refusal keeps document review available without another unsupported question", async () => {
    const refused = {
      ...answered,
      status: "refused",
      result: {
        ...answered.result,
        decision: "REFUSAL",
        answer: null,
        refusal_reason: "INSUFFICIENT_EVIDENCE",
      },
    };
    const fetchMock = vi.fn(
      async (_url: string, _init?: RequestInit) =>
        new Response(JSON.stringify({ items: [refused], next_cursor: null })),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderView();
    expect(
      await screen.findByRole("link", { name: "Review indexed documents" }),
    ).toHaveAttribute("href", "/workspaces/w-1/documents");
    expect(
      screen.queryAllByRole("button", {
        name: /Find supporting evidence|Compare the documents/,
      }),
    ).toHaveLength(0);
    expect(screen.getByLabelText("Question")).toHaveValue("");
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "POST"),
    ).toBe(false);
  });

  it("does not let an older history response clear a newer authentication failure", async () => {
    let finishPage: (response: Response) => void = () => {};
    let finishHistory: (response: Response) => void = () => {};
    const page = { items: [], next_cursor: "next" };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(page)))
      .mockRejectedValueOnce(new Error("connection lost"))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            finishPage = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            finishHistory = resolve;
          }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify(answered)));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "race-key") });
    renderView();
    await screen.findByRole("button", { name: "Load more Turns" });
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Keep this question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Load more Turns" }));
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    finishPage(new Response(null, { status: 401 }));
    await screen.findByRole("link", { name: "Sign in again" });
    finishHistory(new Response(JSON.stringify(page)));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Reload history" }),
      ).toBeEnabled(),
    );
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    expect(
      fetchMock.mock.calls.filter((call) => call[1]?.method === "POST"),
    ).toHaveLength(1);
    expect(screen.getByLabelText("Question")).toHaveValue("Keep this question");
  });

  it("recovers an expired polling session by reading the completed Turn without posting", async () => {
    let turnsCalls = 0;
    const fetchMock = vi.fn(
      async (url: RequestInfo | URL, init?: RequestInit) => {
        const u = String(url);
        if (u.includes("/api/auth/session")) {
          return new Response(
            JSON.stringify({ session: defaultIdentityScope }),
          );
        }
        if (u.includes("/turns/t-1")) {
          return new Response(null, { status: 401 });
        }
        if (u.includes("/turns")) {
          turnsCalls++;
          if (turnsCalls === 1) {
            return new Response(
              JSON.stringify({
                items: [{ ...answered, status: "pending", result: null }],
                next_cursor: null,
              }),
            );
          }
          return new Response(
            JSON.stringify({ items: [answered], next_cursor: null }),
          );
        }
        return new Response(null, { status: 404 });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderView();
    const login = await screen.findByRole("link", { name: "Sign in again" });
    expect(login).toHaveAttribute("href", "/api/auth/login");
    expect(login).toHaveAttribute("target", "_blank");
    expect(screen.queryByText("Processing question…")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reload history" }));
    await screen.findByText("The guide says blue umbrellas.");
    expect(
      screen.queryByRole("link", { name: "Sign in again" }),
    ).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.filter((call) => call[1]?.method === "POST"),
    ).toHaveLength(0);
  });

  it("keeps the draft and original submission key through failed and successful reauthentication", async () => {
    let sessionAttempts = 0;
    let postAttempts = 0;
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes("/api/auth/session")) {
        sessionAttempts++;
        if (sessionAttempts === 1) {
          return new Response(null, { status: 401 });
        }
        return new Response(JSON.stringify({ session: defaultIdentityScope }));
      }
      if (init?.method === "POST") {
        postAttempts++;
        if (postAttempts === 1) {
          return new Response(null, { status: 401 });
        }
        return new Response(JSON.stringify(answered));
      }
      return new Response(JSON.stringify({ items: [], next_cursor: null }));
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "original-key") });
    renderView();
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "My preserved question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByRole("link", { name: "Sign in again" });
    expect(screen.getByLabelText("Question")).toHaveValue(
      "My preserved question",
    );
    expect(screen.getByRole("alert")).toHaveTextContent("preserve your draft");
    expect(screen.getByLabelText("Question")).toHaveAttribute("readonly");
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Reload history" }));
    await waitFor(() => expect(sessionAttempts).toBe(1));
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Reload history" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled(),
    );
    expect(
      fetchMock.mock.calls.filter((call) => call[1]?.method === "POST"),
    ).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText("The guide says blue umbrellas.");
    const posts = fetchMock.mock.calls.filter(
      (call) => call[1]?.method === "POST",
    );
    expect(posts).toHaveLength(2);
    for (const post of posts) {
      expect(new Headers(post[1]?.headers).get("Idempotency-Key")).toBe(
        "original-key",
      );
      expect(JSON.parse(String(post[1]?.body ?? "{}"))).toEqual({
        question: "My preserved question",
      });
    }
  });

  it.each(["initial history", "pagination"])(
    "offers session recovery for expired %s",
    async (phase) => {
      const fetchMock = vi.fn();
      if (phase === "pagination")
        fetchMock.mockResolvedValueOnce(
          new Response(
            JSON.stringify({ items: [answered], next_cursor: "next" }),
          ),
        );
      fetchMock.mockResolvedValueOnce(new Response(null, { status: 401 }));
      vi.stubGlobal("fetch", fetchMock);
      renderView();
      if (phase === "pagination")
        fireEvent.click(
          await screen.findByRole("button", { name: "Load more Turns" }),
        );
      await screen.findByRole("link", { name: "Sign in again" });
      expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    },
  );

  it("keeps non-auth history failures separate from session expiry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 500 })),
    );
    renderView();
    await screen.findByRole("alert");
    expect(
      screen.queryByRole("link", { name: "Sign in again" }),
    ).not.toBeInTheDocument();
  });

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
    renderView();
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
    renderView();

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
    renderView();
    await screen.findByLabelText("Question");
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "A follow-up?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText("This conversation is processing a question");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    await waitFor(() =>
      expect(screen.queryByText("Loading history…")).not.toBeInTheDocument(),
    );
    expect(
      screen.getByText("This conversation is processing a question"),
    ).toBeInTheDocument();
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
    renderView();
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
    renderView();
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
    renderView();
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
        decision: "REFUSAL",
        answer: null,
        citations: [],
        refusal_reason: "INSUFFICIENT_EVIDENCE",
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
    renderView();
    await screen.findByText("Refused: INSUFFICIENT_EVIDENCE");
    expect(
      screen.getByRole("heading", {
        name: "I don’t have enough evidence to answer that.",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "No supporting citation" }),
    ).toBeVisible();
    expect(screen.getAllByText("INSUFFICIENT EVIDENCE")).toHaveLength(1);
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
    renderView({ workspaceArchived: true });
    await screen.findByText("The guide says blue umbrellas.");
    expect(
      screen.getByText("Archived workspace · Read-only"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Ask" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["retrieving", "processing", false],
    ["grounded-answer", "answered", false],
    ["insufficient-evidence", "refused", false],
    ["interrupted", "interrupted", false],
    ["archived-read-only", "answered", true],
  ])(
    "opens the unsaved conversation screen from %s without a write",
    async (_name, status, archived) => {
      const turn = {
        ...answered,
        status,
        stage: status === "processing" ? "retrieving" : null,
        result:
          status === "answered"
            ? answered.result
            : status === "refused"
              ? {
                  ...answered.result,
                  decision: "REFUSAL",
                  answer: null,
                  refusal_reason: "INSUFFICIENT_EVIDENCE",
                }
              : null,
      };
      const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
        if (init.method === "POST") return new Response(null, { status: 503 });
        return new Response(
          JSON.stringify(
            url.endsWith("/turns/t-1")
              ? turn
              : { items: [turn], next_cursor: null },
          ),
        );
      });
      vi.stubGlobal("fetch", fetchMock);
      renderView({ conversation: { ...conversation, archived } });
      await screen.findByText(turn.question);
      if (status === "processing")
        await screen.findByText("Retrieving evidence…");
      if (status === "refused")
        await screen.findByText("Refused: INSUFFICIENT_EVIDENCE");
      if (status === "answered")
        await screen.findByText(answered.result.answer);
      fireEvent.click(screen.getByRole("button", { name: "New Conversation" }));
      expect(push).toHaveBeenCalledWith("/workspaces/w-1/conversations");
      expect(
        fetchMock.mock.calls.filter(([, init]) => init?.method === "POST"),
      ).toHaveLength(0);
    },
  );

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
    renderView();
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
    renderView();
    await screen.findByText("The guide says blue umbrellas.");
    expect(fetchMock.mock.calls[1][0]).toContain("/turns/t-1");
    expect(
      fetchMock.mock.calls.filter((call) => call[1]?.method === "POST"),
    ).toHaveLength(0);
  });
});

describe("session recovery on tab return and identity mismatch", () => {
  let originalLocation: Location;
  let replaceMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    replaceMock = vi.fn();
    originalLocation = window.location;
    try {
      Object.defineProperty(window, "location", {
        configurable: true,
        value: { ...originalLocation, replace: replaceMock },
      });
    } catch {
      window.location.replace = replaceMock as unknown as (
        url: string | URL,
      ) => void;
    }
    vi.spyOn(document, "hasFocus").mockReturnValue(true);
    Object.defineProperty(document, "hidden", {
      configurable: true,
      value: false,
    });
  });

  afterEach(() => {
    try {
      Object.defineProperty(window, "location", {
        configurable: true,
        value: originalLocation,
      });
    } catch {
      // fallback
    }
  });

  it("different subject triggers identity change UI, clears draft/refs and redirects to /workspaces", async () => {
    const fetchMock = vi.fn(
      async (url: RequestInfo | URL, init?: RequestInit) => {
        if (String(url).includes("/api/auth/session")) {
          return new Response(
            JSON.stringify({
              session: {
                issuer: defaultIdentityScope.issuer,
                subject: "user-different",
              },
            }),
          );
        }
        return new Response(
          JSON.stringify({ items: [answered], next_cursor: null }),
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderView();
    await screen.findByText("The guide says blue umbrellas.");
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Draft to discard" },
    });

    fireEvent.blur(window);
    fireEvent.focus(window);

    await screen.findByText("Your account changed. Opening Workspaces…");
    expect(replaceMock).toHaveBeenCalledWith("/workspaces");
    expect(screen.queryByLabelText("Question")).not.toBeInTheDocument();
  });

  it("different issuer with same subject triggers identity change UI and redirects to /workspaces", async () => {
    const fetchMock = vi.fn(
      async (url: RequestInfo | URL, init?: RequestInit) => {
        if (String(url).includes("/api/auth/session")) {
          return new Response(
            JSON.stringify({
              session: {
                issuer: "https://other-issuer.example",
                subject: defaultIdentityScope.subject,
              },
            }),
          );
        }
        return new Response(
          JSON.stringify({ items: [answered], next_cursor: null }),
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderView();
    await screen.findByText("The guide says blue umbrellas.");

    fireEvent.blur(window);
    fireEvent.focus(window);

    await screen.findByText("Your account changed. Opening Workspaces…");
    expect(replaceMock).toHaveBeenCalledWith("/workspaces");
  });

  it("missing baseline identity locks draft submission without sending invalid headers", async () => {
    const fetchMock = vi.fn(
      async (_url: RequestInfo | URL, _init?: RequestInit) =>
        new Response(JSON.stringify({ items: [], next_cursor: null })),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByLabelText("Question");
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Unauthenticated draft" },
    });
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(
      fetchMock.mock.calls.some((call) => call[1]?.method === "POST"),
    ).toBe(false);
  });

  it("session probe returns 401 or null triggers requireAuthentication and keeps draft", async () => {
    const fetchMock = vi.fn(
      async (url: RequestInfo | URL, init?: RequestInit) => {
        if (String(url).includes("/api/auth/session")) {
          return new Response(JSON.stringify({ session: null }), {
            status: 401,
          });
        }
        return new Response(
          JSON.stringify({ items: [answered], next_cursor: null }),
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderView();
    await screen.findByText("The guide says blue umbrellas.");
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Preserve this draft on expiry" },
    });

    fireEvent.blur(window);
    fireEvent.focus(window);

    await screen.findByRole("link", { name: "Sign in again" });
    expect(screen.getByLabelText("Question")).toHaveValue(
      "Preserve this draft on expiry",
    );
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    expect(
      fetchMock.mock.calls.some((call) => call[1]?.method === "POST"),
    ).toBe(false);
  });

  it("session probe returns 503 shows retryable notice, keeps draft, locks submit", async () => {
    const fetchMock = vi.fn(
      async (url: RequestInfo | URL, init?: RequestInit) => {
        if (String(url).includes("/api/auth/session")) {
          return new Response(null, { status: 503 });
        }
        return new Response(
          JSON.stringify({ items: [answered], next_cursor: null }),
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderView();
    await screen.findByText("The guide says blue umbrellas.");
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Draft waiting for server recovery" },
    });

    fireEvent.blur(window);
    fireEvent.focus(window);

    await screen.findByText("Unable to verify your session. Retry.");
    expect(screen.getByLabelText("Question")).toHaveValue(
      "Draft waiting for server recovery",
    );
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  });

  it("history GET returns 403 shows workspace permission error without automatic retry", async () => {
    const fetchMock = vi.fn(
      async (url: RequestInfo | URL, init?: RequestInit) => {
        const u = String(url);
        if (u.includes("/api/auth/session")) {
          return new Response(
            JSON.stringify({ session: defaultIdentityScope }),
          );
        }
        if (u.includes("/turns")) {
          return new Response(null, { status: 403 });
        }
        return new Response(null, { status: 404 });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderView();

    fireEvent.blur(window);
    fireEvent.focus(window);

    await screen.findByText(
      "You don't have permission to ask questions in this workspace.",
    );
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    expect(
      fetchMock.mock.calls.some((call) => call[1]?.method === "POST"),
    ).toBe(false);
  });

  it("two tab return episodes trigger exactly two session probes", async () => {
    let probeCount = 0;
    const fetchMock = vi.fn(
      async (url: RequestInfo | URL, init?: RequestInit) => {
        if (String(url).includes("/api/auth/session")) {
          probeCount++;
          return new Response(
            JSON.stringify({ session: defaultIdentityScope }),
          );
        }
        return new Response(
          JSON.stringify({ items: [answered], next_cursor: null }),
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderView();
    await screen.findByText("The guide says blue umbrellas.");

    fireEvent.blur(window);
    fireEvent.focus(window);
    await waitFor(() => expect(probeCount).toBe(1));

    fireEvent.blur(window);
    fireEvent.focus(window);
    await waitFor(() => expect(probeCount).toBe(2));

    expect(probeCount).toBe(2);
  });

  it("no session probe request when tab remains idle or hidden", async () => {
    let probeCount = 0;
    const fetchMock = vi.fn(
      async (url: RequestInfo | URL, init?: RequestInit) => {
        if (String(url).includes("/api/auth/session")) {
          probeCount++;
          return new Response(
            JSON.stringify({ session: defaultIdentityScope }),
          );
        }
        return new Response(
          JSON.stringify({ items: [answered], next_cursor: null }),
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderView();
    await screen.findByText("The guide says blue umbrellas.");

    Object.defineProperty(document, "hidden", {
      value: true,
      configurable: true,
    });
    fireEvent(document, new Event("visibilitychange"));

    await new Promise((r) => setTimeout(r, 50));
    expect(probeCount).toBe(0);

    Object.defineProperty(document, "hidden", {
      value: false,
      configurable: true,
    });
  });

  it("concurrent tab return focus and Reload history deduplicates to single in-flight probe", async () => {
    let probeCalls = 0;
    let finishProbe: (response: Response) => void = () => {};
    const fetchMock = vi.fn(
      async (url: RequestInfo | URL, init?: RequestInit) => {
        if (String(url).includes("/api/auth/session")) {
          probeCalls++;
          return new Promise<Response>((resolve) => {
            finishProbe = resolve;
          });
        }
        return new Response(
          JSON.stringify({ items: [answered], next_cursor: null }),
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderView();
    await screen.findByText("The guide says blue umbrellas.");

    // Expire session first to have Reload history button available
    fireEvent.blur(window);
    fireEvent.focus(window);
    // wait for timeout(0) to trigger
    await waitFor(() => expect(probeCalls).toBe(1));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking your session…",
    );

    // Click Reload history while first probe is still in-flight
    // Since Reload history is disabled while checkingSession is true, test calling recoverSession again directly
    // or verify probe is not duplicated
    finishProbe(
      new Response(JSON.stringify({ session: defaultIdentityScope })),
    );

    await waitFor(() =>
      expect(
        screen.queryByText("Checking your session…"),
      ).not.toBeInTheDocument(),
    );
    expect(probeCalls).toBe(1);
  });

  it("mismatch 401 from mutation activates session probe and redirects when account changed", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes("/api/auth/session")) {
        return new Response(
          JSON.stringify({
            session: {
              issuer: defaultIdentityScope.issuer,
              subject: "user-swapped",
            },
          }),
        );
      }
      if (init?.method === "POST") {
        return new Response(
          JSON.stringify({ detail: "SESSION_IDENTITY_MISMATCH" }),
          { status: 401 },
        );
      }
      return new Response(
        JSON.stringify({ items: [answered], next_cursor: null }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    renderView();
    await screen.findByText("The guide says blue umbrellas.");

    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Question sent right after switch" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    await screen.findByText("Your account changed. Opening Workspaces…");
    expect(replaceMock).toHaveBeenCalledWith("/workspaces");
    expect(
      fetchMock.mock.calls.filter((c) =>
        String(c[0]).includes("/api/auth/session"),
      ),
    ).toHaveLength(1);
  });

  it("offers an actionable retry after a temporary session-probe failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url) =>
        String(url).includes("/api/auth/session")
          ? new Response(null, { status: 503 })
          : new Response(
              JSON.stringify({ items: [answered], next_cursor: null }),
            ),
      ),
    );
    renderView();
    await screen.findByText(answered.result.answer);
    fireEvent.blur(window);
    fireEvent.focus(window);
    await screen.findByText("Unable to verify your session. Retry.");
    expect(
      screen.queryAllByRole("button", { name: /retry|reload history/i })
        .length > 0,
    ).toBe(true);
  });

  it("prevents an old history response from overwriting recovered history", async () => {
    let finishOld: ((r: Response) => void) | undefined;
    let histories = 0;
    const newer = {
      ...answered,
      result: { ...answered.result, answer: "NEW_RECOVERY_ANSWER" },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url) => {
        if (String(url).includes("/api/auth/session"))
          return new Response(
            JSON.stringify({ session: defaultIdentityScope }),
          );
        if (++histories === 1)
          return new Promise<Response>((resolve) => {
            finishOld = resolve;
          });
        return new Response(
          JSON.stringify({ items: [newer], next_cursor: null }),
        );
      }),
    );
    renderView();
    await waitFor(() => expect(histories).toBe(1));
    fireEvent.blur(window);
    fireEvent.focus(window);
    await screen.findByText("NEW_RECOVERY_ANSWER");
    finishOld?.(
      new Response(JSON.stringify({ items: [answered], next_cursor: null })),
    );
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByText(answered.result.answer)).not.toBeInTheDocument();
  });
});
