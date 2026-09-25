import { proxyOperatorPath } from "../_proxy";

export async function GET() {
  const response = await proxyOperatorPath(
    (workspaceId) => `/v1/workspaces/${workspaceId}/operator/operations`,
  );
  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
}
