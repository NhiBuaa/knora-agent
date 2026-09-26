import type {
  KnoraApiPath,
  ResolutionResponse,
  WorkspaceListResponse,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { KnoraApiError, knoraRequest } from "@/lib/api/client";

export async function resolveCurrentWorkspace(
  identity: { issuer: string; subject: string; accessToken: string },
  hintId: string | null,
): Promise<ResolutionResponse> {
  if (!identity.issuer || !identity.subject || !identity.accessToken)
    throw new Error("Authenticated identity is incomplete");
  return knoraRequest("/v1/workspaces/resolve", {
    method: "POST",
    accessToken: identity.accessToken,
    body: JSON.stringify({ hint_id: hintId }),
  });
}

export async function readEntryWorkspace(
  identity: { issuer: string; subject: string; accessToken: string },
  hintId: string | null,
): Promise<string | null> {
  if (!identity.issuer || !identity.subject || !identity.accessToken)
    throw new Error("Authenticated identity is incomplete");
  if (hintId) {
    try {
      const hinted = (await knoraRequest(
        `/v1/workspaces/${encodeURIComponent(hintId)}` as KnoraApiPath,
        { accessToken: identity.accessToken },
      )) as WorkspaceResponse;
      if (hinted.id === hintId && !hinted.archived) return hinted.id;
    } catch (error) {
      if (
        !(error instanceof KnoraApiError) ||
        ![403, 404].includes(error.status)
      )
        throw error;
      // A stale or foreign hint has no authority; use the owner list.
    }
  }
  const page = (await knoraRequest(
    "/v1/workspaces?archived=false&limit=1" as KnoraApiPath,
    { accessToken: identity.accessToken },
  )) as WorkspaceListResponse;
  return page.items[0]?.id ?? null;
}
