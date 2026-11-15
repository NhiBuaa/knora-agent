import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getAuthProvider } from "@/lib/auth/provider";
import { clearSessionCookie } from "@/lib/auth/session";
import {
  clearRecoveryCookie,
  decodeRecoverySession,
  RECOVERY_COOKIE_NAME,
  updateRecoveredPassword,
} from "@/lib/auth/supabase-recovery";

export async function POST(request: Request) {
  if (getAuthProvider() !== "supabase") {
    return NextResponse.json({ error: "METHOD_NOT_ALLOWED" }, { status: 405 });
  }

  const origin = request.headers.get("origin");
  const internal = new URL(request.url);
  const host = request.headers.get("host") ?? internal.host;
  const protocol =
    request.headers.get("x-forwarded-proto") ?? internal.protocol.slice(0, -1);
  const expectedOrigin = `${protocol}://${host}`;
  if (
    origin !== expectedOrigin ||
    request.headers.get("sec-fetch-site") === "cross-site"
  ) {
    return NextResponse.json(
      { error: "CROSS_ORIGIN_REQUEST" },
      { status: 403 },
    );
  }

  const contentLength = Number(request.headers.get("content-length") || "0");
  if (contentLength > 2048) {
    return NextResponse.json({ error: "PAYLOAD_TOO_LARGE" }, { status: 413 });
  }

  const jar = await cookies();
  const recoveryCookieValue = jar.get(RECOVERY_COOKIE_NAME)?.value;
  const decoded = await decodeRecoverySession(recoveryCookieValue);
  if (!decoded) {
    const response = NextResponse.json(
      {
        error: "Recovery session has expired or is invalid.",
        redirect: "/auth/forgot-password",
      },
      { status: 401 },
    );
    const clearCookie = clearRecoveryCookie();
    response.cookies.set(
      clearCookie.name,
      clearCookie.value,
      clearCookie.options as never,
    );
    return response;
  }

  let body: { password?: string; passwordConfirm?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "INVALID_JSON" }, { status: 400 });
  }

  const { password, passwordConfirm } = body;
  if (
    !password ||
    !passwordConfirm ||
    typeof password !== "string" ||
    typeof passwordConfirm !== "string"
  ) {
    return NextResponse.json(
      { error: "Missing password or password confirmation." },
      { status: 400 },
    );
  }

  if (password !== passwordConfirm) {
    return NextResponse.json(
      { error: "Passwords do not match." },
      { status: 400 },
    );
  }

  if (password.length < 8) {
    return NextResponse.json(
      { error: "Password must be at least 8 characters long." },
      { status: 400 },
    );
  }

  try {
    await updateRecoveredPassword(decoded.session, password);
    const response = NextResponse.json({
      success: true,
      redirect: "/auth/login?reset=1",
    });

    const clearRec = clearRecoveryCookie();
    response.cookies.set(
      clearRec.name,
      clearRec.value,
      clearRec.options as never,
    );

    const clearSess = clearSessionCookie();
    response.cookies.set(
      clearSess.name,
      clearSess.value,
      clearSess.options as never,
    );

    return response;
  } catch (err: unknown) {
    const message = (err as Error)?.message || "Failed to update password.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
