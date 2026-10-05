"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type {
  WorkspaceListResponse,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { routes } from "@/lib/navigation/routes";
import { Button } from "@/components/ui/Button";
import { Menu } from "@/components/ui/Menu";
import { CreateWorkspaceDialog } from "./CreateWorkspaceDialog";
import {
  ArchiveWorkspaceDialog,
  resolveWorkspaceAfterMutation,
} from "./ArchiveWorkspaceDialog";
import "./workspaces.css";

export type WorkspaceSelectorProps = {
  workspaceId: string | null;
  workspaceName: string | null;
  disabled?: boolean;
};

export function WorkspaceSelector({
  workspaceId,
  workspaceName,
  disabled = false,
}: WorkspaceSelectorProps) {
  const router = useRouter();
  const pathname = usePathname() ?? "";
  const [current, setCurrent] = useState<WorkspaceResponse | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<WorkspaceResponse[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const search = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setCurrent(null);
    setUnavailable(false);
    setOpen(false);
    setError(null);
    if (!workspaceId) return;
    const controller = new AbortController();
    let active = true;
    void (async () => {
      try {
        const response = await browserRequest(
          `/v1/workspaces/${encodeURIComponent(workspaceId)}`,
          { signal: controller.signal },
        );
        if (!response.ok) throw new Error("workspace unavailable");
        const workspace = (await response.json()) as WorkspaceResponse;
        if (workspace.id !== workspaceId) throw new Error("workspace mismatch");
        if (active) setCurrent(workspace);
      } catch {
        if (active) setUnavailable(true);
      }
    })();
    return () => {
      active = false;
      controller.abort();
    };
  }, [workspaceId, workspaceName]);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const request = ++generation.current;
    setLoading(true);
    setItems([]);
    setCursor(null);
    setError(null);
    void (async () => {
      try {
        const response = await browserRequest(
          `/v1/workspaces?archived=false&limit=20&q=${encodeURIComponent(query.trim())}`,
          { signal: controller.signal },
        );
        if (!response.ok) throw new Error("list unavailable");
        const page = (await response.json()) as WorkspaceListResponse;
        if (request === generation.current) {
          setItems(page.items);
          setCursor(page.next_cursor);
        }
      } catch {
        if (!controller.signal.aborted && request === generation.current)
          setError("Unable to load Workspaces. Retry.");
      } finally {
        if (request === generation.current) setLoading(false);
      }
    })();
    return () => {
      controller.abort();
      generation.current = request + 1;
    };
  }, [open, query]);

  useEffect(() => {
    if (!open) return;
    search.current?.focus();
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);

  async function more() {
    if (!cursor || loading) return;
    const request = generation.current;
    setLoading(true);
    setError(null);
    try {
      const response = await browserRequest(
        `/v1/workspaces?archived=false&limit=20&q=${encodeURIComponent(query.trim())}&cursor=${encodeURIComponent(cursor)}`,
      );
      if (!response.ok) throw new Error("page unavailable");
      const page = (await response.json()) as WorkspaceListResponse;
      if (request === generation.current) {
        setItems((existing) => [
          ...existing,
          ...page.items.filter(
            (item) => !existing.some((other) => item.id === other.id),
          ),
        ]);
        setCursor(page.next_cursor);
      }
    } catch {
      if (request === generation.current)
        setError("Unable to load more Workspaces. Retry.");
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }

  async function select(workspace: WorkspaceResponse) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/workspace-selection", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ workspaceId: workspace.id }),
      });
      if (!response.ok) throw new Error("selection failed");
      setOpen(false);
      const parts = pathname.split("/").filter(Boolean);
      if (parts[0] === "operator") {
        const section = ["operations", "traces", "evaluations"].includes(
          parts[1],
        )
          ? `/operator/${parts[1]}`
          : "/operator";
        router.push(section);
      } else {
        router.push(
          parts[0] === "workspaces" && parts[2] === "documents"
            ? routes.documents(workspace.id)
            : routes.workspace(workspace.id),
        );
      }
      router.refresh();
    } catch {
      setError("Unable to select Workspace. Retry.");
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    if (!current || busy) return;
    setBusy(true);
    setError(null);
    let archived = false;
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(current.id)}/archive`,
        { method: "POST", headers: { "If-Match": String(current.revision) } },
      );
      if (!response.ok) throw new Error("archive failed");
      const changed = (await response.json()) as WorkspaceResponse;
      archived = true;
      setCurrent(changed);
      setArchiving(false);
      router.refresh();
      router.push(await resolveWorkspaceAfterMutation());
    } catch {
      setError(
        archived
          ? "Workspace archived. Reload to select another active Workspace."
          : "Unable to archive Workspace. Reload and retry.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      ref={root}
      className="workspace-selector"
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.preventDefault();
          event.stopPropagation();
          setOpen(false);
          trigger.current?.focus();
        }
      }}
    >
      <p className="workspace-selector-label">Workspace</p>
      <div className="workspace-selector-heading">
        <button
          ref={trigger}
          type="button"
          className="workspace-selector-trigger"
          aria-label={`Switch workspace${current ? `: ${current.name}` : ""}`}
          aria-expanded={open}
          disabled={disabled}
          onClick={() => setOpen(!open)}
        >
          <span>
            {current?.name ??
              (unavailable
                ? "Workspace unavailable"
                : workspaceId
                  ? "Loading workspace…"
                  : "Choose workspace")}
          </span>
          <span
            className={
              current?.archived && !open
                ? "workspace-caret-context"
                : "workspace-caret-small"
            }
          >
            <img
              alt=""
              src={`/icons/figma/${open ? "23c31" : current?.archived ? "a4e11" : "21b31"}.svg`}
            />
          </span>
        </button>
        {current && !current.archived && !disabled && (
          <Menu label="Workspace actions">
            <button
              role="menuitem"
              type="button"
              onClick={() => {
                setError(null);
                setArchiving(true);
              }}
            >
              Archive workspace
            </button>
          </Menu>
        )}
      </div>
      {current?.archived && (
        <p className="workspace-readonly">Archived · Read-only</p>
      )}
      {open && (
        <div
          className="workspace-selector-popup"
          role="region"
          aria-label="Switch workspace"
        >
          <p className="workspace-selector-label">Switch workspace</p>
          <input
            ref={search}
            type="search"
            maxLength={200}
            aria-label="Search workspaces"
            placeholder="Search workspaces…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <div
            className="workspace-selector-options"
            onKeyDown={(event) => {
              if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key))
                return;
              const controls = Array.from(
                event.currentTarget.querySelectorAll<HTMLButtonElement>(
                  "button:not(:disabled)",
                ),
              );
              const index = controls.indexOf(
                document.activeElement as HTMLButtonElement,
              );
              const next =
                event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? controls.length - 1
                    : (index +
                        (event.key === "ArrowDown" ? 1 : -1) +
                        controls.length) %
                      controls.length;
              event.preventDefault();
              controls[next]?.focus();
            }}
          >
            {items.map((workspace) => (
              <button
                key={workspace.id}
                type="button"
                disabled={busy}
                aria-current={workspace.id === current?.id ? "true" : undefined}
                onClick={() => void select(workspace)}
              >
                <span>{workspace.name}</span>
                {workspace.id === current?.id && (
                  <span aria-hidden="true">✓</span>
                )}
              </button>
            ))}
          </div>
          {loading && <p role="status">Loading workspaces…</p>}
          {!loading && !error && !items.length && (
            <p>
              {query.trim() ? "No workspaces found" : "No active workspace"}
            </p>
          )}
          {cursor && (
            <Button
              variant="ghost"
              disabled={loading}
              onClick={() => void more()}
            >
              Load more Workspaces
            </Button>
          )}
          <div className="workspace-selector-footer">
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                trigger.current?.focus();
                setCreating(true);
              }}
            >
              + Create workspace
            </button>
            <Link href={routes.archivedWorkspaces}>Archived workspaces</Link>
          </div>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      <CreateWorkspaceDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={select}
      />
      <ArchiveWorkspaceDialog
        workspace={archiving ? current : null}
        onClose={() => setArchiving(false)}
        onConfirm={() => void archive()}
        busy={busy}
        error={error}
      />
    </div>
  );
}
