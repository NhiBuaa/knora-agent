import React from "react";
import { redirect } from "next/navigation";
import type { WorkspaceListResponse } from "@/generated/knora-openapi";
import { WorkspaceManagement } from "@/components/workspaces/WorkspaceManagement";
import { knoraRequest } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";

export default async function WorkspacesPage() {
  const session = await getSession();
  if (!session) redirect("/api/auth/login");
  let page: WorkspaceListResponse;
  try {
    page = (await knoraRequest(
      "/v1/workspaces?archived=false&limit=20" as "/v1/workspaces",
      {
        accessToken: session.accessToken,
      },
    )) as WorkspaceListResponse;
  } catch {
    return <p role="alert">Unable to load Workspaces. Retry this page.</p>;
  }
  return (
    <WorkspaceManagement
      initialWorkspaces={page.items}
      nextCursor={page.next_cursor}
    />
  );
}
