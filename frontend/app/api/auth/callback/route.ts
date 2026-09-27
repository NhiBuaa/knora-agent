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
    const origin = new URL(transaction.redirectUri).origin;
    const value = await encodeSession(session);
    let destination = "/workspaces?retry=1";
    let selectedWorkspaceId: string | null = null;
    try {
      const resolution = await resolveCurrentWorkspace(
        {
          issuer: session.issuer,
          subject: session.subject,
          accessToken: session.accessToken,
        },
        hint,
      );
      destination = destinationForResolution(resolution);
      selectedWorkspaceId =
        resolution.state === "ACTIVE"
          ? (resolution.workspace?.id ?? null)
          : null;
    } catch {
      // The OIDC code was already exchanged. Keep the session for a retry.
    }
    const response = NextResponse.redirect(new URL(destination, origin));
    const cookie = sessionCookie(value);
    response.cookies.set(cookie.name, cookie.value, cookie.options as never);
    if (selectedWorkspaceId) {
      const selected = preferenceCookie(
        await encodePreference(selectedWorkspaceId, {
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
