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
    <section
      className="workspace-state workspace-denied flex flex-col items-center px-4 pt-[240px] text-center [.workspace-shell-main>&]:pt-[222px] max-md:pt-[140px] max-md:[.workspace-shell-main>&]:pt-[140px]"
      role="alert"
    >
      <p className="workspace-eyebrow m-0 mb-[18px] max-w-[560px] text-[11px] leading-6 text-text-muted uppercase">
        Workspace unavailable
      </p>
      <h1 className="m-0 mb-4 font-display text-[32px] leading-[42px] max-md:text-[28px]">
        Workspace unavailable
      </h1>
      <p className="m-0 max-w-[560px] leading-6 text-text-muted">
        You don’t have access to this workspace, or it is no longer available.
      </p>
      <div className="workspace-state-actions mt-7 flex flex-wrap justify-center gap-2.5">
        <Link
          className="inline-flex min-h-10 items-center rounded-md border border-border bg-action px-6 py-2 text-sm font-semibold text-action-foreground no-underline"
          href="/workspaces"
        >
          Choose another workspace
        </Link>
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
        <div
          className="workspace-readonly rounded-lg bg-surface-subtle px-3 py-2.5 text-[13px] text-signature"
          role="status"
        >
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
        <p className="workspace-readonly rounded-lg bg-surface-subtle px-3 py-2.5 text-[13px] text-signature">
          Limited permissions
        </p>
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
