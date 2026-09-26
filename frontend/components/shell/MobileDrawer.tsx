"use client";

import React, { useEffect, useRef, useState } from "react";

export function MobileDrawer({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const first = panel.current?.querySelector<HTMLElement>(
      "a, button, input, select, textarea",
    );
    first?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
      if (event.key !== "Tab" || !panel.current) return;
      const focusable = Array.from(
        panel.current.querySelectorAll<HTMLElement>(
          "a, button, input, select, textarea",
        ),
      ).filter((element) => !element.hasAttribute("disabled"));
      if (!focusable.length) return;
      const firstItem = focusable[0];
      const lastItem = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault();
        firstItem.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <>
      <button
        ref={trigger}
        type="button"
        className="mobile-navigation-trigger"
        aria-expanded={open}
        aria-controls="mobile-workspace-navigation"
        onClick={() => setOpen(true)}
      >
        Menu
      </button>
      {open && (
        <div className="mobile-navigation-backdrop">
          <div
            id="mobile-workspace-navigation"
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-label="Workspace navigation"
            className="mobile-navigation-panel"
            onClick={(event) => {
              if ((event.target as Element).closest("a[href]")) {
                setOpen(false);
                trigger.current?.focus();
              }
            }}
          >
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                trigger.current?.focus();
              }}
            >
              Close menu
            </button>
            {children}
          </div>
        </div>
      )}
    </>
  );
}
