import React from "react";
import { OperationsView } from "../../../components/operator/OperationsView";
import { isOperatorOperations } from "../../../lib/operator/api";
import { readOperatorBff } from "../../../lib/operator/bff";

export async function OperationsContent({
  workspaceId,
}: { workspaceId?: string } = {}) {
  let response: Response;
  try {
    response = await readOperatorBff(
      `/api/operator/operations${workspaceId ? `?workspaceId=${encodeURIComponent(workspaceId)}` : ""}`,
    );
  } catch {
    return <p role="status">Operational observation unavailable.</p>;
  }
  if (response.status === 401)
    return <p role="alert">Sign in to inspect operational observations.</p>;
  if (response.status === 403)
    return <p role="alert">You are not authorized to inspect operations.</p>;
  if (response.status === 409)
    return <p role="status">Select a workspace to inspect operations.</p>;
  if (!response.ok)
    return <p role="status">Operational observation unavailable.</p>;
  const data: unknown = await response.json().catch(() => null);
  if (!isOperatorOperations(data))
    return <p role="status">Operational observation unavailable.</p>;
  return (
    <>
      <OperationsView operations={data} />
      <details className="mt-4 text-xs text-text-muted">
        <summary>Observation scope</summary>
        <p>
          Observed Workspace: <code>{data.workspace_id}</code>
        </p>
      </details>
    </>
  );
}
