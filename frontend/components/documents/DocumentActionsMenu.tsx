"use client";

import React from "react";
import Link from "next/link";
import type { DocumentResponse } from "@/generated/knora-openapi";
import { Menu } from "@/components/ui/Menu";
import { routes } from "@/lib/navigation/routes";

export function DocumentActionsMenu({
  document,
  canWrite,
  canDelete,
  canReprocess,
  busy,
  onReprocess,
  onArchive,
  onDelete,
}: {
  document: DocumentResponse;
  canWrite: boolean;
  canDelete: boolean;
  canReprocess: boolean;
  busy: boolean;
  onReprocess: () => void;
  onArchive: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="[&_.kn-menu\_\_panel]:mt-0 [&_.kn-menu\_\_panel]:min-w-[200px] [&_.kn-menu\_\_panel]:rounded-[10px] [&_.kn-menu\_\_trigger]:text-[13px] [&_.kn-menu\_\_trigger]:font-semibold [&_.kn-menu\_\_trigger]:text-text-muted">
      <Menu label={`Actions for ${document.source_name}`}>
        <Link
          role="menuitem"
          href={routes.document(document.workspace_id, document.document_id)}
          className="min-h-[34px] rounded-[7px] py-[7px] text-sm leading-5 no-underline"
        >
          View details
        </Link>
        {canReprocess && (
          <button
            role="menuitem"
            type="button"
            disabled={busy}
            className="min-h-[34px] rounded-[7px] py-[7px] text-sm leading-5"
            onClick={onReprocess}
          >
            Reprocess document
          </button>
        )}
        {canWrite && (
          <button
            role="menuitem"
            type="button"
            disabled={busy}
            className="min-h-[34px] rounded-[7px] py-[7px] text-sm leading-5"
            onClick={onArchive}
          >
            {document.archived ? "Restore document" : "Archive document"}
          </button>
        )}
        {canDelete && (
          <>
            <div role="separator" className="my-0.5 h-px bg-border" />
            <button
              role="menuitem"
              type="button"
              disabled={busy}
              className="min-h-[34px] rounded-[7px] py-[7px] text-sm leading-5 text-signature"
              onClick={onDelete}
            >
              Request deletion
            </button>
          </>
        )}
      </Menu>
    </div>
  );
}
