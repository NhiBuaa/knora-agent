"use client";

import React from "react";
import Link from "next/link";
import type { WorkspaceResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { ToolLifecycleDisplay } from "@/components/tools/ToolLifecycle";
import { Button } from "@/components/ui/Button";
import { resolveWorkspaceAfterMutation } from "./ArchiveWorkspaceDialog";
import "./workspaces.css";
import { routes } from "@/lib/navigation/routes";

export function WorkspaceUnavailable() {
  return (
    <section className="workspace-state workspace-denied" role="alert">
      <p className="workspace-eyebrow">Workspace unavailable</p>
      <h1>Workspace unavailable</h1>
      <p>
        You don’t have access to this workspace, or it is no longer available.
      </p>
      <div className="workspace-state-actions">
        <Link href="/workspaces">Choose another workspace</Link>
      </div>
    </section>
  );
}

export function WorkspaceHome({
  workspace,
  capabilities = [],
  onNavigate = (path: string) => window.location.assign(path),
}: {
  workspace: WorkspaceResponse;
  capabilities?: string[];
  onNavigate?: (path: string) => void;
}) {
  const [error, setError] = React.useState<string | null>(null);
  const createKey = React.useRef<string | null>(null);

  const [restoring, setRestoring] = React.useState(false);
  async function restore() {
    if (restoring) return;
    setRestoring(true);
    setError(null);
    let restored = false;
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspace.id)}/restore`,
        { method: "POST", headers: { "If-Match": String(workspace.revision) } },
      );
      if (!response.ok) throw new Error("restore failed");
      restored = true;
      onNavigate(await resolveWorkspaceAfterMutation(workspace.id));
    } catch {
      setError(
        restored
          ? "Workspace restored. Reload to select an active Workspace."
          : "Unable to restore Workspace. Reload and retry.",
      );
    } finally {
      setRestoring(false);
    }
  }
  async function createConversation() {
    setError(null);
    createKey.current ??= crypto.randomUUID();
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspace.id)}/conversations`,
        { method: "POST", headers: { "Idempotency-Key": createKey.current } },
      );
      if (!response.ok) throw new Error("Conversation creation failed");
      const created = (await response.json()) as { id: string };
      createKey.current = null;
      onNavigate(routes.conversation(workspace.id, created.id));
    } catch {
      setError("Unable to create Conversation. Retry with the same request.");
    }
  }

  return (
    <section>
      <h1>{workspace.name}</h1>
      {workspace.archived && (
        <div className="workspace-readonly" role="status">
          <strong>Archived workspace · Read-only</strong>
          <p>Restore the workspace to make changes again.</p>
          <Button
            variant="secondary"
            disabled={restoring}
            onClick={() => void restore()}
          >
            Restore workspace
          </Button>
        </div>
      )}
      {!capabilities.includes("documents:write") && (
        <p className="workspace-readonly">Limited permissions</p>
      )}
      <p>Manage this Workspace&apos;s documents and Conversations.</p>
      <Link href={routes.documents(workspace.id)}>Documents</Link>{" "}
      <Link href={routes.conversations(workspace.id)}>Conversations</Link>
      {!workspace.archived && (
        <button type="button" onClick={() => void createConversation()}>
          New Conversation
        </button>
      )}
      {capabilities.includes("operator:read") && (
        <ToolLifecycleDisplay workspaceId={workspace.id} />
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
