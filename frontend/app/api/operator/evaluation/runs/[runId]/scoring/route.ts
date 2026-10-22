import { proxyEvaluationPath } from "../../../../_evaluation-proxy";

type Context = { params: Promise<{ runId: string }> };

export async function GET(request: Request, { params }: Context) {
  const { runId } = await params;
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/runs/${encodeURIComponent(runId)}/scoring`,
  );
}

export async function POST(request: Request, { params }: Context) {
  const { runId } = await params;
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/runs/${encodeURIComponent(runId)}/scoring`,
    ["evaluations:run"],
    "json",
  );
}
