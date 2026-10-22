import React from "react";
import { RunArtifact } from "@/components/operator/runs/RunArtifact";

export default async function CasePage({
  params,
  searchParams,
}: {
  params: Promise<{ runId: string; caseId: string }>;
  searchParams?: Promise<{ workspaceId?: string }>;
}) {
  const [{ runId, caseId }, { workspaceId }] = await Promise.all([
    params,
    searchParams ?? Promise.resolve({} as { workspaceId?: string }),
  ]);
  return (
    <RunArtifact runId={runId} caseId={caseId} workspaceId={workspaceId} />
  );
}
