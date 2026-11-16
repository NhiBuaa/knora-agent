import { NextResponse } from "next/server";
import { getAuthProvider } from "@/lib/auth/provider";
import {
  encodeRecoverySession,
  recoveryCookie,
  verifyRecovery,
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

  let body: { email?: string; code?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "INVALID_JSON" }, { status: 400 });
  }

  const { email, code } = body;
  if (
    !email ||
    !code ||
    typeof email !== "string" ||
    typeof code !== "string"
  ) {
    return NextResponse.json(
      { error: "Missing email or recovery code." },
      { status: 400 },
    );
  }

  const sanitizedCode = code.trim();
  if (!/^\d{6}$/.test(sanitizedCode)) {
    return NextResponse.json(
      { error: "Recovery code must be exactly 6 digits." },
      { status: 400 },
    );
  }

  try {
    const session = await verifyRecovery(email.trim(), sanitizedCode);
    const token = await encodeRecoverySession(session, email.trim());
    const cookie = recoveryCookie(token);

    const response = NextResponse.json({
      success: true,
      redirect: "/auth/new-password",
    });
    response.cookies.set(cookie.name, cookie.value, cookie.options as never);
    return response;
  } catch (err: unknown) {
    const message =
      (err as Error)?.message || "Invalid or expired verification code.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
