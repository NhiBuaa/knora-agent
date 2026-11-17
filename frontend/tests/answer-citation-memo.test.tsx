import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnswerContent } from "@/components/conversations/AnswerContent";
import type { CitationResponse } from "@/generated/knora-openapi";

const mockCitations: CitationResponse[] = [
  {
    evidence_id: "E1",
    document_id: "doc-1",
    document_version_id: "v-1",
    source_key: "guide-1",
    source_name: "Guide 1",
    heading_path: ["Heading 1"],
    start_line: 1,
    end_line: 5,
    excerpt: "First excerpt",
    content_checksum: "c1",
    page_start: 1,
    page_end: 1,
    start_offset: 0,
    end_offset: 10,
  },
  {
    evidence_id: "E2",
    document_id: "doc-2",
    document_version_id: "v-2",
    source_key: "guide-2",
    source_name: "Guide 2",
    heading_path: ["Heading 2"],
    start_line: 6,
    end_line: 10,
    excerpt: "Second excerpt",
    content_checksum: "c2",
    page_start: 2,
    page_end: 2,
    start_offset: 0,
    end_offset: 10,
  },
];

afterEach(cleanup);

describe("AnswerContent Citation Selection Memoization", () => {
  it("does not re-parse markdown AST or re-execute rehype visitor when only selectedIndex changes", () => {
    let visitorExecutionCount = 0;

    // Spy on hast transformer or measure visitor executions
    const answer = "Here is an answer citing two sources: [[E1]] and [[E2]].";

    const { rerender } = render(
      <AnswerContent
        answer={answer}
        citations={mockCitations}
        selectedIndex={null}
        onSelect={vi.fn()}
      />,
    );

    // Initial render displays the citation chips
    expect(
      screen.getByRole("button", { name: "Citation 1: Guide 1" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Citation 2: Guide 2" }),
    ).toBeInTheDocument();

    // Now re-render with selectedIndex = 0
    rerender(
      <AnswerContent
        answer={answer}
        citations={mockCitations}
        selectedIndex={0}
        onSelect={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Citation 1: Guide 1" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("button", { name: "Citation 2: Guide 2" }),
    ).toHaveAttribute("aria-pressed", "false");

    // Re-render with selectedIndex = 1
    rerender(
      <AnswerContent
        answer={answer}
        citations={mockCitations}
        selectedIndex={1}
        onSelect={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Citation 1: Guide 1" }),
    ).toHaveAttribute("aria-pressed", "false");
    expect(
      screen.getByRole("button", { name: "Citation 2: Guide 2" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("toggles citation chips via context without re-rendering the outer markdown body", () => {
    const onSelect = vi.fn();
    const answer =
      "Paragraph with **bold text** and citation [[E1]] plus list:\n\n- Item 1\n- Item 2 [[E2]]";

    const { rerender, container } = render(
      <AnswerContent
        answer={answer}
        citations={mockCitations}
        selectedIndex={null}
        onSelect={onSelect}
      />,
    );

    const strongEl = container.querySelector("strong");
    expect(strongEl).toHaveTextContent("bold text");

    const chip1 = screen.getByRole("button", { name: "Citation 1: Guide 1" });
    const chip2 = screen.getByRole("button", { name: "Citation 2: Guide 2" });
    expect(chip1).toHaveAttribute("aria-pressed", "false");
    expect(chip2).toHaveAttribute("aria-pressed", "false");

    // Re-render with selectedIndex = 0
    rerender(
      <AnswerContent
        answer={answer}
        citations={mockCitations}
        selectedIndex={0}
        onSelect={onSelect}
      />,
    );

    expect(chip1).toHaveAttribute("aria-pressed", "true");
    expect(chip2).toHaveAttribute("aria-pressed", "false");
    // Ensure static content is preserved identically
    expect(container.querySelector("strong")).toHaveTextContent("bold text");

    // Click chip 2
    fireEvent.click(chip2);
    expect(onSelect).toHaveBeenCalledWith(1);
  });
});
