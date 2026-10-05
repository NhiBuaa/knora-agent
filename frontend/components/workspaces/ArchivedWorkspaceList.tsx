"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type {
  WorkspaceListResponse,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { routes } from "@/lib/navigation/routes";
import { Button } from "@/components/ui/Button";
import { resolveWorkspaceAfterMutation } from "./ArchiveWorkspaceDialog";
import "./workspaces.css";

export function ArchivedWorkspaceList({
  initialWorkspaces,
  nextCursor = null,
  backHref = "/workspaces",
}: {
  initialWorkspaces: WorkspaceResponse[];
  nextCursor?: string | null;
  backHref?: string;
}) {
  const router = useRouter();
  const [items, setItems] = useState(initialWorkspaces);
  const [cursor, setCursor] = useState(nextCursor);
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    setItems(initialWorkspaces);
    setCursor(nextCursor);
    setQuery("");
    setSearched(false);
    generation.current++;
  }, [initialWorkspaces, nextCursor]);
  useEffect(() => {
    if (!searched) return;
    const controller = new AbortController();
    const request = ++generation.current;
    setLoading(true);
    setItems([]);
    setCursor(null);
    setError(null);
    void (async () => {
      try {
        const response = await browserRequest(
          `/v1/workspaces?archived=true&limit=20&q=${encodeURIComponent(query.trim())}`,
          { signal: controller.signal },
        );
        if (!response.ok) throw new Error("list failed");
        const page = (await response.json()) as WorkspaceListResponse;
        if (request === generation.current) {
          setItems(page.items);
          setCursor(page.next_cursor);
        }
      } catch {
        if (!controller.signal.aborted && request === generation.current)
          setError("Unable to load archived Workspaces. Retry.");
      } finally {
        if (request === generation.current) setLoading(false);
      }
    })();
    return () => {
      controller.abort();
      generation.current = request + 1;
    };
  }, [query, searched]);
  async function more() {
    if (!cursor || loading) return;
    const request = generation.current;
    setLoading(true);
    setError(null);
    try {
      const response = await browserRequest(
        `/v1/workspaces?archived=true&limit=20&q=${encodeURIComponent(query.trim())}&cursor=${encodeURIComponent(cursor)}`,
      );
      if (!response.ok) throw new Error("page failed");
      const page = (await response.json()) as WorkspaceListResponse;
      if (request === generation.current) {
        setItems((existing) => [
          ...existing,
          ...page.items.filter(
            (item) => !existing.some((other) => other.id === item.id),
          ),
        ]);
        setCursor(page.next_cursor);
      }
    } catch {
      if (request === generation.current)
        setError("Unable to load more archived Workspaces. Retry.");
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }
  async function restore(workspace: WorkspaceResponse) {
    if (busy) return;
    setBusy(workspace.id);
    setError(null);
    let restored = false;
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspace.id)}/restore`,
        { method: "POST", headers: { "If-Match": String(workspace.revision) } },
      );
      if (!response.ok) throw new Error("restore failed");
      restored = true;
      setItems((existing) =>
        existing.filter((item) => item.id !== workspace.id),
      );
      setMessage("Workspace restored.");
      router.refresh();
      router.push(await resolveWorkspaceAfterMutation(workspace.id));
    } catch {
      setError(
        restored
          ? "Workspace restored. Reload to select an active Workspace."
          : "Unable to restore Workspace. Reload and retry.",
      );
    } finally {
      setBusy(null);
    }
  }
  return (
    <section className="workspace-archives">
      <Link className="workspace-back" href={backHref}>
        ← Back
      </Link>
      <h1>Archived workspaces</h1>
      <p className="workspace-archives-intro">
        Restore archived workspaces to make them available again.
      </p>
      <div className="workspace-archives-toolbar">
        <input
          type="search"
          maxLength={200}
          aria-label="Search archived workspaces"
          placeholder="Search archived workspaces…"
          value={query}
          onChange={(event) => {
            setSearched(true);
            setQuery(event.target.value);
          }}
        />
        <span>
          {loading
            ? "Searching…"
            : `${items.length}${cursor ? "+ loaded" : ""} ${query.trim() ? "matches" : "archived workspaces"}`}
        </span>
      </div>
      <ul className="workspace-archives-list">
        {items.map((workspace) => (
          <li key={workspace.id}>
            <div>
              <Link href={routes.workspace(workspace.id)}>
                {workspace.name}
              </Link>
              <span>Archived</span>
            </div>
            <Button
              variant="secondary"
              className="border-action! text-action-text!"
              disabled={Boolean(busy)}
              aria-label={`Restore ${workspace.name}`}
              onClick={() => void restore(workspace)}
            >
              Restore
            </Button>
          </li>
        ))}
      </ul>
      {cursor && (
        <Button
          variant="secondary"
          disabled={loading}
          onClick={() => void more()}
        >
          Load more archived Workspaces
        </Button>
      )}
      {!loading && !error && !items.length && (
        <div className="workspace-archives-empty">
          {query.trim() && (
            <img src="/icons/figma/ed1ac.svg" alt="" width={48} height={48} />
          )}
          <h2>
            {query.trim()
              ? "No archived workspaces found"
              : "No archived workspaces"}
          </h2>
          <p>
            {query.trim()
              ? "Try a different search."
              : "Archived workspaces will appear here when you archive them."}
          </p>
        </div>
      )}
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
