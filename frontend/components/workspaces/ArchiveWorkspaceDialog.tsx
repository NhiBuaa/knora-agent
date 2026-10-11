"use client";

import React from "react";
import type {
  ResolutionResponse,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { destinationForResolution } from "@/lib/navigation/routes";
import "./workspaces.css";

/** Resolve after a durable lifecycle change; the signed preference is only a hint. */
export async function resolveWorkspaceAfterMutation(
  hint: string | null = null,
): Promise<string> {
  const response = await browserRequest("/v1/workspaces/resolve", {
    method: "POST",
    body: JSON.stringify({ hint_id: hint }),
  });
  if (!response.ok) throw new Error("resolution failed");
  const resolution = (await response.json()) as ResolutionResponse;
  const selected = resolution.state === "ACTIVE" && resolution.workspace;
  const selection = await fetch(
    "/api/workspace-selection",
    selected
      ? {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ workspaceId: selected.id }),
        }
      : { method: "DELETE" },
  );
  if (!selection.ok) throw new Error("selection failed");
  return destinationForResolution(resolution);
}

export function ArchiveWorkspaceDialog({
  workspace,
  onClose,
  onConfirm,
  busy = false,
  error,
  stayOnList = false,
}: {
  workspace: WorkspaceResponse | null;
  onClose: () => void;
  onConfirm: () => void;
  busy?: boolean;
  error?: string | null;
  stayOnList?: boolean;
}) {
  return (
    <Dialog
      open={Boolean(workspace)}
      onClose={onClose}
      title="Archive workspace"
      className="workspace-dialog workspace-archive-dialog [--dialog-width:600px] [&_.kn-dialog\_\_close]:hidden [&_h2]:font-display [&_h2]:text-2xl [&_h2]:leading-8"
    >
      <p className="workspace-dialog-intro m-0 mb-[34px] text-sm leading-[22px] text-text-muted">
        Archive “{workspace?.name}”? It will no longer be active until you
        restore it.
      </p>
      <div className="workspace-archive-summary grid gap-1 rounded-lg bg-surface-subtle px-3.5 py-3 text-sm">
        <strong className="leading-[18px]">{workspace?.name}</strong>
        <span className="text-xs leading-[14px] text-text-muted">
          Current workspace
        </span>
      </div>
      <p className="workspace-archive-explanation mt-4 text-xs leading-[18px] text-text-muted">
        {stayOnList
          ? "Its documents and conversations become read-only. You’ll remain on the workspace list."
          : "Its documents and conversations become read-only. If another active workspace is available, Knora will switch to it. If none remain, you’ll see the no-active-workspace state."}
      </p>
      {error && <p role="alert">{error}</p>}
      <div className="workspace-dialog-actions mt-6 flex flex-wrap justify-end gap-2.5">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant="signature"
          disabled={busy}
          loading={busy}
          onClick={onConfirm}
        >
          Archive workspace
        </Button>
      </div>
    </Dialog>
  );
}
