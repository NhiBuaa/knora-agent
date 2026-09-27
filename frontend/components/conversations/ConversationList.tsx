"use client";

import React, { useState } from "react";
import Link from "next/link";
import type { ConversationResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { routes } from "@/lib/navigation/routes";

export function ConversationList({
  workspaceId,
  initialConversations,
  nextCursor = null,
  archived = false,
  workspaceArchived = false,
}: {
  workspaceId: string;
  initialConversations: ConversationResponse[];
  nextCursor?: string | null;
  archived?: boolean;
  workspaceArchived?: boolean;
}) {
  const [conversations, setConversations] = useState(initialConversations);
  const [cursor, setCursor] = useState(nextCursor);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [createKey, setCreateKey] = useState<string | null>(null);
  const [titles, setTitles] = useState<Record<string, string>>({});

  async function mutate(
    conversation: ConversationResponse,
    action: "rename" | "archive" | "restore",
  ) {
    setError(null);
    const title = (titles[conversation.id] ?? conversation.title).trim();
    if (action === "rename" && (!title || title === conversation.title)) return;
    if (
      action === "archive" &&
      !window.confirm(
        "Archive this Conversation? Its history stays readable until restored.",
      )
    )
      return;
    try {
      const base = `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations/${encodeURIComponent(conversation.id)}`;
      const response = await browserRequest(
        action === "rename" ? base : `${base}/${action}`,
        {
          method: action === "rename" ? "PATCH" : "POST",
          headers: { "If-Match": String(conversation.revision) },
          body: action === "rename" ? JSON.stringify({ title }) : undefined,
        },
      );
      if (!response.ok) throw new Error("Conversation mutation failed");
      const updated = (await response.json()) as ConversationResponse;
      setConversations((current) =>
        action === "rename"
          ? current.map((item) => (item.id === updated.id ? updated : item))
          : current.filter((item) => item.id !== updated.id),
      );
    } catch {
      setError("Unable to update Conversation. Reload and retry.");
    }
  }

  async function loadMore() {
    if (!cursor) return;
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations?archived=${archived}&limit=20&cursor=${encodeURIComponent(cursor)}`,
      );
      if (!response.ok) throw new Error("Conversation page unavailable");
      const page = (await response.json()) as {
        items: ConversationResponse[];
        next_cursor: string | null;
      };
      setConversations((current) => [...current, ...page.items]);
      setCursor(page.next_cursor);
    } catch {
      setError("Unable to load more Conversations. Retry.");
    }
  }

  async function create() {
    setCreating(true);
    setError(null);
    const key = createKey ?? crypto.randomUUID();
    setCreateKey(key);
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations`,
        { method: "POST", headers: { "Idempotency-Key": key } },
      );
      if (!response.ok) throw new Error("Conversation create failed");
      const result = (await response.json()) as ConversationResponse;
      setCreateKey(null);
      window.location.assign(routes.conversation(workspaceId, result.id));
    } catch {
      setError(
        "Unable to confirm Conversation creation. Retry with the same request.",
      );
    } finally {
      setCreating(false);
    }
  }

  return (
    <section>
      <h1>{archived ? "Archived Conversations" : "Conversations"}</h1>
      {workspaceArchived && <p role="status">This Workspace is read-only.</p>}
      {!archived && !workspaceArchived && (
        <button type="button" disabled={creating} onClick={() => void create()}>
          New Conversation
        </button>
      )}
      {!conversations.length && <p>No Conversations yet.</p>}
      <ul>
        {conversations.map((conversation) => (
          <li key={conversation.id}>
            <Link href={routes.conversation(workspaceId, conversation.id)}>
              {conversation.title}
            </Link>
            {!archived && !workspaceArchived && (
              <>
                <label>
                  Rename {conversation.title}
                  <input
                    value={titles[conversation.id] ?? conversation.title}
                    onChange={(event) =>
                      setTitles((current) => ({
                        ...current,
                        [conversation.id]: event.target.value,
                      }))
                    }
                  />
                </label>
                <button
                  type="button"
                  onClick={() => void mutate(conversation, "rename")}
                >
                  Save {conversation.title} title
                </button>
                <button
                  type="button"
                  onClick={() => void mutate(conversation, "archive")}
                >
                  Archive {conversation.title}
                </button>
              </>
            )}
            {archived && !workspaceArchived && (
              <button
                type="button"
                onClick={() => void mutate(conversation, "restore")}
              >
                Restore {conversation.title}
              </button>
            )}
          </li>
        ))}
      </ul>
      {cursor && (
        <button type="button" onClick={() => void loadMore()}>
          Load more Conversations
        </button>
      )}
      {!archived && (
        <Link href={`${routes.conversations(workspaceId)}?archived=true`}>
          View archived Conversations
        </Link>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
