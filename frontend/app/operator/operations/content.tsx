import React from "react";
import { OperationsView } from "../../../components/operator/OperationsView";
import { isOperatorOperations } from "../../../lib/operator/api";
import { readOperatorBff } from "../../../lib/operator/bff";

export async function OperationsContent() {
  let response: Response;
  try {
    response = await readOperatorBff("/api/operator/operations");
  } catch {
    return <p role="status">Operational observation unavailable.</p>;
  }
  if (response.status === 401)
    return <p role="alert">Sign in to inspect operational observations.</p>;
  if (response.status === 403)
    return <p role="alert">You are not authorized to inspect operations.</p>;
  if (!response.ok)
    return <p role="status">Operational observation unavailable.</p>;
  const data: unknown = await response.json();
  if (!isOperatorOperations(data))
    return <p role="status">Operational observation unavailable.</p>;
  return (
    <>
      <h1>Operations</h1>
      <OperationsView operations={data} />
    </>
  );
}
