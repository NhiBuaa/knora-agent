import React from "react";
import { redirect } from "next/navigation";
import type {
  ConversationResponse,
  ConversationListResponse,
  KnoraApiPath,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { ConversationView } from "@/components/conversations/ConversationView";
import { WorkspaceSelector } from "@/components/workspaces/WorkspaceSelector";
import { knoraRequest } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ workspaceId: string; conversationId: string }>;
}) {
  const session = await getSession();
  if (!session) redirect("/api/auth/login");
  const { workspaceId, conversationId } = await params;
  try {
    const [workspace, conversation, conversations] = await Promise.all([
      knoraRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}` as KnoraApiPath,
        { accessToken: session.accessToken },
      ) as Promise<WorkspaceResponse>,
      knoraRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations/${encodeURIComponent(conversationId)}` as KnoraApiPath,
        { accessToken: session.accessToken },
      ) as Promise<ConversationResponse>,
      knoraRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations?archived=false&limit=20` as KnoraApiPath,
        { accessToken: session.accessToken },
      ) as Promise<ConversationListResponse>,
    ]);
    return (
      <ConversationView
        workspaceId={workspaceId}
        conversation={conversation}
        workspaceArchived={workspace.archived}
        workspaceRevision={workspace.revision}
        workspaceName={workspace.name}
        workspaceSelector={
          <WorkspaceSelector
            workspaceId={workspaceId}
            workspaceName={workspace.name}
            disabled={workspace.archived}
          />
        }
        initialConversations={conversations.items}
        nextCursor={conversations.next_cursor}
        identityScope={
          session.issuer
            ? { issuer: session.issuer, subject: session.subject }
            : undefined
        }
      />
    );
  } catch {
    return <p role="alert">Unable to load this Conversation.</p>;
  }
}
