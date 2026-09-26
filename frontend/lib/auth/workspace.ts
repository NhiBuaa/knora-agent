import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import type { ResolutionResponse } from "@/generated/knora-openapi";
import { knoraRequest } from "@/lib/api/client";

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

export function selectWorkspace(
  workspaceIds: string[],
  requested?: string | null,
): string | null {
  if (requested && workspaceIds.includes(requested)) return requested;
  return workspaceIds[0] ?? null;
}

export async function requireWorkspace(
  requested?: string | null,
): Promise<{ workspaceId: string; capabilities: string[] }> {
  const session = await getSession();
  if (!session) redirect("/");
  const workspaceId = selectWorkspace(session.workspaceIds, requested);
  if (!workspaceId) redirect("/");
  return { workspaceId, capabilities: session.capabilities };
}
