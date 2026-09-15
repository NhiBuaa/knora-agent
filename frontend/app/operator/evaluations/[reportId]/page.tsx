import { cookies } from "next/headers";
import { EvaluationView } from "../../../../components/operator/EvaluationView";
import type { KnoraApiPath } from "../../../../generated/knora-openapi";
import { isOperatorEvaluation, readOperatorResource, sessionFromCookies } from "../../../../lib/operator/api";

export default async function EvaluationDetailPage({ params }: { params: { reportId: string } }) {
  const cookieStore = await cookies();
  const session = sessionFromCookies({ accessToken: cookieStore.get("knora_access_token")?.value, workspaceId: cookieStore.get("knora_workspace_id")?.value });
  if (!session) return <p role="alert">Sign in to inspect this evaluation.</p>;
  const path = `/v1/workspaces/${encodeURIComponent(session.workspaceId)}/operator/evaluations/${encodeURIComponent(params.reportId)}` as KnoraApiPath;
  const result = await readOperatorResource(path, session);
  if (result.response.status === 401 || result.response.status === 403) return <p role="alert">You are not authorized to inspect this evaluation.</p>;
  if (!result.data || !isOperatorEvaluation(result.data)) return <p role="status">Evaluation observation unavailable.</p>;
  return <EvaluationView evaluation={result.data} />;
}
