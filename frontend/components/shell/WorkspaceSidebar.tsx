"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type {
  ConversationResponse,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { routes } from "@/lib/navigation/routes";

export function WorkspaceSidebar({
  workspaces,
  capabilities,
  nextCursor = null,
  onNavigate = (path: string) => window.location.assign(path),
}: {
  workspaces: WorkspaceResponse[];
  capabilities: string[];
  nextCursor?: string | null;
  onNavigate?: (path: string) => void;
}) {
  const [owned, setOwned] = useState(workspaces);
  const [cursor, setCursor] = useState(nextCursor);
  useEffect(() => {
    setOwned(workspaces);
    setCursor(nextCursor);
  }, [workspaces, nextCursor]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [recent, setRecent] = useState<Record<string, ConversationResponse[]>>(
    {},
  );
  const [hasMore, setHasMore] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const createKeys = useRef<Map<string, string>>(new Map());

  async function loadMoreWorkspaces() {
    if (!cursor) return;
    setError(null);
    try {
      const response = await browserRequest(
        `/v1/workspaces?archived=false&limit=20&cursor=${encodeURIComponent(cursor)}`,
      );
      if (!response.ok) throw new Error("Workspace page unavailable");
      const page = (await response.json()) as {
        items: WorkspaceResponse[];
        next_cursor: string | null;
      };
      setOwned((current) => {
        const seen = new Set(current.map((item) => item.id));
        return [...current, ...page.items.filter((item) => !seen.has(item.id))];
      });
      setCursor(page.next_cursor);
    } catch {
      setError("Unable to load more Workspaces. Retry.");
    }
  }

  async function createConversation(workspace: WorkspaceResponse) {
    setError(null);
    let key = createKeys.current.get(workspace.id);
    if (!key) {
      key = crypto.randomUUID();
      createKeys.current.set(workspace.id, key);
    }
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspace.id)}/conversations`,
        {
          method: "POST",
          headers: { "Idempotency-Key": key },
        },
      );
      if (!response.ok) throw new Error("Conversation create failed");
      const created = (await response.json()) as ConversationResponse;
      createKeys.current.delete(workspace.id);
      onNavigate(routes.conversation(workspace.id, created.id));
    } catch {
      setError("Unable to create Conversation. Retry.");
    }
  }

  async function selectWorkspace(workspace: WorkspaceResponse) {
    setError(null);
    try {
      const response = await fetch("/api/workspace-selection", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ workspaceId: workspace.id }),
      });
      if (!response.ok) throw new Error("Workspace selection failed");
      onNavigate(routes.workspace(workspace.id));
    } catch {
      setError("Unable to select Workspace. Retry.");
    }
  }

  async function toggle(workspace: WorkspaceResponse) {
    const opening = !expanded[workspace.id];
    setExpanded((current) => ({ ...current, [workspace.id]: opening }));
    if (!opening || recent[workspace.id]) return;
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspace.id)}/conversations?archived=false&limit=5`,
      );
      if (!response.ok) throw new Error("recent Conversations unavailable");
      const page = (await response.json()) as {
        items: ConversationResponse[];
        next_cursor: string | null;
      };
      setRecent((current) => ({ ...current, [workspace.id]: page.items }));
      setHasMore((current) => ({
        ...current,
        [workspace.id]: Boolean(page.next_cursor),
      }));
    } catch {
      setError("Unable to load recent Conversations. Try expanding again.");
      setExpanded((current) => ({ ...current, [workspace.id]: false }));
    }
  }

  return (
    <nav aria-label="Workspace navigation" className="workspace-sidebar">
      <Link href="/workspaces" className="workspace-sidebar-brand">
        Knora
      </Link>
      <Link href="/workspaces">New Workspace</Link>
      {error && <p role="alert">{error}</p>}
      <ul>
        {owned
          .filter((workspace) => !workspace.archived)
          .map((workspace) => (
            <li key={workspace.id}>
              <div className="workspace-sidebar-row">
                <button
                  type="button"
                  aria-expanded={Boolean(expanded[workspace.id])}
                  aria-label={`${expanded[workspace.id] ? "Collapse" : "Expand"} ${workspace.name}`}
                  onClick={() => void toggle(workspace)}
                >
                  {expanded[workspace.id] ? "▾" : "▸"}
                </button>
                <Link
                  href={routes.workspace(workspace.id)}
                  onClick={(event) => {
                    event.preventDefault();
                    void selectWorkspace(workspace);
                  }}
                >
                  {workspace.name}
                </Link>
              </div>
              {expanded[workspace.id] && (
                <div className="workspace-sidebar-children">
                  <button
                    type="button"
                    onClick={() => void createConversation(workspace)}
                  >
                    New Conversation
                  </button>
                  <ul>
                    {(recent[workspace.id] ?? []).map((conversation) => (
                      <li
                        key={conversation.id}
                        data-testid="recent-conversation"
                      >
                        <Link
                          href={routes.conversation(
                            workspace.id,
                            conversation.id,
                          )}
                        >
                          {conversation.title}
                        </Link>
                      </li>
                    ))}
                  </ul>
                  {hasMore[workspace.id] && (
                    <Link href={routes.conversations(workspace.id)}>
                      View all
                    </Link>
                  )}
                </div>
              )}
            </li>
          ))}
      </ul>
      {cursor && (
        <button type="button" onClick={() => void loadMoreWorkspaces()}>
          Load more Workspaces
        </button>
      )}
      {capabilities.includes("operator:read") && (
        <Link href="/operator">Operator</Link>
      )}
    </nav>
  );
}
