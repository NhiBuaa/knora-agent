import React from "react";
import type {
  KnoraApiPath,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { DocumentList } from "@/components/documents/DocumentList";
import { knoraRequest } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";
export default async function DocumentsPage() {
  const session = await getSession();
  const workspaceId = session?.workspaceIds[0];
  if (!workspaceId)
    return <p role="alert">No workspace is available for this session.</p>;
  let workspace: WorkspaceResponse;
  try {
    workspace = (await knoraRequest(
      `/v1/workspaces/${encodeURIComponent(workspaceId)}` as KnoraApiPath,
      { accessToken: session.accessToken },
    )) as WorkspaceResponse;
  } catch {
    return <p role="alert">Unable to load this Workspace. Retry the page.</p>;
  }
  return (
    <DocumentList
      workspaceId={workspaceId}
      capabilities={session?.capabilities ?? []}
      workspaceArchived={workspace.archived}
    />
  );
}
