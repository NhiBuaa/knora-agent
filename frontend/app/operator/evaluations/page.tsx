import { redirect } from "next/navigation";
import React from "react";
import { OperatorLookup } from "@/components/operator/OperatorFrame";
import { OperatorLookupGuidance } from "@/components/operator/OperatorLookupGuidance";

export default async function EvaluationsPage({
  searchParams,
}: {
  searchParams?: Promise<{ reportId?: string; workspaceId?: string }>;
}) {
  const { reportId, workspaceId } = (await searchParams) ?? {};
  if (reportId?.trim())
    redirect(
      `/operator/evaluations/${encodeURIComponent(reportId.trim())}${workspaceId ? `?workspaceId=${encodeURIComponent(workspaceId)}` : ""}`,
    );
  return (
    <>
      <OperatorLookup kind="report" workspaceId={workspaceId} />
      <OperatorLookupGuidance kind="report" />
    </>
  );
}
