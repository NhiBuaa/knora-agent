import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
export async function GET() { const session = await getSession(); if (!session) return NextResponse.json({ session: null }); return NextResponse.json({ session: { subject: session.subject, workspaceIds: session.workspaceIds, capabilities: session.capabilities } }, { headers: { "cache-control": "no-store" } }); }
