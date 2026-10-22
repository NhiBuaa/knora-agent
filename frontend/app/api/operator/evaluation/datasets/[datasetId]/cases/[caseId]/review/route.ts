import { proxyEvaluationPath } from "../../../../../../_evaluation-proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ datasetId: string; caseId: string }> },
) {
  const { datasetId, caseId } = await params;
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/datasets/${encodeURIComponent(datasetId)}/cases/${encodeURIComponent(caseId)}/review`,
    ["evaluations:approve", "documents:read"],
    "json",
  );
}
