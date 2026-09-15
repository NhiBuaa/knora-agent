import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { forwardOperatorRequest, sessionFromCookies } from "../../../lib/operator/api";

export async function proxyOperatorPath(pathForSession: (workspaceId: string) => string): Promise<Response> {
  const cookieStore = await cookies();
  const session = sessionFromCookies({ accessToken: cookieStore.get("knora_access_token")?.value, workspaceId: cookieStore.get("knora_workspace_id")?.value });
  if (!session) return NextResponse.json({ detail: "UNAUTHENTICATED" }, { status: 401 });
  const baseUrl = process.env.KNORA_BACKEND_URL ?? "http://127.0.0.1:8000";
  return forwardOperatorRequest(`${baseUrl}${pathForSession(encodeURIComponent(session.workspaceId))}`, session);
}
