import React from "react";
import { OperatorLookup } from "@/components/operator/OperatorFrame";
import { EvaluationView } from "../../../../components/operator/EvaluationView";
import { isOperatorEvaluation } from "../../../../lib/operator/api";
import { readOperatorBff } from "../../../../lib/operator/bff";

export default async function EvaluationDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ reportId: string }>;
  searchParams?: Promise<{ workspaceId?: string }>;
}) {
  const { reportId } = await params;
  const { workspaceId } = (await searchParams) ?? {};
  const view = (content: React.ReactNode) => (
    <>
      <OperatorLookup
        key={`${reportId}:${workspaceId ?? ""}`}
        kind="report"
        identifier={reportId}
        workspaceId={workspaceId}
      />
      {content}
    </>
  );
  let response: Response;
  try {
    response = await readOperatorBff(
      `/api/operator/evaluations/${encodeURIComponent(reportId)}${workspaceId ? `?workspaceId=${encodeURIComponent(workspaceId)}` : ""}`,
    );
  } catch {
    return view(<p role="status">Evaluation observation unavailable.</p>);
  }
  if (response.status === 401)
    return view(<p role="alert">Sign in to inspect this evaluation.</p>);
  if (response.status === 403)
    return view(
      <p role="alert">You are not authorized to inspect this evaluation.</p>,
    );
  if (response.status === 409)
    return view(
      <p role="status">Select a workspace to inspect this evaluation.</p>,
    );
  if (!response.ok)
    return view(<p role="status">Evaluation observation unavailable.</p>);
  const data: unknown = await response.json().catch(() => null);
  if (!isOperatorEvaluation(data))
    return view(<p role="status">Evaluation observation unavailable.</p>);
  return view(<EvaluationView evaluation={data} />);
}
