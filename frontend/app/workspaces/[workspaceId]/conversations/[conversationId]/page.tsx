import React from "react";
import { redirect } from "next/navigation";
import type {
  ConversationResponse,
  KnoraApiPath,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { ConversationView } from "@/components/conversations/ConversationView";
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
    const [workspace, conversation] = await Promise.all([
      knoraRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}` as KnoraApiPath,
        { accessToken: session.accessToken },
      ) as Promise<WorkspaceResponse>,
      knoraRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations/${encodeURIComponent(conversationId)}` as KnoraApiPath,
        { accessToken: session.accessToken },
      ) as Promise<ConversationResponse>,
    ]);
    return (
      <ConversationView
        workspaceId={workspaceId}
        conversation={conversation}
        workspaceArchived={workspace.archived}
      />
    );
  } catch {
    return <p role="alert">Unable to load this Conversation.</p>;
  }
}
