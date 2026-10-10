import React from "react";
import { redirect } from "next/navigation";
import type {
  KnoraApiPath,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { WorkspaceUnavailable } from "@/components/workspaces/WorkspaceHome";
import { KnoraApiError, knoraRequest } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";

export default async function WorkspacePage({
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
    if (!workspace.id) throw new Error("invalid Workspace projection");
  } catch (error) {
    if (error instanceof KnoraApiError && [403, 404].includes(error.status)) {
      return <WorkspaceUnavailable />;
    }
    return <p role="alert">Unable to load this Workspace.</p>;
  }
  redirect(`/workspaces/${encodeURIComponent(workspaceId)}/conversations`);
}
