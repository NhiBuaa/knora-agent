"use client";

import React, { useId, useRef, useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { sourceKind } from "@/lib/documents/presentation";

export function UploadDocumentDialog({
  open,
  file,
  busy,
  error,
  onFile,
  onClose,
  onUpload,
}: {
  open: boolean;
  file: File | null;
  busy: boolean;
  error: string | null;
  onFile: (file: File | null) => void;
  onClose: () => void;
  onUpload: () => void;
}) {
  const id = useId();
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);
  const picker = useRef<HTMLInputElement>(null);
  return (
    <Dialog
      open={open}
      title="Upload document"
      onClose={onClose}
      className="documents-dialog pb-6 [&_.kn-dialog\_\_close]:hidden"
    >
      <form
        className="flex flex-col gap-[18px]"
        onSubmit={(event) => {
          event.preventDefault();
          onUpload();
        }}
      >
        <p className="m-0 text-sm leading-5 text-text-muted">
          Add a source to this workspace. Knora will process it before use.
        </p>
        <div
          data-drag-active={dragging}
          onDragEnter={(event) => {
            event.preventDefault();
            if (
              !busy &&
              Array.from(event.dataTransfer.types).includes("Files")
            ) {
              dragDepth.current++;
              setDragging(true);
            }
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            dragDepth.current = Math.max(0, dragDepth.current - 1);
            if (!dragDepth.current) setDragging(false);
          }}
          className="transition-colors data-[drag-active=true]:border-action data-[drag-active=true]:bg-action/10 data-[drag-active=true]:ring-1 data-[drag-active=true]:ring-action flex min-h-[116px] flex-col items-center justify-center gap-[5px] rounded-lg border border-border bg-surface-subtle px-4 py-2.5"
          onDragOver={(event) => {
            event.preventDefault();
            event.dataTransfer.dropEffect = busy ? "none" : "copy";
          }}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            dragDepth.current = 0;
            if (!busy) onFile(event.dataTransfer.files[0] ?? null);
          }}
        >
          <span
            aria-hidden="true"
            className="text-lg leading-5 text-action-text"
          >
            ↑
          </span>
          <p className="m-0 text-[13px] leading-4 font-medium text-action-text">
            {dragging ? "Release to add this file" : "Drop a file here"}
          </p>
          <p className="m-0 text-[11px] leading-[14px] text-text-muted">
            PDF, Markdown, or text
          </p>
          <label className="sr-only" htmlFor={id}>
            Document file
          </label>
          <input
            ref={picker}
            id={id}
            className="sr-only"
            type="file"
            accept=".pdf,.md,.markdown,.txt,.text"
            disabled={busy}
            onChange={(event) => onFile(event.target.files?.[0] ?? null)}
          />
          <Button
            variant="secondary"
            disabled={busy}
            className="min-h-[30px] rounded-[7px] !border-border px-[13px] py-[7px] text-xs leading-[15px] !text-action-text"
            onClick={() => picker.current?.click()}
          >
            Choose file
          </Button>
        </div>
        {file && (
          <div className="flex flex-col gap-2">
            <p className="m-0 text-[11px] leading-[13px] font-semibold tracking-[0.66px] text-text-muted">
              SELECTED FILE
            </p>
            <div className="flex min-h-[68px] items-center gap-3 rounded-lg border !border-border px-3.5 py-2">
              <span className="flex h-[42px] w-[38px] shrink-0 items-center justify-center rounded-[7px] border border-border bg-surface-subtle text-[10px] font-semibold">
                {sourceKind(file.name).marker}
              </span>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <p className="m-0 text-[13px] font-medium [overflow-wrap:anywhere]">
                  {file.name}
                </p>
                <p className="m-0 text-xs text-text-muted">
                  {sourceKind(file.name).label} ·{" "}
                  {file.size < 1024 * 1024
                    ? `${Math.ceil(file.size / 1024)} KB`
                    : `${(file.size / (1024 * 1024)).toFixed(1)} MB`}
                </p>
              </div>
              <Button
                variant="secondary"
                aria-label="Remove file"
                disabled={busy}
                className="min-h-[30px] !border-border px-2.5 py-[7px] text-xs leading-[15px] text-text-muted"
                onClick={() => {
                  onFile(null);
                  if (picker.current) picker.current.value = "";
                }}
              >
                ×
              </Button>
            </div>
          </div>
        )}
        {error && (
          <p role="alert" className="m-0 text-sm text-status-error">
            {error}
            {error.includes("session expired") && (
              <>
                {" "}
                <a
                  href="/api/auth/login"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Sign in
                </a>
              </>
            )}
          </p>
        )}
        <div className="flex justify-end gap-2.5">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={busy}
            className="h-[38px] min-h-[38px] !border-border px-4 py-0 text-[13px]"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={!file || busy}
            className="h-[38px] min-h-[38px] px-3 py-0 text-[13px]"
          >
            <span aria-hidden="true">↑</span>
            {busy ? "Uploading…" : "Upload document"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
