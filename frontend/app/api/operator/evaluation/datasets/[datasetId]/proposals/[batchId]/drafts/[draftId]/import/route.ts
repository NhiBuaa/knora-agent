import { proxyEvaluationPath } from "../../../../../../../../_evaluation-proxy";

export async function POST(
  request: Request,
  {
    params,
  }: {
    params: Promise<{ datasetId: string; batchId: string; draftId: string }>;
  },
) {
  const { datasetId, batchId, draftId } = await params;
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/datasets/${encodeURIComponent(datasetId)}/proposals/${encodeURIComponent(batchId)}/drafts/${encodeURIComponent(draftId)}/import`,
    ["evaluations:write", "documents:read"],
    "json",
  );
}
