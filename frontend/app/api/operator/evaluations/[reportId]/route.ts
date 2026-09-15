import { proxyOperatorPath } from "../../_proxy";

export async function GET(_: Request, { params }: { params: { reportId: string } }) {
  const response = await proxyOperatorPath((workspaceId) => `/v1/workspaces/${workspaceId}/operator/evaluations/${encodeURIComponent(params.reportId)}`);
  return new Response(response.body, { status: response.status, headers: response.headers });
}
