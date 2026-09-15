import { NextResponse } from "next/server";
import { exchangeCode, sessionCookie } from "@/lib/auth/session";

export async function GET(request: Request) {
  const url = new URL(request.url); const code = url.searchParams.get("code");
  if (!code) return NextResponse.json({ error: "MISSING_AUTHORIZATION_CODE" }, { status: 400 });
  try {
    const session = await exchangeCode(code, process.env.KEYCLOAK_REDIRECT_URI ?? new URL("/api/auth/callback", request.url).toString());
    const response = NextResponse.redirect(new URL("/app", request.url));
    const value = await (await import("@/lib/auth/session")).encodeSession(session);
    const cookie = sessionCookie(value); response.cookies.set(cookie.name, cookie.value, cookie.options as never); return response;
  } catch { return NextResponse.json({ error: "AUTHENTICATION_FAILED" }, { status: 401 }); }
}
