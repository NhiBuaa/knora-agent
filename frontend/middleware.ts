import { NextRequest, NextResponse } from "next/server";
import {
  decodeSession,
  encodeSession,
  sessionCookie,
  clearSessionCookie,
  SESSION_COOKIE_NAME,
} from "@/lib/auth/session";
import { renewSession } from "@/lib/auth/session-refresh";

export async function middleware(request: NextRequest) {
  const previous = await decodeSession(
    request.cookies.get(SESSION_COOKIE_NAME)?.value,
  );
  if (!previous) return NextResponse.next();
  try {
    const session = await renewSession(previous);
    if (session === previous) return NextResponse.next();
    const cookie = session
      ? sessionCookie(await encodeSession(session), session.refreshExpiresAt)
      : clearSessionCookie();
    request.cookies.set(cookie.name, cookie.value);
    const response = NextResponse.next({
      request: { headers: request.headers },
    });
    response.cookies.set(cookie.name, cookie.value, cookie.options as never);
    return response;
  } catch {
    return NextResponse.json(
      { error: "SESSION_REFRESH_UNAVAILABLE" },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }
}
export const config = {
  runtime: "nodejs",
  matcher: ["/", "/workspaces/:path*", "/operator/:path*"],
};
