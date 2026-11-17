import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationComposer } from "@/components/conversations/ConversationComposer";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

afterEach(cleanup);

describe("ConversationComposer Height Reflow Remediation", () => {
  it("never sets height to '0px' when rendering or updating draft", () => {
    const { rerender } = render(
      <ConversationComposer
        draft="Initial question"
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        readOnly={false}
        disabled={false}
        archived={false}
        restoreDisabled={false}
      />,
    );

    const textarea = screen.getByPlaceholderText(
      "Ask about the documents in this workspace…",
    ) as HTMLTextAreaElement;

    // Track all style height assignments
    const heightAssignments: string[] = [];
    const originalSet = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      "style",
    );

    // Spy on style.height property writes
    let styleHeight = textarea.style.height;
    Object.defineProperty(textarea.style, "height", {
      get: () => styleHeight,
      set: (val: string) => {
        heightAssignments.push(val);
        styleHeight = val;
      },
      configurable: true,
    });

    // Update draft to trigger resize effect
    rerender(
      <ConversationComposer
        draft="Initial question with more lines\nSecond line"
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        readOnly={false}
        disabled={false}
        archived={false}
        restoreDisabled={false}
      />,
    );

    // Should never collapse to 0px (which causes forced synchronous reflow and layout thrashing)
    expect(heightAssignments).not.toContain("0px");
  });

  it("skips JavaScript height manipulation entirely when CSS field-sizing: content is supported", () => {
    // Mock CSS.supports to return true for field-sizing
    const originalSupports = window.CSS?.supports;
    window.CSS = {
      ...window.CSS,
      supports: vi.fn(
        (prop: string, val?: string) =>
          prop === "field-sizing" ||
          (prop === "field-sizing" && val === "content"),
      ),
    } as any;

    try {
      const heightAssignments: string[] = [];
      const { rerender } = render(
        <ConversationComposer
          draft="Draft 1"
          onChange={vi.fn()}
          onSubmit={vi.fn()}
          readOnly={false}
          disabled={false}
          archived={false}
          restoreDisabled={false}
        />,
      );

      const textarea = screen.getByPlaceholderText(
        "Ask about the documents in this workspace…",
      ) as HTMLTextAreaElement;

      let styleHeight = textarea.style.height;
      Object.defineProperty(textarea.style, "height", {
        get: () => styleHeight,
        set: (val: string) => {
          heightAssignments.push(val);
          styleHeight = val;
        },
        configurable: true,
      });

      rerender(
        <ConversationComposer
          draft="Draft 2"
          onChange={vi.fn()}
          onSubmit={vi.fn()}
          readOnly={false}
          disabled={false}
          archived={false}
          restoreDisabled={false}
        />,
      );

      // With native field-sizing support, JS shouldn't touch style.height at all
      expect(heightAssignments).toHaveLength(0);
    } finally {
      if (originalSupports) {
        window.CSS.supports = originalSupports;
      }
    }
  });
});
