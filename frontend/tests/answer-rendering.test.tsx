import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TurnCard } from "@/components/conversations/TurnCard";
import { EvidenceInspector } from "@/components/citations/EvidenceInspector";
import type { TurnResponse } from "@/generated/knora-openapi";

const citations = ["E2", "E1"].map((evidence_id, index) => ({
  evidence_id,
  document_id: `document-${index}`,
  document_version_id: `version-${index}`,
  source_key: `guide-${index}`,
  source_name: `Guide ${index}`,
  heading_path: [],
  start_line: 2,
  end_line: 5,
  excerpt: "Report structure\n  - Introduction\n  - Conclusion",
  content_checksum: `checksum-${index}`,
  page_start: index + 3,
  page_end: index + 3,
  start_offset: 10,
  end_offset: 80,
}));
const turn: TurnResponse = {
  id: "turn",
  conversation_id: "conversation",
  sequence: 1,
  question: "How is the report organized?",
  status: "answered",
  stage: null,
  error_code: null,
  result: {
    workspace_id: "workspace",
    decision: "ANSWER",
    answer:
      "## Structure\n\nTwo chapters:\n\n1. **Introduction**\n2. Conclusion [[E2]]\n\nA second paragraph. [[E1]]",
    citations,
    refusal_reason: null,
    trace_id: "trace",
  },
};
afterEach(cleanup);

it("renders answer headings, paragraphs and lists with inline citations selecting the exact projection", () => {
  const onSelect = vi.fn();
  const { container } = render(
    <TurnCard
      turn={turn}
      workspaceId="workspace"
      selection={null}
      onSelect={onSelect}
      onRetry={vi.fn()}
    />,
  );
  expect(screen.getByRole("heading", { name: "Structure" })).toBeVisible();
  const list = container.querySelector("article ol")!;
  expect(within(list as HTMLElement).getAllByRole("listitem")).toHaveLength(2);
  expect(container.querySelector("strong")).toHaveTextContent("Introduction");
  expect(screen.getByText("A second paragraph.").tagName).toBe("P");
  expect(container.textContent).not.toContain("[[E");
  fireEvent.click(
    within(list as HTMLElement).getByRole("button", {
      name: "Citation 1: Guide 0",
    }),
  );
  expect(onSelect).toHaveBeenLastCalledWith({
    turnId: "turn",
    citationIndex: 0,
  });
  fireEvent.click(
    screen.getByText("A second paragraph.").querySelector("button")!,
  );
  expect(onSelect).toHaveBeenLastCalledWith({
    turnId: "turn",
    citationIndex: 1,
  });
  render(
    <EvidenceInspector
      workspaceId="workspace"
      citation={citations[1]}
      turn={turn}
    />,
  );
  expect(screen.getByRole("link", { name: "Open document" })).toHaveAttribute(
    "href",
    "/workspaces/workspace/documents/document-1",
  );
  expect(screen.getByText("version-1")).toBeVisible();
  expect(screen.getByText("page 4")).toBeVisible();
  expect(screen.getByText("E1")).toBeInTheDocument();
  expect(screen.getByText("10–80")).toBeInTheDocument();
});

it.each(["Unsupported [[E3]]", "Malformed [[E1]", "Repeated [[E1]] [[E1]]"])(
  "surfaces invalid citation output instead of stripping markers: %s",
  (answer) => {
    const { container } = render(
      <TurnCard
        turn={{ ...turn, result: { ...turn.result!, answer } }}
        workspaceId="workspace"
        selection={null}
        onSelect={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "GENERATION_OUTPUT_INVALID",
    );
    expect(container.textContent).not.toContain("[[");
  },
);

it("keeps source excerpt newlines and indentation without interpreting source markup", () => {
  const excerpt =
    "Report structure\n  - Introduction\n  - Conclusion\n<script>source text</script>";
  const { container } = render(
    <EvidenceInspector
      workspaceId="workspace"
      citation={{ ...citations[0], excerpt }}
      turn={turn}
    />,
  );
  const passage = container.querySelector("blockquote p:last-child")!;
  expect(passage.textContent).toBe(excerpt);
  expect(passage).toHaveClass("whitespace-pre-wrap", "break-words");
  expect(container.querySelector("script")).toBeNull();
});

it("does not turn generated HTML, links or images into active content", () => {
  const answer =
    "<script>alert(1)</script>\n\n[click](javascript:alert) ![tracking](https://example.com/track) [[E1]]";
  const { container } = render(
    <TurnCard
      turn={{ ...turn, result: { ...turn.result!, answer } }}
      workspaceId="workspace"
      selection={null}
      onSelect={vi.fn()}
      onRetry={vi.fn()}
    />,
  );
  expect(container.querySelector("script, img, article a")).toBeNull();
  expect(container.textContent).toContain("click");
  expect(container.textContent).not.toContain("[[E1]]");
});

it.each([
  "[[E1]](https://example.com)",
  "![[E1]](https://example.com)",
  "`[[E1]]`",
])(
  "keeps citation selection when Markdown surrounds a marker: %s",
  (answer) => {
    render(
      <TurnCard
        turn={{ ...turn, result: { ...turn.result!, answer } }}
        workspaceId="workspace"
        selection={null}
        onSelect={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    expect(
      screen.getAllByRole("button", { name: "Citation 2: Guide 1" }),
    ).toHaveLength(2);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  },
);

it.each(["&#91;&#91;E99&#93;&#93; [[E1]]", "&#xE000;99&#xE001; [[E1]]"])(
  "surfaces unvalidated decoded text without fabricating a citation: %s",
  (answer) => {
    const { container } = render(
      <TurnCard
        turn={{ ...turn, result: { ...turn.result!, answer } }}
        workspaceId="workspace"
        selection={null}
        onSelect={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "GENERATION_OUTPUT_INVALID",
    );
    expect(container.textContent).not.toContain("[[");
  },
);
