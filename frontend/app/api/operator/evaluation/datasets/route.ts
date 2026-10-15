import { proxyEvaluationPath } from "../../_evaluation-proxy";

export async function POST(request: Request) {
  return proxyEvaluationPath(
    request,
    (workspaceId) => `/v1/workspaces/${workspaceId}/evaluation/datasets`,
    ["evaluations:write"],
    "json",
  );
}
