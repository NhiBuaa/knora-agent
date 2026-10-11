"use client";

import React, { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { focusableControls } from "@/components/ui/focusable-controls";

export function MobileDrawer({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDialogElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const dialog = panel.current;
    const returnFocus = trigger.current;
    if (!dialog) return;
    const overflow = document.body.style.overflow;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    document.body.style.overflow = "hidden";
    focusableControls(dialog)[0]?.focus();
    function onKeyDown(event: KeyboardEvent) {
      // A feature modal in the top layer owns keyboard input while this drawer is underneath it.
      const owner =
        event.target instanceof Element ? event.target.closest("dialog") : null;
      if (owner && owner !== dialog) return;
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
      }
      if (event.key !== "Tab" || !panel.current) return;
      const focusable = focusableControls(panel.current);
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
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (typeof dialog.close === "function") dialog.close();
      document.body.style.overflow = overflow;
      returnFocus?.focus();
    };
  }, [open]);

  return (
    <>
      <button
        ref={trigger}
        type="button"
        className="mobile-navigation-trigger"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(true)}
      >
        Menu
      </button>
      {open &&
        createPortal(
          <dialog
            id={id}
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-label="Workspace navigation"
            className="mobile-navigation-panel"
            onCancel={(event) => {
              event.preventDefault();
              setOpen(false);
            }}
            onClick={(event) => {
              const bounds = event.currentTarget.getBoundingClientRect();
              const backdrop =
                event.target === event.currentTarget &&
                (event.clientX < bounds.left ||
                  event.clientX > bounds.right ||
                  event.clientY < bounds.top ||
                  event.clientY > bounds.bottom);
              if (backdrop || (event.target as Element).closest("a[href]")) {
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
          </dialog>,
          document.body,
        )}
    </>
  );
}
