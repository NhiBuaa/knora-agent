import { proxyEvaluationPath } from "../../../_evaluation-proxy";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId } = await params;
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/runs/${encodeURIComponent(runId)}`,
  );
}
