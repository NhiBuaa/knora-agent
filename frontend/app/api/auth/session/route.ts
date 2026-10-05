import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
export async function GET() {
  let session;
  try {
    session = await getSession(true);
  } catch {
    return NextResponse.json(
      { error: "SESSION_REFRESH_UNAVAILABLE" },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }
  if (!session)
    return NextResponse.json(
      { session: null },
      { headers: { "cache-control": "no-store" } },
    );
  return NextResponse.json(
    {
      session: {
        subject: session.subject,
        workspaceIds: session.workspaceIds,
        capabilities: session.capabilities,
      },
    },
    { headers: { "cache-control": "no-store" } },
  );
}
