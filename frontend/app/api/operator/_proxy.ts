import { NextResponse } from "next/server";
import { getSession } from "../../../lib/auth/session";
import { readEntryWorkspace } from "../../../lib/auth/workspace";
import { forwardOperatorRequest } from "../../../lib/operator/api";

export async function proxyOperatorPath(
  pathForSession: (workspaceId: string) => string,
): Promise<Response> {
  const session = await getSession();
  if (!session)
    return NextResponse.json({ detail: "UNAUTHENTICATED" }, { status: 401 });
  if (!session.issuer)
    return NextResponse.json({ detail: "UNAUTHENTICATED" }, { status: 401 });
  let workspaceId: string | null;
  try {
    workspaceId = await readEntryWorkspace(
      {
        issuer: session.issuer,
        subject: session.subject,
        accessToken: session.accessToken,
      },
      null,
    );
  } catch {
    return NextResponse.json(
      { detail: "WORKSPACE_RESOLUTION_UNAVAILABLE" },
      { status: 503 },
    );
  }
  if (!workspaceId)
    return NextResponse.json(
      { detail: "WORKSPACE_ACCESS_DENIED" },
      { status: 403 },
    );
  const baseUrl = process.env.KNORA_BACKEND_URL ?? "http://127.0.0.1:8000";
  return forwardOperatorRequest(
    `${baseUrl}${pathForSession(encodeURIComponent(workspaceId))}`,
    { accessToken: session.accessToken },
  );
}
