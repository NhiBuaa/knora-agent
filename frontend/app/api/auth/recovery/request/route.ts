import { NextResponse } from "next/server";
import { getAuthProvider } from "@/lib/auth/provider";
import { requestRecovery } from "@/lib/auth/supabase-recovery";

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

  let body: { email?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "INVALID_JSON" }, { status: 400 });
  }

  const email = body.email;
  if (!email || typeof email !== "string" || !email.includes("@")) {
    return NextResponse.json(
      { error: "Enter a valid email address and try again." },
      { status: 400 },
    );
  }

  try {
    await requestRecovery(email.trim());
    return NextResponse.json({ success: true });
  } catch (err: unknown) {
    if ((err as Error)?.message === "RATE_LIMIT_EXCEEDED") {
      return NextResponse.json(
        {
          error: "Too many recovery attempts. Please wait before trying again.",
        },
        { status: 429 },
      );
    }
    return NextResponse.json(
      { error: "Unable to process recovery request. Try again later." },
      { status: 503 },
    );
  }
}
