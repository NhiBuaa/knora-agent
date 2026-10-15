import React from "react";
import { RunsView } from "@/components/operator/runs/RunsView";

export default async function RunPage({
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
  return <RunsView workspaceId={workspaceId} runId={runId} />;
}
