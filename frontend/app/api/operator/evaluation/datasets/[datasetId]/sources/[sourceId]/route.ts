import { proxyEvaluationPath } from "../../../../../_evaluation-proxy";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ datasetId: string; sourceId: string }> },
) {
  const { datasetId, sourceId } = await params;
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/datasets/${encodeURIComponent(datasetId)}/sources/${encodeURIComponent(sourceId)}`,
  );
}
