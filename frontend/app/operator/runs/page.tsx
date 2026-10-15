import React from "react";
import { RunsView } from "@/components/operator/runs/RunsView";

export default async function RunsPage({
  searchParams,
}: {
  searchParams?: Promise<{ workspaceId?: string }>;
}) {
  const { workspaceId } = (await searchParams) ?? {};
  return <RunsView workspaceId={workspaceId} />;
}
