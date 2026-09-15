import { NextResponse } from "next/server";
import { clearAuthorizationTransactionCookie, decodeAuthorizationTransaction, encodeSession, exchangeCode, sessionCookie, AUTH_TRANSACTION_COOKIE_NAME } from "@/lib/auth/session";
import { cookies } from "next/headers";

export async function GET(request: Request) {
  const url = new URL(request.url); const code = url.searchParams.get("code"); const state = url.searchParams.get("state");
  if (!code || !state) return NextResponse.json({ error: "INVALID_AUTHORIZATION_CALLBACK" }, { status: 400 });
  try {
    const transaction = await decodeAuthorizationTransaction((await cookies()).get(AUTH_TRANSACTION_COOKIE_NAME)?.value);
    if (!transaction || transaction.state !== state) return NextResponse.json({ error: "INVALID_AUTHORIZATION_CALLBACK" }, { status: 400 });
    const session = await exchangeCode(code, transaction.redirectUri, transaction.codeVerifier, transaction.nonce);
    const response = NextResponse.redirect(new URL("/app", request.url));
    const value = await encodeSession(session);
    const cookie = sessionCookie(value); response.cookies.set(cookie.name, cookie.value, cookie.options as never); return response;
  } catch { return NextResponse.json({ error: "AUTHENTICATION_FAILED" }, { status: 401 }); }
}
