"use client";

import React, { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { focusableControls } from "./focusable-controls";

export type DialogProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  /** Presentation only. For sizing, use a static utility such as [--dialog-width:600px]. */
  className?: string;
};

export function Dialog({
  open,
  title,
  onClose,
  children,
  className = "",
}: DialogProps) {
  const panel = useRef<HTMLDialogElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  const titleId = useId();

  useEffect(() => {
    const dialog = panel.current;
    if (!open || !dialog) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    // Native modality makes the background inert and puts the dialog in the top layer.
    // The fallback also allows the public interface to be exercised in jsdom.
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    document.body.style.overflow = "hidden";
    (focusableControls(dialog)[0] ?? dialog).focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        close.current();
      }
      if (event.key !== "Tab" || !dialog) return;
      const controls = focusableControls(dialog);
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (!first) {
        event.preventDefault();
        dialog.focus();
      } else if (
        event.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === dialog ||
          !dialog.contains(document.activeElement))
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last ||
          document.activeElement === dialog ||
          !dialog.contains(document.activeElement))
      ) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus();
    };
  }, [open]);

  if (!open || typeof document === "undefined") return null;
  return createPortal(
    <dialog
      ref={panel}
      aria-modal="true"
      aria-labelledby={titleId}
      tabIndex={-1}
      className={`kn-dialog m-auto max-h-[calc(100dvh-32px)] w-[min(var(--dialog-width,560px),calc(100vw-32px))] overflow-auto rounded-xl border border-border bg-surface p-7 text-text-primary shadow-xl ${className}`.trim()}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target !== event.currentTarget) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < bounds.left ||
          event.clientX > bounds.right ||
          event.clientY < bounds.top ||
          event.clientY > bounds.bottom
        )
          onClose();
      }}
    >
      <div className="kn-dialog__content">
        <header className="mb-[18px] flex items-center justify-between gap-4">
          <h2 id={titleId} className="text-2xl font-semibold">
            {title}
          </h2>
          <button
            type="button"
            aria-label={`Close ${title}`}
            className="kn-dialog__close"
            onClick={onClose}
          >
            ×
          </button>
        </header>
        <div>{children}</div>
      </div>
    </dialog>,
    document.body,
  );
}
