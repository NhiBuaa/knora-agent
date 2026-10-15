import { proxyEvaluationPath } from "../../_evaluation-proxy";

export async function GET(request: Request) {
  return proxyEvaluationPath(
    request,
    (workspaceId) => `/v1/workspaces/${workspaceId}/evaluation/datasets`,
    ["operator:read"],
  );
}

export async function POST(request: Request) {
  return proxyEvaluationPath(
    request,
    (workspaceId) => `/v1/workspaces/${workspaceId}/evaluation/datasets`,
    ["evaluations:write"],
    "json",
  );
}
