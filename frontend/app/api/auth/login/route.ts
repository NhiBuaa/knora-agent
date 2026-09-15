import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const authorize = process.env.KEYCLOAK_AUTHORIZATION_URL;
  if (!authorize) return NextResponse.json({ error: "OIDC_NOT_CONFIGURED" }, { status: 503 });
  const url = new URL(authorize);
  url.searchParams.set("client_id", process.env.KEYCLOAK_CLIENT_ID ?? "knora-web");
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", "openid profile");
  url.searchParams.set("redirect_uri", process.env.KEYCLOAK_REDIRECT_URI ?? new URL("/api/auth/callback", request.url).toString());
  return NextResponse.redirect(url);
}
