"use client";

import { LeafLoading } from "@/components/ui/LeafLoading";
import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import type { ConversationResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { routes } from "@/lib/navigation/routes";
import { Menu } from "@/components/ui/Menu";

function conversationLabel(conversation: ConversationResponse): string {
  return conversation.title_source === "auto" &&
    conversation.title.toLocaleLowerCase() === "new conversation"
    ? `Untitled conversation · ${conversation.id.slice(0, 8)}`
    : conversation.title;
}

export function ConversationList({
  workspaceId,
  initialConversations,
  nextCursor = null,
  archived = false,
  workspaceArchived = false,
  presentation = "list",
  selectedId,
  onChanged,
}: {
  workspaceId: string;
  initialConversations: ConversationResponse[];
  nextCursor?: string | null;
  archived?: boolean;
  workspaceArchived?: boolean;
  presentation?: "list" | "rail" | "collapsed";
  selectedId?: string;
  onChanged?: (conversation: ConversationResponse) => void;
}) {
  const router = useRouter();
  const [archiveTarget, setArchiveTarget] =
    useState<ConversationResponse | null>(null);
  const [mutating, setMutating] = useState(false);
  const [conversations, setConversations] = useState(initialConversations);
  const [cursor, setCursor] = useState(nextCursor);
  const [error, setError] = useState<string | null>(null);
  const pathname = usePathname();
  const [titles, setTitles] = useState<Record<string, string>>({});

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [renaming, setRenaming] = useState<ConversationResponse | null>(null);
  const scope = `${workspaceId}:${archived}`;
  const currentScope = useRef(scope);
  currentScope.current = scope;
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const initial = useRef(true);
  const collapsed = presentation === "collapsed";
  const rail = presentation !== "list";
  useEffect(() => {
    setConversations(initialConversations);
    setCursor(nextCursor);
    setQuery("");
    setError(null);
    initial.current = true;
    generation.current++;
    controller.current?.abort();
  }, [scope, initialConversations, nextCursor]);
  useEffect(() => {
    if (initial.current) {
      initial.current = false;
      return;
    }
    const request = ++generation.current;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setSearching(true);
    setCursor(null);
    const timer = setTimeout(
      () =>
        void (async () => {
          try {
            const response = await browserRequest(
              `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations?archived=${archived}&limit=20${query.trim() ? `&q=${encodeURIComponent(query.trim())}` : ""}`,
              { signal: abort.signal },
            );
            if (!response.ok) throw new Error("search unavailable");
            const page = (await response.json()) as {
              items: ConversationResponse[];
              next_cursor: string | null;
            };
            if (
              request !== generation.current ||
              currentScope.current !== scope
            )
              return;
            setConversations(page.items);
            setCursor(page.next_cursor);
            setError(null);
          } catch {
            if (
              !abort.signal.aborted &&
              request === generation.current &&
              currentScope.current === scope
            )
              setError("Unable to search Conversations. Retry.");
          } finally {
            if (
              request === generation.current &&
              currentScope.current === scope
            )
              setSearching(false);
          }
        })(),
      300,
    );
    return () => {
      clearTimeout(timer);
      abort.abort();
    };
  }, [query, scope, workspaceId, archived]);

  async function mutate(
    conversation: ConversationResponse,
    action: "rename" | "archive" | "restore",
  ) {
    setError(null);
    const title = (titles[conversation.id] ?? conversation.title).trim();
    if (action === "rename" && (!title || title === conversation.title)) return;
    if (mutating) return;
    setMutating(true);
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
      if (currentScope.current !== scope) return;
      onChanged?.(updated);
      setRenaming(null);
      setArchiveTarget(null);
      if (action === "archive" && selectedId === updated.id)
        router.push(routes.conversations(workspaceId));
      setConversations((current) =>
        action === "rename"
          ? current.map((item) => (item.id === updated.id ? updated : item))
          : current.filter((item) => item.id !== updated.id),
      );
    } catch {
      setError("Unable to update Conversation. Reload and retry.");
    } finally {
      setMutating(false);
    }
  }

  async function loadMore() {
    if (!cursor || searching) return;
    const request = generation.current;
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations?archived=${archived}&limit=20&cursor=${encodeURIComponent(cursor)}${query.trim() ? `&q=${encodeURIComponent(query.trim())}` : ""}`,
      );
      if (!response.ok) throw new Error("Conversation page unavailable");
      const page = (await response.json()) as {
        items: ConversationResponse[];
        next_cursor: string | null;
      };
      if (request !== generation.current || currentScope.current !== scope)
        return;
      setConversations((current) => {
        const seen = new Set(current.map((item) => item.id));
        return [...current, ...page.items.filter((item) => !seen.has(item.id))];
      });
      setCursor(page.next_cursor);
    } catch {
      setError("Unable to load more Conversations. Retry.");
    }
  }

  return (
    <div
      data-menu-boundary={rail ? "conversation" : undefined}
      className={
        rail
          ? "flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto [&>*]:shrink-0"
          : "flex flex-col gap-4"
      }
    >
      {!rail && (
        <h1 className="font-display text-2xl font-semibold">
          {archived ? "Archived Conversations" : "Conversations"}
        </h1>
      )}
      {workspaceArchived && !collapsed && (
        <p role="status" className="text-xs text-text-muted">
          This Workspace is read-only.
        </p>
      )}
      {!archived && !workspaceArchived && (
        <button
          type="button"
          aria-label="New Conversation"
          onClick={() => {
            const destination = routes.conversations(workspaceId);
            if (pathname !== destination) router.push(destination);
          }}
          className={`m-0 flex h-9 shrink-0 items-center gap-2 rounded-lg border border-action bg-action/10 px-3 text-[13px] font-semibold text-action-text ${collapsed ? "w-10 justify-center" : "w-full"}`}
        >
          <span aria-hidden="true">+</span>
          {!collapsed && "New conversation"}
        </button>
      )}
      {!collapsed && (
        <label className="kn-search-field flex h-9 shrink-0 items-center gap-[7px] rounded-lg border border-border bg-surface px-[11px] text-text-muted">
          <span aria-hidden="true">⌕</span>
          <span className="sr-only">Search conversations</span>
          <input
            type="search"
            maxLength={200}
            value={query}
            placeholder="Search conversations…"
            onChange={(event) => {
              generation.current++;
              controller.current?.abort();
              setQuery(event.target.value);
            }}
            className="min-w-0 flex-1 border-0 bg-transparent text-xs text-text-primary placeholder:text-text-muted"
          />
        </label>
      )}
      {!collapsed && (
        <p className="text-[10px] font-semibold text-text-muted">
          {archived ? "ARCHIVED" : "RECENT"}
        </p>
      )}
      {searching && !collapsed && (
        <LeafLoading compact label="Searching conversations" />
      )}
      {!conversations.length && !searching && !collapsed && (
        <p className="text-xs text-text-muted">
          {query ? "No matching Conversations." : "No Conversations yet."}
        </p>
      )}
      <ul className="m-0 flex min-h-0 flex-col gap-3 p-0">
        {conversations.map((conversation) => (
          <li
            key={conversation.id}
            className={
              collapsed
                ? "m-0"
                : "m-0 flex min-h-11 items-center gap-1 rounded-lg pl-2.5 pr-2 transition-colors hover:bg-surface-subtle focus-within:bg-surface-subtle"
            }
          >
            <div
              className={`flex min-w-0 flex-1 items-center gap-2 ${selectedId === conversation.id ? "rounded-lg border border-border bg-surface-subtle" : ""}`}
            >
              {selectedId === conversation.id && !collapsed && (
                <span
                  aria-hidden="true"
                  className="h-[18px] w-[3px] shrink-0 rounded-sm bg-signature"
                />
              )}
              <Link
                href={routes.conversation(workspaceId, conversation.id)}
                aria-current={
                  selectedId === conversation.id ? "page" : undefined
                }
                aria-label={conversationLabel(conversation)}
                title={conversationLabel(conversation)}
                className={
                  collapsed
                    ? "flex size-10 items-center justify-center rounded-lg text-xs font-medium"
                    : "min-w-0 flex-1 truncate py-3 text-xs"
                }
              >
                {collapsed
                  ? conversation.title.trim().charAt(0).toLocaleUpperCase()
                  : conversationLabel(conversation)}
              </Link>
              {rail && !collapsed && !workspaceArchived && (
                <Menu
                  label={`Actions for ${conversationLabel(conversation)}`}
                  boundarySelector='[data-menu-boundary="conversation"]'
                >
                  {!conversation.archived && (
                    <>
                      <button
                        role="menuitem"
                        type="button"
                        onClick={() => setRenaming(conversation)}
                      >
                        Rename
                      </button>
                      <button
                        role="menuitem"
                        type="button"
                        onClick={() => setArchiveTarget(conversation)}
                      >
                        Archive
                      </button>
                    </>
                  )}
                  {conversation.archived && (
                    <button
                      role="menuitem"
                      type="button"
                      onClick={() => void mutate(conversation, "restore")}
                    >
                      Restore
                    </button>
                  )}
                </Menu>
              )}
            </div>
            {!rail && !archived && !workspaceArchived && (
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <label>
                  Rename {conversation.title}
                  <input
                    className="ml-2 rounded border border-control-border px-2 py-1"
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
                  onClick={() => setArchiveTarget(conversation)}
                >
                  Archive {conversation.title}
                </button>
              </div>
            )}
            {!rail && archived && !workspaceArchived && (
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
      {cursor && !collapsed && (
        <button
          type="button"
          disabled={searching}
          onClick={() => void loadMore()}
          className="m-0 border-0 bg-transparent p-0 text-left text-xs text-text-muted"
        >
          Load more Conversations
        </button>
      )}
      {!collapsed && (
        <Link
          href={`${routes.conversations(workspaceId)}${archived ? "" : "?archived=true"}`}
          className="text-xs text-text-muted"
        >
          {archived
            ? "View active Conversations"
            : "View archived Conversations"}
        </Link>
      )}
      {error && (
        <p
          role="alert"
          className="w-full text-xs text-status-error [overflow-wrap:anywhere]"
        >
          {error}
        </p>
      )}
      <div>
        {renaming && (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void mutate(renaming, "rename");
            }}
            className="flex flex-col gap-4"
          >
            <label className="flex flex-col gap-2 text-sm">
              Conversation title
              <input
                value={titles[renaming.id] ?? renaming.title}
                onChange={(event) =>
                  setTitles((current) => ({
                    ...current,
                    [renaming.id]: event.target.value,
                  }))
                }
                className="m-0 rounded-lg border border-control-border bg-surface px-3 py-2"
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                type="submit"
                className="m-0 w-fit rounded-lg bg-action px-4 py-2 text-action-foreground"
              >
                Save title
              </button>
              <button
                type="button"
                onClick={() => setRenaming(null)}
                className="text-xs text-text-muted"
              >
                Cancel rename
              </button>
            </div>
          </form>
        )}
      </div>
      <Dialog
        open={archiveTarget !== null}
        title="Archive conversation"
        onClose={() => {
          if (!mutating) setArchiveTarget(null);
        }}
      >
        <p>
          Archive “{archiveTarget?.title}”? Its history remains available in
          archived conversations.
        </p>
        {error && <p role="alert">{error}</p>}
        <div className="mt-6 flex justify-end gap-3">
          <Button
            variant="secondary"
            disabled={mutating}
            onClick={() => setArchiveTarget(null)}
          >
            Cancel
          </Button>
          <Button
            disabled={mutating}
            onClick={() => {
              if (archiveTarget) void mutate(archiveTarget, "archive");
            }}
          >
            Archive conversation
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
