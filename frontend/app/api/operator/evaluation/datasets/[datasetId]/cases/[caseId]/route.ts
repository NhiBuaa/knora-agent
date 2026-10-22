import { proxyEvaluationPath } from "../../../../../_evaluation-proxy";

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ datasetId: string; caseId: string }> },
) {
  const { datasetId, caseId } = await params;
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/datasets/${encodeURIComponent(datasetId)}/cases/${encodeURIComponent(caseId)}`,
    ["evaluations:write"],
    "json",
  );
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ datasetId: string; caseId: string }> },
) {
  const { datasetId, caseId } = await params;
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/datasets/${encodeURIComponent(datasetId)}/cases/${encodeURIComponent(caseId)}`,
    ["evaluations:write"],
  );
}
