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
    logoutDestination(expectedOrigin),
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

function logoutDestination(expectedOrigin: string): URL {
  const local = new URL("/?signed-out=1", expectedOrigin);
  const issuer = process.env.KEYCLOAK_ISSUER;
  const configuredReturn = process.env.KEYCLOAK_POST_LOGOUT_REDIRECT_URI;
  if (!issuer || !configuredReturn) return local;
  try {
    const issuerUrl = new URL(issuer);
    const returnUrl = new URL(configuredReturn);
    if (
      !["http:", "https:"].includes(issuerUrl.protocol) ||
      issuerUrl.username ||
      issuerUrl.password ||
      issuerUrl.search ||
      issuerUrl.hash ||
      returnUrl.origin !== expectedOrigin ||
      returnUrl.pathname !== "/" ||
      (returnUrl.search && returnUrl.search !== "?signed-out=1") ||
      returnUrl.hash
    )
      return local;
    const endpoint = new URL(issuerUrl);
    endpoint.pathname = `${issuerUrl.pathname.replace(/\/$/, "")}/protocol/openid-connect/logout`;
    endpoint.searchParams.set(
      "client_id",
      process.env.KEYCLOAK_CLIENT_ID ?? "knora-web",
    );
    endpoint.searchParams.set("post_logout_redirect_uri", returnUrl.toString());
    endpoint.searchParams.set("state", "knora-logout-complete");
    return endpoint;
  } catch {
    return local;
  }
}
