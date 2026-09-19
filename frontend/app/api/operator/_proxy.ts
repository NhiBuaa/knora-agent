import { NextResponse } from "next/server";
import { getSession } from "../../../lib/auth/session";
import { selectWorkspace } from "../../../lib/auth/workspace";
import { forwardOperatorRequest } from "../../../lib/operator/api";

export async function proxyOperatorPath(pathForSession: (workspaceId: string) => string): Promise<Response> {
  const session = await getSession();
  if (!session) return NextResponse.json({ detail: "UNAUTHENTICATED" }, { status: 401 });
  const workspaceId = selectWorkspace(session.workspaceIds);
  if (!workspaceId) return NextResponse.json({ detail: "WORKSPACE_ACCESS_DENIED" }, { status: 403 });
  const baseUrl = process.env.KNORA_BACKEND_URL ?? "http://127.0.0.1:8000";
  return forwardOperatorRequest(`${baseUrl}${pathForSession(encodeURIComponent(workspaceId))}`, { accessToken: session.accessToken });
}
