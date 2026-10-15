import React from "react";
import { RunsView } from "@/components/operator/runs/RunsView";
import { getSession } from "@/lib/auth/session";

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
  const session = await getSession();
  return (
    <RunsView
      workspaceId={workspaceId}
      runId={runId}
      capabilities={session?.capabilities ?? []}
    />
  );
}
