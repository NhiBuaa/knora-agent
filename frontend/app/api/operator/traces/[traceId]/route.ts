import { proxyOperatorPath } from "../../_proxy";

export async function GET(_: Request, { params }: { params: { traceId: string } }) {
  const response = await proxyOperatorPath((workspaceId) => `/v1/workspaces/${workspaceId}/operator/traces/${encodeURIComponent(params.traceId)}`);
  return new Response(response.body, { status: response.status, headers: response.headers });
}
