import { proxyEvaluationPath } from "../../../../_evaluation-proxy";

type Context = { params: Promise<{ datasetId: string }> };

export async function GET(request: Request, { params }: Context) {
  const { datasetId } = await params;
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/datasets/${encodeURIComponent(datasetId)}/proposals`,
    ["documents:read"],
  );
}

export async function POST(request: Request, { params }: Context) {
  const { datasetId } = await params;
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/datasets/${encodeURIComponent(datasetId)}/proposals`,
    ["evaluations:write", "documents:read"],
    "json",
  );
}
