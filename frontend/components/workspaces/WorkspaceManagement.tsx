"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { WorkspaceResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { CreateWorkspaceDialog } from "./CreateWorkspaceDialog";
import { ArchiveWorkspaceDialog } from "./ArchiveWorkspaceDialog";
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
    if (!proposed || proposed === workspace.name) return;
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
    } catch {
      setError("Unable to rename Workspace. Reload and retry.");
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
      className={workspaces.length ? "workspace-management" : "workspace-state"}
    >
      {workspaces.length ? (
        <h1>Workspaces</h1>
      ) : (
        <>
          <p className="workspace-eyebrow">Workspace required</p>
          <h1>No active workspace</h1>
          <p>Create a new workspace or restore one to continue.</p>
        </>
      )}
      <ul className="workspace-management-list">
        {workspaces.map((workspace) => (
          <li key={workspace.id}>
            <Link href={routes.workspace(workspace.id)}>{workspace.name}</Link>
            <label>
              Rename {workspace.name}
              <input
                value={names[workspace.id] ?? workspace.name}
                onChange={(event) =>
                  setNames((current) => ({
                    ...current,
                    [workspace.id]: event.target.value,
                  }))
                }
              />
            </label>
            <button type="button" onClick={() => void rename(workspace)}>
              Save {workspace.name} name
            </button>
            <button
              type="button"
              disabled={archiveBusy}
              onClick={() => {
                setError(null);
                setArchiveTarget(workspace);
              }}
            >
              Archive workspace {workspace.name}
            </button>
          </li>
        ))}
      </ul>
      {cursor && (
        <button type="button" onClick={() => void loadMore()}>
          Load more Workspaces
        </button>
      )}
      <div className="workspace-state-actions">
        <Button onClick={() => setCreating(true)}>Create workspace</Button>
        <Link href={routes.archivedWorkspaces}>Restore workspace</Link>
      </div>
      {!workspaces.length && (
        <p className="workspace-state-help">
          Restoring a workspace makes its conversations, documents, and evidence
          available again.
        </p>
      )}
      <CreateWorkspaceDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={async (created) => {
          setWorkspaces((current) => [...current, created]);
          router.refresh();
          setMessage("Workspace created.");
          try {
            const response = await fetch("/api/workspace-selection", {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify({ workspaceId: created.id }),
            });
            if (!response.ok) throw new Error("selection failed");
            router.push(routes.workspace(created.id));
            router.refresh();
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
