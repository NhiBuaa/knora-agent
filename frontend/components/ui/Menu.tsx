"use client";

import React, { useEffect, useId, useRef, useState } from "react";
import { focusableControls } from "./focusable-controls";

export type MenuProps = { label: string; children: React.ReactNode };

export function Menu({ label, children }: MenuProps) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const root = useRef<HTMLDivElement>(null);
  const initialEnd = useRef(false);
  const id = useId();

  function dismiss(returnFocus: boolean) {
    setOpen(false);
    if (returnFocus) trigger.current?.focus();
  }

  useEffect(() => {
    if (!open) return;
    const items = panel.current ? focusableControls(panel.current) : [];
    (initialEnd.current ? items[items.length - 1] : items[0])?.focus();
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);

  return (
    <div
      ref={root}
      className="kn-menu relative"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node))
          setOpen(false);
      }}
    >
      <button
        ref={trigger}
        type="button"
        className="kn-menu__trigger"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => {
          initialEnd.current = false;
          setOpen(!open);
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            initialEnd.current = event.key === "ArrowUp";
            setOpen(true);
          }
        }}
      >
        <span aria-hidden="true">···</span>
      </button>
      {open && (
        <div
          ref={panel}
          id={id}
          role="menu"
          aria-label={label}
          className="kn-menu__panel absolute right-0 z-30 mt-2 min-w-52 rounded-lg border border-border bg-surface p-1.5 text-text-primary shadow-lg"
          onClick={(event) => {
            const action = (event.target as Element).closest(
              'button, a[href], [role="menuitem"]',
            );
            // Keep native submit buttons connected until the browser submits their form.
            if (
              action instanceof HTMLButtonElement &&
              action.type === "submit" &&
              action.form
            )
              return;
            if (action && !action.matches(':disabled, [aria-disabled="true"]'))
              dismiss(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              dismiss(true);
            }
            if (event.key === "Tab" && trigger.current) {
              event.preventDefault();
              const scope =
                trigger.current.closest<HTMLElement>("dialog[open]") ??
                document.body;
              const outside = focusableControls(scope).filter(
                (item) => !panel.current?.contains(item),
              );
              const index = outside.indexOf(trigger.current);
              setOpen(false);
              (
                outside[index + (event.shiftKey ? -1 : 1)] ?? trigger.current
              ).focus();
            }
            if (
              !panel.current ||
              !["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)
            )
              return;
            if ((event.target as Element).matches("input, select, textarea"))
              return;
            event.preventDefault();
            const items = focusableControls(panel.current);
            const current = items.indexOf(
              document.activeElement as HTMLElement,
            );
            const next =
              event.key === "Home"
                ? 0
                : event.key === "End"
                  ? items.length - 1
                  : (current +
                      (event.key === "ArrowDown" ? 1 : -1) +
                      items.length) %
                    items.length;
            items[next]?.focus();
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}
