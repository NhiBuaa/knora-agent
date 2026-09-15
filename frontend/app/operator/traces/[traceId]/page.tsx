import { cookies } from "next/headers";
import { TraceView } from "../../../../components/operator/TraceView";
import type { KnoraApiPath } from "../../../../generated/knora-openapi";
import { isOperatorTrace, readOperatorResource, sessionFromCookies } from "../../../../lib/operator/api";

export default async function TraceDetailPage({ params }: { params: { traceId: string } }) {
  const cookieStore = await cookies();
  const session = sessionFromCookies({ accessToken: cookieStore.get("knora_access_token")?.value, workspaceId: cookieStore.get("knora_workspace_id")?.value });
  if (!session) return <p role="alert">Sign in to inspect this trace.</p>;
  const path = `/v1/workspaces/${encodeURIComponent(session.workspaceId)}/operator/traces/${encodeURIComponent(params.traceId)}` as KnoraApiPath;
  const result = await readOperatorResource(path, session);
  if (result.response.status === 401 || result.response.status === 403) return <p role="alert">You are not authorized to inspect this trace.</p>;
  if (!result.data || !isOperatorTrace(result.data)) return <p role="status">Trace observation unavailable.</p>;
  return <TraceView trace={result.data} />;
}
