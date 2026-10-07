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
  presentation?: "default" | "operator-operations" | "operator-detail";
};

export function WorkspaceSelector({
  workspaceId,
  workspaceName,
  disabled = false,
  presentation = "default",
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
  const operator = presentation !== "default";
  const operatorDetail = presentation === "operator-detail";

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
      className="workspace-selector relative min-w-0 [&_:is(button,input,a):focus-visible]:outline-2 [&_:is(button,input,a):focus-visible]:outline-offset-2 [&_:is(button,input,a):focus-visible]:outline-focus"
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.preventDefault();
          event.stopPropagation();
          setOpen(false);
          trigger.current?.focus();
        }
      }}
    >
      <p className="workspace-selector-label m-0 mb-1.5 text-[10px] leading-3 font-semibold text-text-muted uppercase">
        Workspace
      </p>
      <div
        className={String.raw`workspace-selector-heading flex min-h-[26px] items-center justify-between gap-2 [&_.kn-menu\_\_panel]:left-0 [&_.kn-menu\_\_panel]:right-auto [&_.kn-menu\_\_panel]:w-[182px] [&_.kn-menu\_\_panel]:min-w-[182px] [&_.kn-menu\_\_panel_button]:text-signature ${operator ? "[&_[aria-haspopup=menu]]:h-[26px] [&_[aria-haspopup=menu]]:py-0" : ""}`}
      >
        <button
          ref={trigger}
          type="button"
          className="workspace-selector-trigger flex min-w-0 items-center gap-1.5 border-0 bg-transparent p-0 text-sm font-semibold text-text-primary"
          aria-label={`Switch workspace${current ? `: ${current.name}` : ""}`}
          aria-expanded={open}
          disabled={disabled}
          onClick={() => setOpen(!open)}
        >
          <span className="truncate">
            {current?.name ??
              (unavailable
                ? "Workspace unavailable"
                : workspaceId
                  ? "Loading workspace…"
                  : "Choose workspace")}
          </span>
          <span
            className={
              operator && !open
                ? `relative inline-block w-[10px] shrink-0 [&_img]:absolute [&_img]:max-w-none ${operatorDetail ? "h-[5px] [&_img]:-top-[0.7px] [&_img]:-left-[0.7px]" : "h-[6px] [&_img]:top-0 [&_img]:left-0"}`
                : current?.archived && !open
                  ? "workspace-caret-context"
                  : "workspace-caret-small"
            }
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- Native local SVG preserves the original fractional caret geometry and negative inset. */}
            <img
              alt=""
              src={`/icons/figma/${open ? "23c31" : operator ? (operatorDetail ? "bab86" : "a4e11") : current?.archived ? "a4e11" : "21b31"}.svg`}
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
        <p className="workspace-readonly rounded-lg bg-surface-subtle px-3 py-2.5 text-[13px] text-signature">
          Archived · Read-only
        </p>
      )}
      {open && (
        <div
          className="workspace-selector-popup absolute top-11 left-0 z-35 w-[220px] max-w-[calc(100vw-36px)] rounded-[10px] border border-border bg-surface p-3 shadow-[0_8px_16px_color-mix(in_srgb,var(--text-primary)_14%,transparent)]"
          role="region"
          aria-label="Switch workspace"
        >
          <p className="workspace-selector-label m-0 mb-1.5 text-[10px] leading-3 font-semibold text-text-muted uppercase">
            Switch workspace
          </p>
          <input
            className="mb-2 w-full rounded-md border border-border bg-surface p-2 text-xs text-text-primary"
            ref={search}
            type="search"
            maxLength={200}
            aria-label="Search workspaces"
            placeholder="Search workspaces…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <div
            className="workspace-selector-options max-h-[min(320px,40dvh)] overflow-auto"
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
                className="flex min-h-10 w-full items-center justify-between gap-2 rounded-[7px] p-2.5 text-left text-[13px] text-text-primary [overflow-wrap:anywhere] hover:bg-surface-subtle aria-[current=true]:bg-[color-mix(in_srgb,var(--action)_12%,var(--surface))] aria-[current=true]:font-semibold aria-[current=true]:text-action-text"
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
          <div className="workspace-selector-footer mt-2 grid gap-2 border-t border-border pt-2 text-[13px]">
            <button
              className="px-2.5 py-2 text-left text-action-text no-underline"
              type="button"
              onClick={() => {
                setOpen(false);
                trigger.current?.focus();
                setCreating(true);
              }}
            >
              + Create workspace
            </button>
            <Link
              className="px-2.5 py-2 text-left text-action-text no-underline"
              href={routes.archivedWorkspaces}
            >
              Archived workspaces
            </Link>
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
