import { headers } from "next/headers";

export function buildOperatorBffUrl(origin: string, path: string): string {
  if (!path.startsWith("/api/operator/")) throw new Error("Operator pages must use the operator BFF");
  return new URL(path, origin).toString();
}

export async function readOperatorBff(path: string): Promise<Response> {
  const requestHeaders = await headers();
  const origin = process.env.NEXT_PUBLIC_APP_ORIGIN ?? `${requestHeaders.get("x-forwarded-proto") ?? "http"}://${requestHeaders.get("host") ?? "127.0.0.1:3000"}`;
  return fetch(buildOperatorBffUrl(origin, path), {
    headers: { Accept: "application/json", Cookie: requestHeaders.get("cookie") ?? "" },
  });
}
