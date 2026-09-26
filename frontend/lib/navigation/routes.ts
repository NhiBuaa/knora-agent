import type { ResolutionResponse } from "@/generated/knora-openapi";

const segment = (value: string) => encodeURIComponent(value);

export const routes = {
  workspace: (workspaceId: string) => `/workspaces/${segment(workspaceId)}`,
  documents: (workspaceId: string) =>
    `/workspaces/${segment(workspaceId)}/documents`,
  document: (workspaceId: string, documentId: string) =>
    `/workspaces/${segment(workspaceId)}/documents/${segment(documentId)}`,
  conversations: (workspaceId: string) =>
    `/workspaces/${segment(workspaceId)}/conversations`,
  conversation: (workspaceId: string, conversationId: string) =>
    `/workspaces/${segment(workspaceId)}/conversations/${segment(conversationId)}`,
};

export function destinationForResolution(
  resolution: ResolutionResponse,
): string {
  return resolution.state === "ACTIVE" && resolution.workspace
    ? routes.workspace(resolution.workspace.id)
    : "/workspaces";
}
