import React from "react";
import { RunsView } from "@/components/operator/runs/RunsView";
import { getSession } from "@/lib/auth/session";

export default async function RunsPage({
  searchParams,
}: {
  searchParams?: Promise<{ workspaceId?: string }>;
}) {
  const { workspaceId } = (await searchParams) ?? {};
  const session = await getSession();
  return (
    <RunsView
      workspaceId={workspaceId}
      capabilities={session?.capabilities ?? []}
    />
  );
}
