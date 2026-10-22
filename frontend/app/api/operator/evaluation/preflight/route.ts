import { proxyEvaluationPath } from "../../_evaluation-proxy";

export function POST(request: Request) {
  return proxyEvaluationPath(
    request,
    (workspaceId) => `/v1/workspaces/${workspaceId}/evaluation/preflight`,
    ["evaluations:run", "questions:ask"],
    "json",
  );
}
