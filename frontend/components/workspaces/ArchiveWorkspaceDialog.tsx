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
}: {
  workspace: WorkspaceResponse | null;
  onClose: () => void;
  onConfirm: () => void;
  busy?: boolean;
  error?: string | null;
}) {
  return (
    <Dialog
      open={Boolean(workspace)}
      onClose={onClose}
      title="Archive workspace"
      className="workspace-dialog workspace-archive-dialog [--dialog-width:600px]"
    >
      <p className="workspace-dialog-intro">
        Archive “{workspace?.name}”? It will no longer be active until you
        restore it.
      </p>
      <div className="workspace-archive-summary">
        <strong>{workspace?.name}</strong>
        <span>Current workspace</span>
      </div>
      <p className="workspace-archive-explanation">
        Its documents and conversations become read-only. If another active
        workspace is available, Knora will switch to it. If none remain, you’ll
        see the no-active-workspace state.
      </p>
      {error && <p role="alert">{error}</p>}
      <div className="workspace-dialog-actions">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button variant="signature" disabled={busy} onClick={onConfirm}>
          {busy ? "Archiving…" : "Archive workspace"}
        </Button>
      </div>
    </Dialog>
  );
}
