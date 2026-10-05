import React from "react";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import type {
  KnoraApiPath,
  WorkspaceListResponse,
} from "@/generated/knora-openapi";
import { ArchivedWorkspaceList } from "@/components/workspaces/ArchivedWorkspaceList";
import { knoraRequest } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";
import { readEntryWorkspace } from "@/lib/auth/workspace";
import {
  decodePreference,
  WORKSPACE_PREFERENCE_COOKIE,
} from "@/lib/auth/workspace-preference";
import { routes } from "@/lib/navigation/routes";

export default async function ArchivedWorkspacesPage() {
  const session = await getSession();
  if (!session) redirect("/api/auth/login");
  try {
    const page = (await knoraRequest(
      "/v1/workspaces?archived=true&limit=20" as KnoraApiPath,
      { accessToken: session.accessToken },
    )) as WorkspaceListResponse;
    let selected: string | null = null;
    if (session.issuer) {
      const hint = await decodePreference(
        (await cookies()).get(WORKSPACE_PREFERENCE_COOKIE)?.value,
        { issuer: session.issuer, subject: session.subject },
      );
      selected = await readEntryWorkspace(
        { ...session, issuer: session.issuer },
        hint,
      );
    }
    return (
      <ArchivedWorkspaceList
        initialWorkspaces={page.items}
        nextCursor={page.next_cursor}
        backHref={selected ? routes.workspace(selected) : "/workspaces"}
      />
    );
  } catch {
    return (
      <p role="alert">Unable to load archived Workspaces. Retry this page.</p>
    );
  }
}
