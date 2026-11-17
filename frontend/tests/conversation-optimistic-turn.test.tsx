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

const conversation = {
  id: "c-1",
  workspace_id: "w-1",
  title: "Optimistic conversation",
  title_source: "manual",
  archived: false,
  revision: 1,
  updated_at: "2026-09-26T00:00:00Z",
};

describe("Conversation Optimistic Turn Submission", () => {
  it("immediately mounts the optimistic question card, verifies POST request, and reconciles server turn", async () => {
    let resolvePost: (value: Response) => void;
    const postPromise = new Promise<Response>((resolve) => {
      resolvePost = resolve;
    });

    const realTurn = {
      id: "t-real-123",
      conversation_id: "c-1",
      sequence: 1,
      question: "Where is the finance report?",
      status: "queued",
      stage: null,
      error_code: null,
      result: null,
    };

    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, options?: RequestInit) => {
        if (options?.method === "POST" && url.includes("/turns")) {
          return postPromise;
        }
        if (url.includes("/turns/t-real-123")) {
          return Promise.resolve(
            new Response(JSON.stringify(realTurn), { status: 200 }),
          );
        }
        return Promise.resolve(
          new Response(JSON.stringify({ items: [], next_cursor: null }), {
            status: 200,
          }),
        );
      });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "turn-key-opt") });

    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByLabelText("Question");

    const textarea = screen.getByLabelText("Question") as HTMLTextAreaElement;
    fireEvent.change(textarea, {
      target: { value: "Where is the finance report?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    // Verify 1: The question card is IMMEDIATELY mounted in the conversation thread!
    expect(
      screen.getByText("Where is the finance report?", { selector: "p" }),
    ).toBeInTheDocument();

    // Verify 2: The processing indicator is immediately visible!
    expect(screen.getByText("Processing question…")).toBeInTheDocument();

    // Verify 3: The draft in the textarea is IMMEDIATELY cleared!
    expect(textarea.value).toBe("");

    // Verify 4: The temporary optimistic turn ID is rendered in the DOM
    expect(
      document.querySelector('[data-turn-id^="optimistic-"]'),
    ).toBeInTheDocument();
    expect(
      document.querySelector('[data-turn-id="t-real-123"]'),
    ).not.toBeInTheDocument();

    // Verify 5: POST fetch was actually dispatched with correct payload
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/turns"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ question: "Where is the finance report?" }),
      }),
    );

    // Now resolve the server response
    resolvePost!(new Response(JSON.stringify(realTurn), { status: 202 }));

    // Verify 6: Reconciliation replaces optimistic turn with real server turn
    await waitFor(() => {
      expect(
        document.querySelector('[data-turn-id="t-real-123"]'),
      ).toBeInTheDocument();
      expect(
        document.querySelector('[data-turn-id^="optimistic-"]'),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText("Where is the finance report?", { selector: "p" }),
      ).toBeInTheDocument();
      expect(screen.getByText("Processing question…")).toBeInTheDocument();
    });
  });

  it("rolls back the optimistic turn and restores the draft if turn submission fails", async () => {
    let rejectPost: (reason?: unknown) => void;
    const postPromise = new Promise<Response>((_, reject) => {
      rejectPost = reject;
    });

    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, options?: RequestInit) => {
        if (options?.method === "POST" && url.includes("/turns")) {
          return postPromise;
        }
        return Promise.resolve(
          new Response(JSON.stringify({ items: [], next_cursor: null }), {
            status: 200,
          }),
        );
      });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "turn-key-rollback") });

    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByLabelText("Question");

    const textarea = screen.getByLabelText("Question") as HTMLTextAreaElement;
    fireEvent.change(textarea, {
      target: { value: "Important query to restore" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    // Optimistic turn mounted
    expect(
      screen.getByText("Important query to restore", { selector: "p" }),
    ).toBeInTheDocument();
    expect(
      document.querySelector('[data-turn-id^="optimistic-"]'),
    ).toBeInTheDocument();
    expect(textarea.value).toBe("");

    // Simulate network error
    rejectPost!(new Error("Network connection lost"));

    // Verify: Optimistic turn is removed, and draft is restored so user doesn't lose data
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(textarea.value).toBe("Important query to restore");
      expect(
        screen.queryByText("Important query to restore", { selector: "p" }),
      ).not.toBeInTheDocument();
      expect(
        document.querySelector('[data-turn-id^="optimistic-"]'),
      ).not.toBeInTheDocument();
    });
  });

  it("rolls back optimistic turn and restores draft on 409 CONVERSATION_BUSY", async () => {
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
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "turn-key-busy") });

    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByLabelText("Question");

    const textarea = screen.getByLabelText("Question") as HTMLTextAreaElement;
    fireEvent.change(textarea, {
      target: { value: "Concurrent question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() => {
      expect(
        screen.getByText("This conversation is processing a question"),
      ).toBeInTheDocument();
      expect(textarea.value).toBe("Concurrent question");
      expect(
        screen.queryByText("Concurrent question", { selector: "p" }),
      ).not.toBeInTheDocument();
      expect(
        document.querySelector('[data-turn-id^="optimistic-"]'),
      ).not.toBeInTheDocument();
    });
  });

  it("preserves pending optimistic turn when load refreshes history on retry after error", async () => {
    const initialTurn = {
      id: "t-past-0",
      conversation_id: "c-1",
      sequence: 1,
      question: "Initial greeting",
      status: "completed",
      stage: null,
      error_code: null,
      result: { decision: "ANSWER", answer: "Hello there!", citations: [] },
    };

    const realTurn = {
      id: "t-real-retry",
      conversation_id: "c-1",
      sequence: 2,
      question: "Retry question",
      status: "queued",
      stage: null,
      error_code: null,
      result: null,
    };

    let postCallCount = 0;
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, options?: RequestInit) => {
        if (options?.method === "POST" && url.includes("/turns")) {
          postCallCount++;
          if (postCallCount === 1) {
            // First attempt fails with network error
            return Promise.reject(new Error("Transient connection error"));
          }
          // Second attempt succeeds
          return Promise.resolve(
            new Response(JSON.stringify(realTurn), { status: 202 }),
          );
        }
        if (url.includes("/turns/t-real-retry")) {
          return Promise.resolve(
            new Response(JSON.stringify(realTurn), { status: 200 }),
          );
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({ items: [initialTurn], next_cursor: null }),
            { status: 200 },
          ),
        );
      });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "turn-key-retry") });

    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByText("Initial greeting");

    const textarea = screen.getByLabelText("Question") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "Retry question" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    // First attempt fails -> error alert appears, draft is restored
    await screen.findByRole("alert");
    expect(textarea.value).toBe("Retry question");

    // Click Ask again to trigger retry flow (submitKey.current && error is set)
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    // Optimistic turn is mounted immediately
    expect(
      screen.getByText("Retry question", { selector: "p" }),
    ).toBeInTheDocument();
    expect(
      document.querySelector('[data-turn-id^="optimistic-"]'),
    ).toBeInTheDocument();

    // After retry completes, both the past turn and the reconciled turn are present
    await waitFor(() => {
      expect(
        document.querySelector('[data-turn-id="t-real-retry"]'),
      ).toBeInTheDocument();
      expect(
        document.querySelector('[data-turn-id="t-past-0"]'),
      ).toBeInTheDocument();
      expect(
        document.querySelector('[data-turn-id^="optimistic-"]'),
      ).not.toBeInTheDocument();
    });
  });

  it("aborts and rolls back optimistic turn when turn submission times out", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, options?: RequestInit) => {
        if (options?.method === "POST" && url.includes("/turns")) {
          return new Promise<Response>((_, reject) => {
            if (options?.signal?.aborted) {
              reject(
                new DOMException("The operation was aborted", "AbortError"),
              );
            } else if (options?.signal) {
              options.signal.addEventListener("abort", () => {
                reject(
                  new DOMException("The operation was aborted", "AbortError"),
                );
              });
            }
          });
        }
        return Promise.resolve(
          new Response(JSON.stringify({ items: [], next_cursor: null }), {
            status: 200,
          }),
        );
      });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "turn-key-timeout") });

    render(
      <ConversationView
        workspaceId="w-1"
        conversation={conversation}
        submissionTimeoutMs={50}
      />,
    );
    await screen.findByLabelText("Question");

    const textarea = screen.getByLabelText("Question") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "Stalled question" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    // Optimistic turn mounted initially
    expect(
      screen.getByText("Stalled question", { selector: "p" }),
    ).toBeInTheDocument();
    expect(
      document.querySelector('[data-turn-id^="optimistic-"]'),
    ).toBeInTheDocument();
    expect(textarea.value).toBe("");

    // Wait for the 50ms timeout to trigger abort -> rollback, draft restored, alert displayed
    await waitFor(
      () => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
        expect(textarea.value).toBe("Stalled question");
        expect(
          screen.queryByText("Stalled question", { selector: "p" }),
        ).not.toBeInTheDocument();
        expect(
          document.querySelector('[data-turn-id^="optimistic-"]'),
        ).not.toBeInTheDocument();
      },
      { timeout: 2000 },
    );

    // Busy state is released: Ask button is re-enabled
    const askButton = screen.getByRole("button", { name: "Ask" });
    expect(askButton).not.toBeDisabled();
  });
});
