import React from "react";
import { TraceView } from "../../../../components/operator/TraceView";
import { isOperatorTrace } from "../../../../lib/operator/api";
import { readOperatorBff } from "../../../../lib/operator/bff";

export default async function TraceDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ traceId: string }>;
  searchParams?: Promise<{ workspaceId?: string }>;
}) {
  const { traceId } = await params;
  const { workspaceId } = (await searchParams) ?? {};
  let response: Response;
  try {
    response = await readOperatorBff(
      `/api/operator/traces/${encodeURIComponent(traceId)}${workspaceId ? `?workspaceId=${encodeURIComponent(workspaceId)}` : ""}`,
    );
  } catch {
    return <p role="status">Trace observation unavailable.</p>;
  }
  if (response.status === 401)
    return <p role="alert">Sign in to inspect this trace.</p>;
  if (response.status === 403)
    return <p role="alert">You are not authorized to inspect this trace.</p>;
  if (response.status === 409)
    return <p role="status">Select a workspace to inspect this trace.</p>;
  if (!response.ok) return <p role="status">Trace observation unavailable.</p>;
  const data: unknown = await response.json();
  if (!isOperatorTrace(data))
    return <p role="status">Trace observation unavailable.</p>;
  return <TraceView trace={data} />;
}
