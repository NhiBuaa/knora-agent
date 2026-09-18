import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";

type Context = { params: Promise<{ path: string[] }> };
async function forward(request: Request, context: Context) {
  const session = await getSession();
  if (!session) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  const { path } = await context.params;
  const targetPath = `/${path.join("/")}`;
  const base = process.env.KNORA_API_URL ?? "http://localhost:8000";
  const headers = new Headers(request.headers); headers.set("authorization", `Bearer ${session.accessToken}`); headers.delete("host");
  const response = await fetch(`${base}${targetPath}${new URL(request.url).search}`, { method: request.method, headers, body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(), cache: "no-store" });
  return new NextResponse(response.body, { status: response.status, headers: { "content-type": response.headers.get("content-type") ?? "application/json", "cache-control": "no-store" } });
}
export const GET = forward; export const POST = forward; export const PATCH = forward; export const PUT = forward; export const DELETE = forward;
