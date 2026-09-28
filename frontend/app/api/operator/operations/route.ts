import { proxyOperatorPath } from "../_proxy";

export async function GET(request: Request) {
  const response = await proxyOperatorPath(
    (workspaceId) => `/v1/workspaces/${workspaceId}/operator/operations`,
    new URL(request.url).searchParams.get("workspaceId"),
  );
  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
}
