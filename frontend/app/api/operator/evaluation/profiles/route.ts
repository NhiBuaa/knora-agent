import { proxyEvaluationPath } from "../../_evaluation-proxy";

export function GET(request: Request) {
  return proxyEvaluationPath(
    request,
    (workspaceId) => `/v1/workspaces/${workspaceId}/evaluation/profiles`,
  );
}
