"use client";

import React from "react";
import type { DocumentResponse } from "@/generated/knora-openapi";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { documentStatus, sourceKind } from "@/lib/documents/presentation";

export function DeletionRequestDialog({
  document,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  document: DocumentResponse | null;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog
      open={Boolean(document)}
      title="Request document deletion"
      onClose={onClose}
      className="documents-dialog pb-6 [&_.kn-dialog\_\_close]:hidden"
    >
      {document && (
        <div className="flex flex-col gap-[18px]">
          <p className="m-0 text-sm leading-5 text-text-muted">
            Submit a deletion request for this document. It will not be removed
            immediately. Availability for new answers depends on the returned
            request state and policy.
          </p>
          <div className="flex flex-col gap-2">
            <p className="m-0 text-[11px] leading-[13px] font-semibold tracking-[0.66px] text-text-muted">
              DOCUMENT
            </p>
            <div className="flex min-h-[68px] items-center gap-3 rounded-lg border !border-border px-3.5 py-2">
              <span className="flex h-[42px] w-[38px] shrink-0 items-center justify-center rounded-[7px] border border-border bg-surface-subtle text-[10px] font-semibold">
                {sourceKind(document.source_name).marker}
              </span>
              <div className="flex min-w-0 flex-col gap-1">
                <p className="m-0 text-[13px] font-medium [overflow-wrap:anywhere]">
                  {document.source_name}
                </p>
                <p className="m-0 text-xs text-text-muted">
                  {sourceKind(document.source_name).label} source ·{" "}
                  {documentStatus(document).label}
                </p>
              </div>
            </div>
          </div>
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
              disabled={busy}
              onClick={onClose}
              className="h-[38px] min-h-[38px] !border-border px-4 py-0 text-[13px]"
            >
              Cancel
            </Button>
            <Button
              variant="signature"
              disabled={busy}
              onClick={onConfirm}
              className="h-[38px] min-h-[38px] px-5 py-0 text-[13px]"
            >
              {busy ? "Requesting…" : "Request deletion"}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
