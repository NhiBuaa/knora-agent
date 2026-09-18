import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";

export function selectWorkspace(workspaceIds: string[], requested?: string | null): string | null {
  if (requested && workspaceIds.includes(requested)) return requested;
  return workspaceIds[0] ?? null;
}

export async function requireWorkspace(requested?: string | null): Promise<{ workspaceId: string; capabilities: string[] }> {
  const session = await getSession();
  if (!session) redirect("/");
  const workspaceId = selectWorkspace(session.workspaceIds, requested);
  if (!workspaceId) redirect("/");
  return { workspaceId, capabilities: session.capabilities };
}
