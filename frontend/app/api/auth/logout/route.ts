import { NextResponse } from "next/server";
import { clearSessionCookie } from "@/lib/auth/session";
import { clearPreferenceCookie } from "@/lib/auth/workspace-preference";

export async function POST(request: Request) {
  const origin = request.headers.get("origin");
  if (
    origin !== new URL(request.url).origin ||
    request.headers.get("sec-fetch-site") === "cross-site"
  )
    return NextResponse.json(
      { error: "CROSS_ORIGIN_REQUEST" },
      { status: 403 },
    );
  const response = NextResponse.json({ ok: true });
  const cookie = clearSessionCookie();
  response.cookies.set(cookie.name, cookie.value, cookie.options as never);
  const preference = clearPreferenceCookie();
  response.cookies.set(
    preference.name,
    preference.value,
    preference.options as never,
  );
  return response;
}
