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
  it("immediately mounts the optimistic question card, shows processing indicator, and clears input before POST resolves", async () => {
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
      screen.getByText("Where is the finance report?"),
    ).toBeInTheDocument();

    // Verify 2: The processing indicator is immediately visible!
    expect(screen.getByText("Processing question…")).toBeInTheDocument();

    // Verify 3: The draft in the textarea is IMMEDIATELY cleared!
    expect(textarea.value).toBe("");

    // Now resolve the server response
    resolvePost!(new Response(JSON.stringify(realTurn), { status: 202 }));

    // Verify 4: The question remains visible after server reconciliation
    await waitFor(() => {
      expect(
        screen.getByText("Where is the finance report?"),
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
    expect(screen.getByText("Important query to restore")).toBeInTheDocument();
    expect(textarea.value).toBe("");

    // Simulate network error
    rejectPost!(new Error("Network connection lost"));

    // Verify: Optimistic turn is removed, and draft is restored so user doesn't lose data
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(textarea.value).toBe("Important query to restore");
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
    });
  });
});
