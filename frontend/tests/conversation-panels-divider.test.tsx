import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConversationPanels } from "@/components/conversations/ConversationPanels";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

if (typeof window.PointerEvent === "undefined") {
  class PointerEvent extends MouseEvent {
    pointerId: number;
    constructor(type: string, params: PointerEventInit = {}) {
      super(type, params);
      this.pointerId = params.pointerId ?? 0;
    }
  }
  // @ts-expect-error polyfill for jsdom
  window.PointerEvent = PointerEvent;
}

Element.prototype.setPointerCapture = vi.fn();
Element.prototype.releasePointerCapture = vi.fn();

afterEach(cleanup);

describe("ConversationPanels Divider Performance", () => {
  it("does not write preferences to storage on every pointermove and commits only on pointerup", () => {
    Object.defineProperty(window, "innerWidth", {
      value: 1440,
      writable: true,
      configurable: true,
    });
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

    render(
      <ConversationPanels
        workspaceId="ws-1"
        identityScope={{ issuer: "https://auth.knora.test", subject: "user-1" }}
        rail={(mode, onChange) => <div>Rail content</div>}
        inspector={<div>Inspector content</div>}
        composer={null}
      >
        <div>Center content</div>
      </ConversationPanels>,
    );

    const divider = screen.getByRole("separator", {
      name: "Resize conversation rail",
    });

    setItemSpy.mockClear();

    // Start dragging
    fireEvent(
      divider,
      new PointerEvent("pointerdown", {
        bubbles: true,
        cancelable: true,
        button: 0,
        clientX: 250,
        pointerId: 1,
      }),
    );

    // Move 10 times
    for (let i = 1; i <= 10; i++) {
      fireEvent(
        divider,
        new PointerEvent("pointermove", {
          bubbles: true,
          cancelable: true,
          clientX: 250 + i * 5,
          pointerId: 1,
        }),
      );
    }

    // In a high-frequency drag, setItem (storage I/O) MUST NOT be called on every pointermove
    expect(setItemSpy).not.toHaveBeenCalled();

    // Release mouse
    fireEvent(
      divider,
      new PointerEvent("pointerup", {
        bubbles: true,
        cancelable: true,
        pointerId: 1,
      }),
    );

    // Committed exactly once on pointerup
    expect(setItemSpy).toHaveBeenCalledTimes(1);
  });
});
