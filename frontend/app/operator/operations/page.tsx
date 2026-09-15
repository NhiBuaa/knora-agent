import { cookies } from "next/headers";
import { OperationsView } from "../../../components/operator/OperationsView";
import { isOperatorOperations, readOperatorResource, sessionFromCookies } from "../../../lib/operator/api";
import type { KnoraApiPath } from "../../../generated/knora-openapi";

export default function OperationsPage() {
  return <OperationsContent />;
}

async function OperationsContent() {
  const cookieStore = await cookies();
  const session = sessionFromCookies({ accessToken: cookieStore.get("knora_access_token")?.value, workspaceId: cookieStore.get("knora_workspace_id")?.value });
  if (!session) return <p role="alert">Sign in to inspect operational observations.</p>;
  const path = `/v1/workspaces/${encodeURIComponent(session.workspaceId)}/operator/operations` as KnoraApiPath;
  const result = await readOperatorResource(path, session);
  if (result.response.status === 401 || result.response.status === 403) return <p role="alert">You are not authorized to inspect operations.</p>;
  if (!result.data || !isOperatorOperations(result.data)) return <p role="status">Operational observation unavailable.</p>;
  return <><h1>Operations</h1><OperationsView operations={result.data} /></>;
}
