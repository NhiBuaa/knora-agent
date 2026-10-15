import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getSession } from "@/lib/auth/session";
import {
  decodePreference,
  WORKSPACE_PREFERENCE_COOKIE,
} from "@/lib/auth/workspace-preference";

function failure(detail: string, status: number): Response {
  return NextResponse.json(
    { detail },
    { status, headers: { "cache-control": "no-store" } },
  );
}

async function boundedBody(
  request: Request,
  limit: number,
): Promise<Uint8Array> {
  const reader = request.body?.getReader();
  const parts: Uint8Array[] = [];
  let length = 0;
  if (reader) {
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        length += value.byteLength;
        if (length > limit) {
          await reader.cancel();
          throw new RangeError("Request body too large");
        }
        parts.push(value);
      }
    } finally {
      reader.releaseLock();
    }
  }
  const body = new Uint8Array(length);
  let offset = 0;
  for (const part of parts) {
    body.set(part, offset);
    offset += part.byteLength;
  }
  return body;
}

/** Only fixed route handlers construct paths; browser input never selects a backend endpoint. */
export async function proxyEvaluationPath(
  request: Request,
  pathForWorkspace: (workspaceId: string) => string,
  capabilities: readonly string[] = [],
  bodyKind: "none" | "json" | "multipart" = "none",
): Promise<Response> {
  if (request.method !== "GET") {
    const internal = new URL(request.url);
    const host = request.headers.get("host") ?? internal.host;
    const protocol =
      request.headers.get("x-forwarded-proto") ??
      internal.protocol.slice(0, -1);
    if (
      request.headers.get("origin") !== `${protocol}://${host}` ||
      request.headers.get("sec-fetch-site") === "cross-site"
    ) {
      return failure("CROSS_ORIGIN_REQUEST", 403);
    }
  }
  let session;
  try {
    session = await getSession(true);
  } catch {
    return failure("SESSION_REFRESH_UNAVAILABLE", 503);
  }
  if (!session?.issuer) return failure("UNAUTHENTICATED", 401);
  if (
    !["operator:read", ...capabilities].every((capability) =>
      session.capabilities.includes(capability),
    )
  ) {
    return failure("FORBIDDEN", 403);
  }
  let workspaceId = new URL(request.url).searchParams.get("workspaceId");
  try {
    if (!workspaceId) {
      workspaceId = await decodePreference(
        (await cookies()).get(WORKSPACE_PREFERENCE_COOKIE)?.value,
        {
          issuer: session.issuer,
          subject: session.subject,
        },
      );
    }
  } catch {
    return failure("WORKSPACE_RESOLUTION_UNAVAILABLE", 503);
  }
  if (!workspaceId) return failure("WORKSPACE_SELECTION_REQUIRED", 409);
  const headers = new Headers({
    Authorization: `Bearer ${session.accessToken}`,
    Accept: "application/json",
  });
  let body: Uint8Array | undefined;
  if (bodyKind !== "none") {
    const contentType = request.headers.get("content-type") ?? "";
    if (
      bodyKind === "json"
        ? !/^application\/json(?:;|$)/i.test(contentType)
        : !/^multipart\/form-data;.*boundary=/i.test(contentType)
    ) {
      return failure("UNSUPPORTED_CONTENT_TYPE", 415);
    }
    try {
      body = await boundedBody(
        request,
        bodyKind === "json" ? 256 * 1024 : 26 * 1024 * 1024,
      );
    } catch (error) {
      return failure(
        error instanceof RangeError
          ? "REQUEST_TOO_LARGE"
          : "INVALID_REQUEST_BODY",
        error instanceof RangeError ? 413 : 400,
      );
    }
    headers.set("content-type", contentType);
  }
  const idempotencyKey = request.headers.get("idempotency-key");
  if (idempotencyKey) headers.set("idempotency-key", idempotencyKey);
  try {
    const response = await fetch(
      `${process.env.KNORA_BACKEND_URL ?? "http://127.0.0.1:8000"}${pathForWorkspace(encodeURIComponent(workspaceId))}`,
      {
        method: request.method,
        headers,
        body: body as BodyInit | undefined,
        cache: "no-store",
        redirect: "error",
      },
    );
    const responseHeaders = new Headers({
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    });
    for (const key of ["content-type", "content-disposition", "retry-after"]) {
      const value = response.headers.get(key);
      if (value) responseHeaders.set(key, value);
    }
    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return failure("EVALUATION_UNAVAILABLE", 503);
  }
}
