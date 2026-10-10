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
      className="workspace-state workspace-denied mx-auto mt-[215px] mb-0 flex min-h-[330px] w-full max-w-[640px] flex-col items-center justify-center px-4 text-center [.workspace-shell-main>&]:mt-[167px] max-md:mt-[116px] max-md:[.workspace-shell-main>&]:mt-[116px]"
      role="alert"
    >
      <p className="workspace-eyebrow m-0 mb-[18px] max-w-[560px] text-[11px] leading-[normal] font-semibold text-text-muted uppercase">
        Workspace unavailable
      </p>
      <h1 className="m-0 mb-[14px] font-display text-[32px] leading-[42px] font-semibold max-md:text-[28px]">
        Workspace unavailable
      </h1>
      <p className="m-0 max-w-[560px] leading-6 text-text-muted">
        You don’t have access to this workspace, or it is no longer available.
      </p>
      <div className="workspace-state-actions mt-7 flex flex-wrap justify-center gap-2.5">
        <Link
          className="inline-flex min-h-10 w-[236px] max-w-full items-center justify-center rounded-[7px] border-0 bg-action px-4 py-2 text-sm font-semibold text-action-foreground no-underline"
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
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="m-0 font-display text-[32px] leading-10 font-semibold">
          {workspace.name}
        </h1>
        <p className="m-0 text-sm leading-6 text-text-muted">
          Manage this Workspace&apos;s documents and Conversations.
        </p>
      </header>
      {workspace.archived && (
        <div
          className="workspace-readonly flex flex-col items-start gap-2 rounded-lg bg-surface-subtle px-3 py-2.5 text-[13px] text-signature"
          role="status"
        >
          <strong>Archived workspace · Read-only</strong>
          <p className="m-0">Restore the workspace to make changes again.</p>
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
        <p className="workspace-readonly m-0 rounded-lg bg-surface-subtle px-3 py-2.5 text-[13px] text-signature">
          Limited permissions
        </p>
      )}
      <nav aria-label="Workspace actions" className="flex flex-wrap gap-3">
        <Link
          className="inline-flex min-h-10 items-center justify-center rounded-lg border border-control-border bg-surface px-3.5 py-2 text-sm font-semibold text-text-primary no-underline hover:bg-surface-subtle"
          href={routes.documents(workspace.id)}
        >
          Documents
        </Link>
        <Link
          className="inline-flex min-h-10 items-center justify-center rounded-lg border border-control-border bg-surface px-3.5 py-2 text-sm font-semibold text-text-primary no-underline hover:bg-surface-subtle"
          href={routes.conversations(workspace.id)}
        >
          Conversations
        </Link>
        {!workspace.archived && (
          <Button onClick={() => void createConversation()}>
            New Conversation
          </Button>
        )}
      </nav>
      {capabilities.includes("operator:read") && (
        <ToolLifecycleDisplay workspaceId={workspace.id} />
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
