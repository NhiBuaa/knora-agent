import { NextRequest, NextResponse } from "next/server";
import {
  decodeSession,
  encodeSession,
  sessionCookie,
  clearSessionCookie,
  clearLegacySessionCookie,
  SESSION_COOKIE_NAME,
  LEGACY_SESSION_COOKIE_NAME,
} from "@/lib/auth/session";
import { isSessionRevoked, renewSession } from "@/lib/auth/session-refresh";

export async function middleware(request: NextRequest) {
  const legacyValue = request.cookies.get(LEGACY_SESSION_COOKIE_NAME)?.value;
  const rawValue = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  const previous = await decodeSession(rawValue);

  if (!previous) {
    if (rawValue || legacyValue) {
      const response = NextResponse.next();
      if (rawValue) {
        const c = clearSessionCookie();
        response.cookies.set(c.name, c.value, c.options as never);
      }
      if (legacyValue) {
        const c = clearLegacySessionCookie();
        response.cookies.set(c.name, c.value, c.options as never);
      }
      return response;
    }
    return NextResponse.next();
  }

  try {
    const session = await renewSession(previous);
    if (session === previous && !legacyValue) return NextResponse.next();

    let cookie;
    if (session) {
      const encoded = await encodeSession(session);
      const now = Math.floor(Date.now() / 1000);
      if (
        isSessionRevoked(session.sessionId) ||
        session.sessionExpiresAt <= now ||
        session.refreshExpiresAt <= now
      ) {
        cookie = clearSessionCookie();
      } else {
        cookie = sessionCookie(encoded, session);
      }
    } else {
      cookie = clearSessionCookie();
    }

    if (cookie.value) {
      request.cookies.set(cookie.name, cookie.value);
    } else {
      request.cookies.delete(cookie.name);
    }
    if (legacyValue) {
      request.cookies.delete(LEGACY_SESSION_COOKIE_NAME);
    }

    const response = NextResponse.next({
      request: { headers: request.headers },
    });
    response.cookies.set(cookie.name, cookie.value, cookie.options as never);
    if (legacyValue) {
      const c = clearLegacySessionCookie();
      response.cookies.set(c.name, c.value, c.options as never);
    }
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
