import { proxyOperatorPath } from "../../_proxy";

export async function GET(_: Request, { params }: { params: Promise<{ traceId: string }> }) {
  const { traceId } = await params;
  const response = await proxyOperatorPath((workspaceId) => `/v1/workspaces/${workspaceId}/operator/traces/${encodeURIComponent(traceId)}`);
  return new Response(response.body, { status: response.status, headers: response.headers });
}
