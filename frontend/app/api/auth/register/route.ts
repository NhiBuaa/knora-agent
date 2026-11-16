import { NextResponse } from "next/server";
import {
  encodeSession,
  sessionCookie,
  type KnoraSession,
} from "@/lib/auth/session";
import { getAuthProvider } from "@/lib/auth/provider";
import { registerWithPassword } from "@/lib/auth/supabase";
import { resolveCurrentWorkspace } from "@/lib/auth/workspace";
import {
  encodePreference,
  preferenceCookie,
} from "@/lib/auth/workspace-preference";

export async function GET(request: Request) {
  if (getAuthProvider() === "supabase") {
    return NextResponse.redirect(new URL("/auth/register", request.url));
  }
  return NextResponse.json({ error: "METHOD_NOT_ALLOWED" }, { status: 405 });
}

export async function POST(request: Request) {
  if (getAuthProvider() !== "supabase") {
    return NextResponse.json({ error: "METHOD_NOT_ALLOWED" }, { status: 405 });
  }

  const origin = request.headers.get("origin");
  const internal = new URL(request.url);
  const host = request.headers.get("host") ?? internal.host;
  const protocol =
    request.headers.get("x-forwarded-proto") ?? internal.protocol.slice(0, -1);
  const expectedOrigin = `${protocol}://${host}`;
  if (
    origin !== expectedOrigin ||
    request.headers.get("sec-fetch-site") === "cross-site"
  ) {
    return NextResponse.json(
      { error: "CROSS_ORIGIN_REQUEST" },
      { status: 403 },
    );
  }

  const contentLength = Number(request.headers.get("content-length") || "0");
  if (contentLength > 4096) {
    return NextResponse.json({ error: "PAYLOAD_TOO_LARGE" }, { status: 413 });
  }

  let body: { email?: string; password?: string; displayName?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "INVALID_JSON" }, { status: 400 });
  }

  const { email, password, displayName } = body;
  if (
    !email ||
    !password ||
    typeof email !== "string" ||
    typeof password !== "string"
  ) {
    return NextResponse.json({ error: "MISSING_CREDENTIALS" }, { status: 400 });
  }

  let session: KnoraSession;
  try {
    session = await registerWithPassword(email.trim(), password, displayName);
  } catch (err: unknown) {
    const message = (err as Error)?.message || "Registration failed";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  const sessionCookieValue = sessionCookie(
    await encodeSession(session),
    session.sessionExpiresAt,
  );

  let destination = "/workspaces";
  let selectedWorkspaceId: string | null = null;
  try {
    const resolution = await resolveCurrentWorkspace(
      {
        issuer: session.issuer ?? "",
        subject: session.subject,
        accessToken: session.accessToken,
      },
      null,
    );
    selectedWorkspaceId = resolution.workspace?.id ?? null;
  } catch {
    // Preserve session when registration succeeds but workspace resolution has a transient error
    destination = "/workspaces?retry=1";
  }

  const response = NextResponse.json({ success: true, redirect: destination });
  response.cookies.set(
    sessionCookieValue.name,
    sessionCookieValue.value,
    sessionCookieValue.options as never,
  );

  if (selectedWorkspaceId && session.issuer) {
    const prefCookie = preferenceCookie(
      await encodePreference(selectedWorkspaceId, {
        issuer: session.issuer,
        subject: session.subject,
      }),
    );
    response.cookies.set(
      prefCookie.name,
      prefCookie.value,
      prefCookie.options as never,
    );
  }

  return response;
}
