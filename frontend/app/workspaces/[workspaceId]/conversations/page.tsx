import React from "react";
import { redirect } from "next/navigation";
import type {
  ConversationListResponse,
  KnoraApiPath,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { ConversationHub } from "@/components/conversations/ConversationPanels";
import { knoraRequest } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";

export default async function ConversationsPage({
  params,
  searchParams,
}: {
  params: Promise<{ workspaceId: string }>;
  searchParams: Promise<{ archived?: string }>;
}) {
  const session = await getSession();
  if (!session) redirect("/api/auth/login");
  const { workspaceId } = await params;
  const archived = (await searchParams).archived === "true";
  try {
    const [workspace, page] = await Promise.all([
      knoraRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}` as KnoraApiPath,
        { accessToken: session.accessToken },
      ) as Promise<WorkspaceResponse>,
      knoraRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations?archived=${archived}&limit=20` as KnoraApiPath,
        { accessToken: session.accessToken },
      ) as Promise<ConversationListResponse>,
    ]);
    return (
      <ConversationHub
        workspaceId={workspaceId}
        workspaceName={workspace.name}
        initialConversations={page.items}
        nextCursor={page.next_cursor}
        archived={archived}
        workspaceArchived={workspace.archived}
        identityScope={
          session.issuer
            ? { issuer: session.issuer, subject: session.subject }
            : undefined
        }
      />
    );
  } catch {
    return <p role="alert">Unable to load Conversations.</p>;
  }
}
