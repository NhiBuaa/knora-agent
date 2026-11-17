import React from "react";
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Dialog } from "@/components/ui/Dialog";

afterEach(cleanup);

describe("Dialog Exit Transition", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("applies data-closing attribute during exit transition and unmounts after duration", () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <Dialog
        open={true}
        title="Test Dialog"
        onClose={onClose}
        animateExit={true}
      >
        <p>Dialog Body</p>
      </Dialog>,
    );

    const dialog = screen.getByRole("dialog", { name: "Test Dialog" });
    expect(dialog).toBeInTheDocument();
    expect(dialog).not.toHaveAttribute("data-closing");

    // Close the dialog
    rerender(
      <Dialog
        open={false}
        title="Test Dialog"
        onClose={onClose}
        animateExit={true}
      >
        <p>Dialog Body</p>
      </Dialog>,
    );

    // During exit animation (before 140ms), dialog remains mounted with data-closing="true"
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("data-closing", "true");

    // Advance timers past the exit animation duration (140ms)
    act(() => {
      vi.advanceTimersByTime(150);
    });

    // Now dialog is completely unmounted
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("unmounts immediately when animateExit is false", () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <Dialog
        open={true}
        title="Instant Dialog"
        onClose={onClose}
        animateExit={false}
      >
        <p>Body</p>
      </Dialog>,
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();

    rerender(
      <Dialog
        open={false}
        title="Instant Dialog"
        onClose={onClose}
        animateExit={false}
      >
        <p>Body</p>
      </Dialog>,
    );

    // Immediately removed
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("unmounts immediately when prefers-reduced-motion is active", () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("prefers-reduced-motion: reduce"),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    try {
      const onClose = vi.fn();
      const { rerender } = render(
        <Dialog
          open={true}
          title="Reduced Motion Dialog"
          onClose={onClose}
          animateExit={true}
        >
          <p>Body</p>
        </Dialog>,
      );

      expect(screen.getByRole("dialog")).toBeInTheDocument();

      rerender(
        <Dialog
          open={false}
          title="Reduced Motion Dialog"
          onClose={onClose}
          animateExit={true}
        >
          <p>Body</p>
        </Dialog>,
      );

      // Reduced motion bypasses exit animation for instant unmount
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    } finally {
      window.matchMedia = originalMatchMedia;
    }
  });
});
