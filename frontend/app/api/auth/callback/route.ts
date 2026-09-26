import { NextResponse } from "next/server";
import {
  clearAuthorizationTransactionCookie,
  decodeAuthorizationTransaction,
  encodeSession,
  exchangeCode,
  sessionCookie,
  AUTH_TRANSACTION_COOKIE_NAME,
} from "@/lib/auth/session";
import { cookies } from "next/headers";
import { resolveCurrentWorkspace } from "@/lib/auth/workspace";
import {
  clearPreferenceCookie,
  decodePreference,
  encodePreference,
  preferenceCookie,
  WORKSPACE_PREFERENCE_COOKIE,
} from "@/lib/auth/workspace-preference";
import { destinationForResolution } from "@/lib/navigation/routes";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  if (!code || !state)
    return NextResponse.json(
      { error: "INVALID_AUTHORIZATION_CALLBACK" },
      { status: 400 },
    );
  try {
    const transaction = await decodeAuthorizationTransaction(
      (await cookies()).get(AUTH_TRANSACTION_COOKIE_NAME)?.value,
    );
    if (!transaction || transaction.state !== state)
      return NextResponse.json(
        { error: "INVALID_AUTHORIZATION_CALLBACK" },
        { status: 400 },
      );
    const session = await exchangeCode(
      code,
      transaction.redirectUri,
      transaction.codeVerifier,
      transaction.nonce,
    );
    if (!session.issuer) throw new Error("OIDC issuer missing");
    const previousPreference = (await cookies()).get(
      WORKSPACE_PREFERENCE_COOKIE,
    )?.value;
    const hint = await decodePreference(previousPreference, {
      issuer: session.issuer,
      subject: session.subject,
    });
    const resolution = await resolveCurrentWorkspace(
      {
        issuer: session.issuer,
        subject: session.subject,
        accessToken: session.accessToken,
      },
      hint,
    );
    const origin = process.env.NEXT_PUBLIC_APP_ORIGIN ?? request.url;
    const response = NextResponse.redirect(
      new URL(destinationForResolution(resolution), origin),
    );
    const value = await encodeSession(session);
    const cookie = sessionCookie(value);
    response.cookies.set(cookie.name, cookie.value, cookie.options as never);
    if (resolution.state === "ACTIVE" && resolution.workspace) {
      const selected = preferenceCookie(
        await encodePreference(resolution.workspace.id, {
          issuer: session.issuer,
          subject: session.subject,
        }),
      );
      response.cookies.set(
        selected.name,
        selected.value,
        selected.options as never,
      );
    } else {
      const cleared = clearPreferenceCookie();
      response.cookies.set(
        cleared.name,
        cleared.value,
        cleared.options as never,
      );
    }
    const transactionCookie = clearAuthorizationTransactionCookie();
    response.cookies.set(
      transactionCookie.name,
      transactionCookie.value,
      transactionCookie.options as never,
    );
    return response;
  } catch {
    return NextResponse.json(
      { error: "AUTHENTICATION_FAILED" },
      { status: 401 },
    );
  }
}
