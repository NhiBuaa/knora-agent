"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { WorkspaceResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { CreateWorkspaceDialog } from "./CreateWorkspaceDialog";
import { ArchiveWorkspaceDialog } from "./ArchiveWorkspaceDialog";
import { Menu } from "@/components/ui/Menu";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import "./workspaces.css";
import { routes } from "@/lib/navigation/routes";

export function WorkspaceManagement({
  initialWorkspaces,
  nextCursor = null,
}: {
  initialWorkspaces: WorkspaceResponse[];
  nextCursor?: string | null;
}) {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState(initialWorkspaces);
  const [cursor, setCursor] = useState(nextCursor);
  useEffect(() => {
    setWorkspaces(initialWorkspaces);
    setCursor(nextCursor);
  }, [initialWorkspaces, nextCursor]);
  const [renameTarget, setRenameTarget] = useState<WorkspaceResponse | null>(
    null,
  );
  const [renameBusy, setRenameBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState<WorkspaceResponse | null>(
    null,
  );
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [names, setNames] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadMore() {
    if (!cursor) return;
    setError(null);
    try {
      const response = await browserRequest(
        `/v1/workspaces?archived=false&limit=20&cursor=${encodeURIComponent(cursor)}`,
      );
      if (!response.ok) throw new Error("page unavailable");
      const page = (await response.json()) as {
        items: WorkspaceResponse[];
        next_cursor: string | null;
      };
      setWorkspaces((current) => {
        const seen = new Set(current.map((item) => item.id));
        return [...current, ...page.items.filter((item) => !seen.has(item.id))];
      });
      setCursor(page.next_cursor);
    } catch {
      setError("Unable to load more Workspaces. Retry.");
    }
  }

  async function rename(workspace: WorkspaceResponse) {
    const proposed = (names[workspace.id] ?? workspace.name).trim();
    if (!proposed || renameBusy) return;
    if (proposed === workspace.name) {
      setRenameTarget(null);
      return;
    }
    setRenameBusy(true);
    setError(null);
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspace.id)}`,
        {
          method: "PATCH",
          headers: { "If-Match": String(workspace.revision) },
          body: JSON.stringify({ name: proposed }),
        },
      );
      if (!response.ok) throw new Error("rename failed");
      const renamed = (await response.json()) as WorkspaceResponse;
      setWorkspaces((current) =>
        current.map((item) => (item.id === renamed.id ? renamed : item)),
      );
      setNames((current) => ({ ...current, [renamed.id]: renamed.name }));
      router.refresh();
      setMessage("Workspace renamed.");
      setRenameTarget(null);
    } catch {
      setError("Unable to rename Workspace. Reload and retry.");
    } finally {
      setRenameBusy(false);
    }
  }

  async function archive(workspace: WorkspaceResponse) {
    if (archiveBusy) return;
    setArchiveBusy(true);
    setError(null);
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspace.id)}/archive`,
        { method: "POST", headers: { "If-Match": String(workspace.revision) } },
      );
      if (!response.ok) throw new Error("archive failed");
      const archivedWorkspace = (await response.json()) as WorkspaceResponse;
      setWorkspaces((current) =>
        current.filter((item) => item.id !== archivedWorkspace.id),
      );
      router.refresh();
      setArchiveTarget(null);
      setMessage("Workspace archived. Its retained content remains readable.");
    } catch {
      setArchiveBusy(false);
      setError("Unable to archive Workspace. Reload and retry.");
      return;
    }
    try {
      const resolutionResponse = await browserRequest(
        "/v1/workspaces/resolve",
        {
          method: "POST",
          body: JSON.stringify({ hint_id: null }),
        },
      );
      if (!resolutionResponse.ok) {
        setError(
          "Workspace archived. Reload to select another active Workspace.",
        );
        return;
      }
      const resolution = (await resolutionResponse.json()) as {
        state: "ACTIVE" | "NO_ACTIVE_WORKSPACE";
        workspace: WorkspaceResponse | null;
      };
      if (resolution.state === "ACTIVE" && resolution.workspace) {
        const selection = await fetch("/api/workspace-selection", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ workspaceId: resolution.workspace.id }),
        });
        if (!selection.ok) {
          setError(
            "Workspace archived. Reload to select another active Workspace.",
          );
        } else router.push(routes.workspace(resolution.workspace.id));
      } else {
        const cleared = await fetch("/api/workspace-selection", {
          method: "DELETE",
        });
        if (!cleared.ok) {
          setError(
            "Workspace archived. Reload to clear the previous selection.",
          );
        } else router.push("/workspaces");
      }
    } catch {
      setError(
        "Workspace archived. Reload to select another active Workspace.",
      );
    } finally {
      setArchiveBusy(false);
    }
  }

  return (
    <section
      className={
        workspaces.length
          ? "workspace-management"
          : "workspace-state flex flex-col items-center px-4 pt-[130px] text-center [.workspace-shell-main>&]:pt-[120px] max-md:pt-[72px] max-md:[.workspace-shell-main>&]:pt-[72px]"
      }
    >
      {workspaces.length ? (
        <h1>Workspaces</h1>
      ) : (
        <>
          <p className="workspace-eyebrow m-0 mb-[18px] max-w-[560px] text-[11px] leading-6 text-text-muted uppercase">
            Workspace required
          </p>
          <h1 className="m-0 mb-4 font-display text-[32px] leading-[42px] max-md:text-[28px]">
            No active workspace
          </h1>
          <p className="m-0 max-w-[560px] leading-6 text-text-muted">
            Create a new workspace or restore one to continue.
          </p>
        </>
      )}
      <ul className="workspace-management-list list-none p-0">
        {workspaces.map((workspace) => (
          <li
            className="flex flex-wrap items-center gap-3 border-b border-border py-4"
            key={workspace.id}
          >
            <Link
              href={routes.workspace(workspace.id)}
              className="workspace-entry-link flex min-w-0 flex-1 items-center gap-3 rounded-lg px-3 py-2 font-semibold text-action-text hover:bg-surface-subtle hover:underline focus-visible:underline"
            >
              <span className="truncate">{workspace.name}</span>
              <span aria-hidden="true">→</span>
            </Link>
            <Menu label={`Actions for ${workspace.name}`}>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setError(null);
                  setRenameTarget(workspace);
                }}
              >
                Rename workspace
              </button>
              <button
                type="button"
                role="menuitem"
                disabled={archiveBusy}
                onClick={() => {
                  setError(null);
                  setArchiveTarget(workspace);
                }}
              >
                Archive workspace
              </button>
            </Menu>
          </li>
        ))}
      </ul>
      {cursor && (
        <button type="button" onClick={() => void loadMore()}>
          Load more Workspaces
        </button>
      )}
      <div className="workspace-state-actions mt-7 flex flex-wrap justify-center gap-2.5">
        <Button onClick={() => setCreating(true)}>Create workspace</Button>
        <Link
          className="inline-flex min-h-10 items-center rounded-md border border-border px-6 py-2 text-sm font-semibold text-text-primary no-underline"
          href={routes.archivedWorkspaces}
        >
          Restore workspace
        </Link>
      </div>
      {!workspaces.length && (
        <p className="workspace-state-help m-0 mt-6 max-w-[560px] rounded-lg bg-surface-subtle px-5 py-2.5 text-[13px] leading-[18px] text-text-muted">
          Restoring a workspace makes its conversations, documents, and evidence
          available again.
        </p>
      )}
      <Dialog
        open={renameTarget !== null}
        title="Rename workspace"
        onClose={() => {
          if (!renameBusy) setRenameTarget(null);
        }}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (renameTarget) void rename(renameTarget);
          }}
        >
          <label className="kn-field">
            Workspace name
            <input
              className="kn-field__control"
              maxLength={200}
              value={
                renameTarget
                  ? (names[renameTarget.id] ?? renameTarget.name)
                  : ""
              }
              onChange={(event) => {
                if (renameTarget)
                  setNames((current) => ({
                    ...current,
                    [renameTarget.id]: event.target.value,
                  }));
              }}
            />
          </label>
          {error && <p role="alert">{error}</p>}
          <div className="mt-6 flex justify-end gap-3">
            <Button
              variant="secondary"
              disabled={renameBusy}
              onClick={() => setRenameTarget(null)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={renameBusy}>
              Save name
            </Button>
          </div>
        </form>
      </Dialog>
      <CreateWorkspaceDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={async (created) => {
          setWorkspaces((current) => [...current, created]);
          setMessage("Workspace created.");
          try {
            const response = await fetch("/api/workspace-selection", {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify({ workspaceId: created.id }),
            });
            if (!response.ok) throw new Error("selection failed");
            router.push(routes.workspace(created.id));
          } catch {
            setError("Workspace created. Reload to select the Workspace.");
          }
        }}
      />
      <ArchiveWorkspaceDialog
        workspace={archiveTarget}
        busy={archiveBusy}
        error={archiveTarget ? error : null}
        onClose={() => setArchiveTarget(null)}
        onConfirm={() => {
          if (archiveTarget) void archive(archiveTarget);
        }}
      />
      {message && <p role="status">{message}</p>}
      {error && !archiveTarget && <p role="alert">{error}</p>}
    </section>
  );
}
