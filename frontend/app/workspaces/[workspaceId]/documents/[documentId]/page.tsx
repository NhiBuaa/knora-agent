import React from "react";
import { redirect } from "next/navigation";
import type {
  KnoraApiPath,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { DocumentDetail } from "@/components/documents/DocumentDetail";
import { knoraRequest } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";

export default async function DocumentPage({
  params,
}: {
  params: Promise<{ workspaceId: string; documentId: string }>;
}) {
  const session = await getSession();
  if (!session) redirect("/api/auth/login");
  const { workspaceId, documentId } = await params;
  try {
    const workspace = (await knoraRequest(
      `/v1/workspaces/${encodeURIComponent(workspaceId)}` as KnoraApiPath,
      { accessToken: session.accessToken },
    )) as WorkspaceResponse;
    return (
      <DocumentDetail
        workspaceId={workspaceId}
        documentId={documentId}
        capabilities={session.capabilities}
        workspaceArchived={workspace.archived}
      />
    );
  } catch {
    return <p role="alert">Unable to load this Workspace.</p>;
  }
}
