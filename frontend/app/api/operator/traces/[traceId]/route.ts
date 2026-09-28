import { proxyOperatorPath } from "../../_proxy";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ traceId: string }> },
) {
  const { traceId } = await params;
  const response = await proxyOperatorPath(
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/operator/traces/${encodeURIComponent(traceId)}`,
    new URL(request.url).searchParams.get("workspaceId"),
  );
  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
}
