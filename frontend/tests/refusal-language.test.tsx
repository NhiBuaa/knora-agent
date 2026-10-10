import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TurnCard } from "@/components/conversations/TurnCard";
import { EvidenceInspector } from "@/components/citations/EvidenceInspector";
import type { TurnResponse } from "@/generated/knora-openapi";
afterEach(cleanup);
it.each([
  ["alo ai do", true],
  ["bao nhieu chuong trong tai lieu?", true],
  ["Tài liệu nói gì?", true],
  ["What do the documents say?", false],
  ["Can you summarize this?", false],
])("presents refusal in the language of %s", (question, vietnamese) => {
  const turn = {
    id: "t",
    conversation_id: "c",
    sequence: 1,
    question,
    status: "refused",
    stage: null,
    error_code: null,
    result: {
      decision: "REFUSAL",
      answer: null,
      citations: [],
      refusal_reason: "INSUFFICIENT_EVIDENCE",
      trace_id: "trace",
      workspace_id: "w",
    },
  } as TurnResponse;
  render(
    <>
      <TurnCard
        turn={turn}
        workspaceId="w"
        selection={null}
        onSelect={vi.fn()}
        onSuggest={vi.fn()}
        onRetry={vi.fn()}
      />
      <EvidenceInspector workspaceId="w" turn={turn} />
    </>,
  );
  expect(
    screen.getByRole("heading", {
      name: vietnamese
        ? "Tôi chưa có đủ bằng chứng để trả lời câu hỏi này."
        : "I don’t have enough evidence to answer that.",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      vietnamese
        ? "Knora không tạo câu trả lời thiếu bằng chứng."
        : "Knora did not generate an unsupported answer.",
    ),
  ).toBeInTheDocument();
});
