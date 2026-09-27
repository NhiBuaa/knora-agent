import React from "react";
import { redirect } from "next/navigation";
import type {
  KnoraApiPath,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { DocumentList } from "@/components/documents/DocumentList";
import { knoraRequest } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";

export default async function DocumentsPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const session = await getSession();
  if (!session) redirect("/api/auth/login");
  const { workspaceId } = await params;
  try {
    const workspace = (await knoraRequest(
      `/v1/workspaces/${encodeURIComponent(workspaceId)}` as KnoraApiPath,
      { accessToken: session.accessToken },
    )) as WorkspaceResponse;
    return (
      <DocumentList
        workspaceId={workspaceId}
        capabilities={session.capabilities}
        workspaceArchived={workspace.archived}
      />
    );
  } catch {
    return <p role="alert">Unable to load this Workspace.</p>;
  }
}
