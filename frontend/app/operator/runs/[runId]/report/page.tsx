import React from "react";
import { RunArtifact } from "@/components/operator/runs/RunArtifact";

export default async function ReportPage({
  params,
  searchParams,
}: {
  params: Promise<{ runId: string }>;
  searchParams?: Promise<{ workspaceId?: string }>;
}) {
  const [{ runId }, { workspaceId }] = await Promise.all([
    params,
    searchParams ?? Promise.resolve({} as { workspaceId?: string }),
  ]);
  return <RunArtifact runId={runId} workspaceId={workspaceId} />;
}
