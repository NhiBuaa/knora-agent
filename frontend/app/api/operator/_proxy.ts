import { NextResponse } from "next/server";
import { getSession } from "../../../lib/auth/session";
import { cookies } from "next/headers";
import {
  decodePreference,
  WORKSPACE_PREFERENCE_COOKIE,
} from "../../../lib/auth/workspace-preference";
import { forwardOperatorRequest } from "../../../lib/operator/api";

export async function proxyOperatorPath(
  pathForSession: (workspaceId: string) => string,
  requestedWorkspaceId?: string | null,
): Promise<Response> {
  const session = await getSession();
  if (!session)
    return NextResponse.json({ detail: "UNAUTHENTICATED" }, { status: 401 });
  if (!session.issuer)
    return NextResponse.json({ detail: "UNAUTHENTICATED" }, { status: 401 });
  if (!session.capabilities.includes("operator:read"))
    return NextResponse.json({ detail: "FORBIDDEN" }, { status: 403 });
  let workspaceId = requestedWorkspaceId || null;
  try {
    if (!workspaceId)
      workspaceId = await decodePreference(
        (await cookies()).get(WORKSPACE_PREFERENCE_COOKIE)?.value,
        { issuer: session.issuer, subject: session.subject },
      );
  } catch {
    return NextResponse.json(
      { detail: "WORKSPACE_RESOLUTION_UNAVAILABLE" },
      { status: 503 },
    );
  }
  if (!workspaceId)
    return NextResponse.json(
      { detail: "WORKSPACE_SELECTION_REQUIRED" },
      { status: 409 },
    );
  const baseUrl = process.env.KNORA_BACKEND_URL ?? "http://127.0.0.1:8000";
  return forwardOperatorRequest(
    `${baseUrl}${pathForSession(encodeURIComponent(workspaceId))}`,
    { accessToken: session.accessToken },
  );
}
