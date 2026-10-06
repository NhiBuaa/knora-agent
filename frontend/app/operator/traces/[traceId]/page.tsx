import React from "react";
import { OperatorLookup } from "@/components/operator/OperatorFrame";
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
  const view = (content: React.ReactNode) => (
    <>
      <OperatorLookup
        key={`${traceId}:${workspaceId ?? ""}`}
        kind="trace"
        identifier={traceId}
        workspaceId={workspaceId}
      />
      {content}
    </>
  );
  let response: Response;
  try {
    response = await readOperatorBff(
      `/api/operator/traces/${encodeURIComponent(traceId)}${workspaceId ? `?workspaceId=${encodeURIComponent(workspaceId)}` : ""}`,
    );
  } catch {
    return view(<p role="status">Trace observation unavailable.</p>);
  }
  if (response.status === 401)
    return view(<p role="alert">Sign in to inspect this trace.</p>);
  if (response.status === 403)
    return view(
      <p role="alert">You are not authorized to inspect this trace.</p>,
    );
  if (response.status === 409)
    return view(<p role="status">Select a workspace to inspect this trace.</p>);
  if (!response.ok)
    return view(<p role="status">Trace observation unavailable.</p>);
  const data: unknown = await response.json().catch(() => null);
  if (!isOperatorTrace(data))
    return view(<p role="status">Trace observation unavailable.</p>);
  return view(<TraceView trace={data} />);
}
