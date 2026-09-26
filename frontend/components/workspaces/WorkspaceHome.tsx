"use client";

import React from "react";
import Link from "next/link";
import type { WorkspaceResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { routes } from "@/lib/navigation/routes";

export function WorkspaceHome({
  workspace,
  onNavigate = (path: string) => window.location.assign(path),
}: {
  workspace: WorkspaceResponse;
  onNavigate?: (path: string) => void;
}) {
  const [error, setError] = React.useState<string | null>(null);
  const createKey = React.useRef<string | null>(null);

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
        <p role="status">This Workspace is read-only until restored.</p>
      )}
      <p>Manage this Workspace&apos;s documents and Conversations.</p>
      <Link href={routes.documents(workspace.id)}>Documents</Link>{" "}
      <Link href={routes.conversations(workspace.id)}>Conversations</Link>
      {!workspace.archived && (
        <button type="button" onClick={() => void createConversation()}>
          New Conversation
        </button>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
