import { NextResponse } from "next/server";
import type {
  KnoraApiPath,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { KnoraApiError, knoraRequest } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";
import {
  clearPreferenceCookie,
  encodePreference,
  preferenceCookie,
} from "@/lib/auth/workspace-preference";

function sameOrigin(request: Request): boolean {
  const internal = new URL(request.url);
  const host = request.headers.get("host") ?? internal.host;
  const protocol =
    request.headers.get("x-forwarded-proto") ?? internal.protocol.slice(0, -1);
  return (
    request.headers.get("origin") === `${protocol}://${host}` &&
    request.headers.get("sec-fetch-site") !== "cross-site"
  );
}

export async function POST(request: Request) {
  if (!sameOrigin(request))
    return NextResponse.json(
      { error: "CROSS_ORIGIN_REQUEST" },
      { status: 403 },
    );
  let session;
  try {
    session = await getSession(true);
  } catch {
    return NextResponse.json(
      { error: "SESSION_REFRESH_UNAVAILABLE" },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }
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
  } catch (error) {
    if (
      error instanceof KnoraApiError &&
      [401, 403, 404].includes(error.status)
    ) {
      return NextResponse.json(
        {
          error:
            error.status === 401
              ? "UNAUTHENTICATED"
              : "WORKSPACE_ACCESS_DENIED",
        },
        { status: error.status, headers: { "cache-control": "no-store" } },
      );
    }
    return NextResponse.json(
      { error: "WORKSPACE_SELECTION_UNAVAILABLE" },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }
}

export async function DELETE(request: Request) {
  if (!sameOrigin(request))
    return NextResponse.json(
      { error: "CROSS_ORIGIN_REQUEST" },
      { status: 403 },
    );
  let session;
  try {
    session = await getSession(true);
  } catch {
    return NextResponse.json(
      { error: "SESSION_REFRESH_UNAVAILABLE" },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }
  if (!session?.issuer)
    return NextResponse.json({ error: "UNAUTHENTICATED" }, { status: 401 });
  const cleared = clearPreferenceCookie();
  const response = NextResponse.json(
    { ok: true },
    { headers: { "cache-control": "no-store" } },
  );
  response.cookies.set(cleared.name, cleared.value, cleared.options as never);
  return response;
}
