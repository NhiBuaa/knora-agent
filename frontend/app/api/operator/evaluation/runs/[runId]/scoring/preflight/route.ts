import { proxyEvaluationPath } from "../../../../../_evaluation-proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId } = await params;
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/runs/${encodeURIComponent(runId)}/scoring/preflight`,
    ["evaluations:run"],
    "json",
  );
}
