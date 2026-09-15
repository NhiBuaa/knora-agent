import { NextResponse } from "next/server";
import { authorizationTransactionCookie, createAuthorizationTransaction, encodeAuthorizationTransaction } from "@/lib/auth/session";

export async function GET(request: Request) {
  const authorize = process.env.KEYCLOAK_AUTHORIZATION_URL;
  if (!authorize) return NextResponse.json({ error: "OIDC_NOT_CONFIGURED" }, { status: 503 });
  const redirectUri = process.env.KEYCLOAK_REDIRECT_URI ?? new URL("/api/auth/callback", request.url).toString();
  const transaction = createAuthorizationTransaction(redirectUri);
  const url = new URL(authorize);
  url.searchParams.set("client_id", process.env.KEYCLOAK_CLIENT_ID ?? "knora-web");
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", "openid profile");
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("state", transaction.state);
  url.searchParams.set("nonce", transaction.nonce);
  url.searchParams.set("code_challenge", transaction.codeChallenge);
  url.searchParams.set("code_challenge_method", "S256");
  const response = NextResponse.redirect(url);
  const cookie = authorizationTransactionCookie(await encodeAuthorizationTransaction(transaction));
  response.cookies.set(cookie.name, cookie.value, cookie.options as never);
  return response;
}
