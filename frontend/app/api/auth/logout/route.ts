import { NextResponse } from "next/server";
import { clearSessionCookie } from "@/lib/auth/session";
import { clearPreferenceCookie } from "@/lib/auth/workspace-preference";

export async function POST(request: Request) {
  const origin = request.headers.get("origin");
  const internal = new URL(request.url);
  const host = request.headers.get("host") ?? internal.host;
  const protocol =
    request.headers.get("x-forwarded-proto") ?? internal.protocol.slice(0, -1);
  const expectedOrigin = `${protocol}://${host}`;
  if (
    origin !== expectedOrigin ||
    request.headers.get("sec-fetch-site") === "cross-site"
  )
    return NextResponse.json(
      { error: "CROSS_ORIGIN_REQUEST" },
      { status: 403 },
    );
  const response = NextResponse.redirect(
    new URL("/?signed-out=1", expectedOrigin),
    303,
  );
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
