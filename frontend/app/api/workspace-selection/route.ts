import { NextResponse } from "next/server";
import type {
  KnoraApiPath,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { knoraRequest } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";
import {
  encodePreference,
  preferenceCookie,
} from "@/lib/auth/workspace-preference";

export async function POST(request: Request) {
  if (
    request.headers.get("origin") !== new URL(request.url).origin ||
    request.headers.get("sec-fetch-site") === "cross-site"
  )
    return NextResponse.json(
      { error: "CROSS_ORIGIN_REQUEST" },
      { status: 403 },
    );
  const session = await getSession();
  if (!session?.issuer)
    return NextResponse.json({ error: "UNAUTHENTICATED" }, { status: 401 });
  let workspaceId: string;
  try {
    const body = (await request.json()) as Record<string, unknown>;
    if (
      !body ||
      typeof body.workspaceId !== "string" ||
      !body.workspaceId ||
      Object.keys(body).length !== 1
    )
      throw new Error("invalid request");
    workspaceId = body.workspaceId;
  } catch {
    return NextResponse.json({ error: "INVALID_REQUEST" }, { status: 400 });
  }
  try {
    const workspace = (await knoraRequest(
      `/v1/workspaces/${encodeURIComponent(workspaceId)}` as KnoraApiPath,
      { accessToken: session.accessToken },
    )) as WorkspaceResponse;
    if (workspace.id !== workspaceId || workspace.archived)
      return NextResponse.json(
        { error: "WORKSPACE_NOT_ACTIVE" },
        { status: 409 },
      );
    const selected = preferenceCookie(
      await encodePreference(workspaceId, {
        issuer: session.issuer,
        subject: session.subject,
      }),
    );
    const response = NextResponse.json(
      { workspaceId },
      { headers: { "cache-control": "no-store" } },
    );
    response.cookies.set(
      selected.name,
      selected.value,
      selected.options as never,
    );
    return response;
  } catch {
    return NextResponse.json(
      { error: "WORKSPACE_SELECTION_UNAVAILABLE" },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }
}
