import { proxyOperatorPath } from "../../_proxy";

export async function GET(_: Request, { params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  const response = await proxyOperatorPath((workspaceId) => `/v1/workspaces/${workspaceId}/operator/evaluations/${encodeURIComponent(reportId)}`);
  return new Response(response.body, { status: response.status, headers: response.headers });
}
