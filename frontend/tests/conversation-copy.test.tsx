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
import type { TurnResponse } from "@/generated/knora-openapi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const conversation = {
  id: "c-1",
  workspace_id: "w-1",
  title: "Test conversation",
  title_source: "manual",
  archived: false,
  revision: 1,
  updated_at: "2026-10-24T00:00:00Z",
};

const baseAnsweredTurn: TurnResponse = {
  id: "t-1",
  conversation_id: "c-1",
  sequence: 1,
  question: "Hướng dẫn cài đặt hệ thống?",
  status: "answered",
  stage: null,
  error_code: null,
  result: {
    decision: "ANSWER",
    answer: "Xem tài liệu hướng dẫn [[E1]] để bắt đầu.",
    citations: [
      {
        evidence_id: "E1",
        document_id: "doc-install",
        document_version_id: "ver-1",
        source_name: "Tài liệu cài đặt",
        source_key: "install.pdf",
        content_checksum: "sha-1",
        heading_path: ["Cài đặt", "Bước 1"],
        page_start: 3,
        page_end: 3,
        start_line: 1,
        end_line: 20,
        excerpt: "Bước 1: Chạy npm install",
      },
    ],
    refusal_reason: null,
    trace_id: "tr-1",
    workspace_id: "w-1",
  },
};

describe("Conversation message copy functionality", () => {
  let writeTextMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });
  });

  it("renders question copy button and copies raw question text", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ items: [baseAnsweredTurn], next_cursor: null }),
          ),
      ),
    );

    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    const copyQuestionBtn = await screen.findByRole("button", {
      name: /Sao chép câu hỏi 1|Copy question 1/i,
    });
    expect(copyQuestionBtn).toBeInTheDocument();

    fireEvent.click(copyQuestionBtn);
    expect(writeTextMock).toHaveBeenCalledWith("Hướng dẫn cài đặt hệ thống?");

    await waitFor(() => {
      expect(screen.getByText(/Đã sao chép|Copied/i)).toBeInTheDocument();
    });
  });

  it("copies answer with transformed citation links", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ items: [baseAnsweredTurn], next_cursor: null }),
          ),
      ),
    );

    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    const copyAnswerBtn = await screen.findByRole("button", {
      name: /Sao chép câu trả lời 1|Copy answer 1/i,
    });
    expect(copyAnswerBtn).toBeInTheDocument();

    fireEvent.click(copyAnswerBtn);
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith(
        expect.stringContaining(
          "[Tài liệu cài đặt, p.3](http://localhost:3000/workspaces/w-1/documents/doc-install)",
        ),
      );
    });
  });

  it("handles clipboard API rejection gracefully without crash", async () => {
    writeTextMock.mockRejectedValue(new Error("Permission denied"));

    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ items: [baseAnsweredTurn], next_cursor: null }),
          ),
      ),
    );

    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    const copyQuestionBtn = await screen.findByRole("button", {
      name: /Sao chép câu hỏi 1|Copy question 1/i,
    });

    fireEvent.click(copyQuestionBtn);
    await waitFor(() => {
      expect(
        screen.getByText(/Không thể sao chép|Copy failed/i),
      ).toBeInTheDocument();
    });
  });

  it("handles absent clipboard API safely", async () => {
    // @ts-expect-error simulating absent clipboard
    delete navigator.clipboard;

    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ items: [baseAnsweredTurn], next_cursor: null }),
          ),
      ),
    );

    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    const copyQuestionBtn = await screen.findByRole("button", {
      name: /Sao chép câu hỏi 1|Copy question 1/i,
    });

    fireEvent.click(copyQuestionBtn);
    await waitFor(() => {
      expect(
        screen.getByText(/Không thể sao chép|Copy failed/i),
      ).toBeInTheDocument();
    });
  });

  it("hides copy answer button when answer has invalid unprojected markers", async () => {
    const invalidTurn: TurnResponse = {
      ...baseAnsweredTurn,
      result: {
        ...baseAnsweredTurn.result!,
        answer: "Nội dung sai marker [[E99]]",
      },
    };

    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ items: [invalidTurn], next_cursor: null }),
          ),
      ),
    );

    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    await screen.findByText(/GENERATION_OUTPUT_INVALID/i);

    // Question copy button still available
    expect(
      screen.getByRole("button", {
        name: /Sao chép câu hỏi 1|Copy question 1/i,
      }),
    ).toBeInTheDocument();

    // Answer copy button must NOT be present
    expect(
      screen.queryByRole("button", {
        name: /Sao chép câu trả lời 1|Copy answer 1/i,
      }),
    ).not.toBeInTheDocument();
  });

  it("supports copying completed refusal notice", async () => {
    const refusalTurn: TurnResponse = {
      ...baseAnsweredTurn,
      result: {
        decision: "REFUSAL",
        answer: "",
        citations: [],
        refusal_reason: "INSUFFICIENT_EVIDENCE",
        trace_id: "tr-refusal",
        workspace_id: "w-1",
      },
    };

    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ items: [refusalTurn], next_cursor: null }),
          ),
      ),
    );

    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    const copyAnswerBtn = await screen.findByRole("button", {
      name: /Sao chép câu trả lời 1|Copy answer 1/i,
    });

    fireEvent.click(copyAnswerBtn);
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith(
        "Tôi chưa có đủ bằng chứng để trả lời câu hỏi này.",
      );
    });
  });

  it("maintains independent copy state across multiple turns", async () => {
    const secondTurn: TurnResponse = {
      ...baseAnsweredTurn,
      id: "t-2",
      sequence: 2,
      question: "Câu hỏi thứ hai?",
      result: {
        ...baseAnsweredTurn.result!,
        answer: "Câu trả lời thứ hai thuần văn bản.",
        citations: [],
      },
    };

    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              items: [baseAnsweredTurn, secondTurn],
              next_cursor: null,
            }),
          ),
      ),
    );

    render(<ConversationView workspaceId="w-1" conversation={conversation} />);
    const copyQ1 = await screen.findByRole("button", {
      name: /Sao chép câu hỏi 1|Copy question 1/i,
    });
    const copyQ2 = await screen.findByRole("button", {
      name: /Sao chép câu hỏi 2|Copy question 2/i,
    });

    fireEvent.click(copyQ1);
    await waitFor(() => {
      // Q1 in copied state
      expect(copyQ1).toHaveTextContent(/Đã sao chép|Copied/i);
      // Q2 remains in idle state
      expect(copyQ2).not.toHaveTextContent(/Đã sao chép|Copied/i);
    });
  });

  it("allows copying in archived conversations without initiating mutations", async () => {
    const archivedConversation = {
      ...conversation,
      archived: true,
    };

    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ items: [baseAnsweredTurn], next_cursor: null }),
          ),
      ),
    );

    render(
      <ConversationView
        workspaceId="w-1"
        conversation={archivedConversation}
      />,
    );
    const copyQuestionBtn = await screen.findByRole("button", {
      name: /Sao chép câu hỏi 1|Copy question 1/i,
    });

    fireEvent.click(copyQuestionBtn);
    expect(writeTextMock).toHaveBeenCalledWith("Hướng dẫn cài đặt hệ thống?");
  });
});
