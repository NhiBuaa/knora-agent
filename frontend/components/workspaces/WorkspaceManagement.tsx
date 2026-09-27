"use client";

import React, { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { WorkspaceResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
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
  const [archived, setArchived] = useState<WorkspaceResponse[]>([]);
  const [archivedCursor, setArchivedCursor] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [name, setName] = useState("");
  const createKey = useRef<string | null>(null);
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

  async function loadArchived() {
    setError(null);
    try {
      const response = await browserRequest(
        "/v1/workspaces?archived=true&limit=20",
      );
      if (!response.ok) throw new Error("archive read failed");
      const page = (await response.json()) as {
        items: WorkspaceResponse[];
        next_cursor: string | null;
      };
      setArchived(page.items);
      setArchivedCursor(page.next_cursor);
      setShowArchived(true);
    } catch {
      setError("Unable to load archived Workspaces. Retry.");
    }
  }

  async function loadMoreArchived() {
    if (!archivedCursor) return;
    setError(null);
    try {
      const response = await browserRequest(
        `/v1/workspaces?archived=true&limit=20&cursor=${encodeURIComponent(archivedCursor)}`,
      );
      if (!response.ok) throw new Error("archive page unavailable");
      const page = (await response.json()) as {
        items: WorkspaceResponse[];
        next_cursor: string | null;
      };
      setArchived((current) => {
        const seen = new Set(current.map((item) => item.id));
        return [...current, ...page.items.filter((item) => !seen.has(item.id))];
      });
      setArchivedCursor(page.next_cursor);
    } catch {
      setError("Unable to load more archived Workspaces. Retry.");
    }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const proposed = name.trim();
    if (!proposed) return;
    setError(null);
    try {
      const response = await browserRequest("/v1/workspaces", {
        method: "POST",
        headers: {
          "Idempotency-Key": (createKey.current ??= crypto.randomUUID()),
        },
        body: JSON.stringify({ name: proposed }),
      });
      if (!response.ok) throw new Error("creation failed");
      const created = (await response.json()) as WorkspaceResponse;
      setWorkspaces((current) => [...current, created]);
      router.refresh();
      createKey.current = null;
      setName("");
      setMessage("Workspace created.");
    } catch {
      setError("Unable to create Workspace. Retry.");
    }
  }

  async function restore(workspace: WorkspaceResponse) {
    setError(null);
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspace.id)}/restore`,
        { method: "POST", headers: { "If-Match": String(workspace.revision) } },
      );
      if (!response.ok) throw new Error("restore failed");
      const restored = (await response.json()) as WorkspaceResponse;
      setArchived((current) =>
        current.filter((item) => item.id !== restored.id),
      );
      setWorkspaces((current) => [...current, restored]);
      router.refresh();
      setMessage("Workspace restored.");
    } catch {
      setError("Unable to restore Workspace. Reload and retry.");
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
    if (
      !window.confirm(
        "Archive this Workspace? Its documents and Conversations become read-only until restored.",
      )
    )
      return;
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
      setArchived((current) => [...current, archivedWorkspace]);
      router.refresh();
      setMessage("Workspace archived. Its retained content remains readable.");
    } catch {
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
        }
      } else {
        const cleared = await fetch("/api/workspace-selection", {
          method: "DELETE",
        });
        if (!cleared.ok) {
          setError(
            "Workspace archived. Reload to clear the previous selection.",
          );
        }
      }
    } catch {
      setError(
        "Workspace archived. Reload to select another active Workspace.",
      );
    }
  }

  return (
    <section>
      <h1>Workspaces</h1>
      {!workspaces.length && <p>No active Workspace</p>}
      <ul>
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
            <button type="button" onClick={() => void archive(workspace)}>
              Archive {workspace.name}
            </button>
          </li>
        ))}
      </ul>
      {cursor && (
        <button type="button" onClick={() => void loadMore()}>
          Load more Workspaces
        </button>
      )}
      <form onSubmit={(event) => void create(event)}>
        <label htmlFor="new-workspace-name">Workspace name</label>
        <input
          id="new-workspace-name"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
            createKey.current = null;
          }}
        />
        <button type="submit">Create Workspace</button>
      </form>
      <button type="button" onClick={() => void loadArchived()}>
        Show archived Workspaces
      </button>
      {showArchived && (
        <div>
          <ul>
            {archived.map((workspace) => (
              <li key={workspace.id}>
                <Link href={routes.workspace(workspace.id)}>
                  {workspace.name}
                </Link>{" "}
                <button
                  type="button"
                  onClick={() => void restore(workspace)}
                  aria-label={`Restore ${workspace.name}`}
                >
                  Restore
                </button>
              </li>
            ))}
          </ul>
          {archivedCursor && (
            <button type="button" onClick={() => void loadMoreArchived()}>
              Load more archived Workspaces
            </button>
          )}
        </div>
      )}
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
