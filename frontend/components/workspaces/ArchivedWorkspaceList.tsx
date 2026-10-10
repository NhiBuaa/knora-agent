"use client";

import { LeafLoading } from "@/components/ui/LeafLoading";
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
    <section className="workspace-archives mx-auto -mt-1 mb-0 w-full max-w-[1200px] max-md:mt-0">
      <Link
        className="workspace-back mb-6 inline-block text-sm leading-[18px] text-action-text no-underline"
        href={backHref}
      >
        ← Back
      </Link>
      <h1 className="m-0 mb-2 font-display text-[32px] leading-10">
        Archived workspaces
      </h1>
      <p className="workspace-archives-intro m-0 mb-7 text-sm leading-5 text-text-muted">
        Restore archived workspaces to make them available again.
      </p>
      <div className="workspace-archives-toolbar flex flex-wrap items-center justify-between gap-3 border-b border-border pb-[18px] text-[13px] text-text-muted">
        <input
          className="m-0 h-10 w-[232px] max-w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-[13px] text-text-primary"
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
          {loading ? (
            <LeafLoading compact label="Searching archived workspaces" />
          ) : (
            `${items.length}${cursor ? "+ loaded" : ""} ${query.trim() ? "matches" : "archived workspaces"}`
          )}
        </span>
      </div>
      <ul className="workspace-archives-list m-0 list-none p-0">
        {items.map((workspace) => (
          <li
            className="m-0 flex min-h-[77px] items-center justify-between gap-4 border-b border-border py-[18px]"
            key={workspace.id}
          >
            <div className="grid min-w-0 gap-1">
              <Link
                className="text-sm font-semibold text-text-primary no-underline [overflow-wrap:anywhere]"
                href={routes.workspace(workspace.id)}
              >
                {workspace.name}
              </Link>
              <span className="text-xs text-signature">Archived</span>
            </div>
            <Button
              variant="secondary"
              className="min-h-[38px] min-w-[104px] border-action! text-action-text!"
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
        <div
          className={`workspace-archives-empty flex min-h-[655px] flex-col items-center justify-center text-center max-md:min-h-[380px] ${query.trim() ? "gap-2.5" : "gap-2"}`}
        >
          {query.trim() && (
            // eslint-disable-next-line @next/next/no-img-element -- Render the byte-preserved local Figma SVG at its original 48px geometry; no raster optimization is needed.
            <img
              className="h-12 w-12"
              src="/icons/figma/ed1ac.svg"
              alt=""
              width={48}
              height={48}
            />
          )}
          <h2 className="m-0 font-display text-[22px] leading-[30px]">
            {query.trim()
              ? "No archived workspaces found"
              : "No archived workspaces"}
          </h2>
          <p className="m-0 text-sm text-text-muted">
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
