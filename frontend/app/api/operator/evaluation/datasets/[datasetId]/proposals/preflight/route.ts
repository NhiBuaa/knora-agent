import { proxyEvaluationPath } from "../../../../../_evaluation-proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ datasetId: string }> },
) {
  const { datasetId } = await params;
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/datasets/${encodeURIComponent(datasetId)}/proposals/preflight`,
    ["evaluations:write", "documents:read"],
    "json",
  );
}
