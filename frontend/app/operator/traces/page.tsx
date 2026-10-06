import { redirect } from "next/navigation";
import React from "react";
import { OperatorLookup } from "@/components/operator/OperatorFrame";

export default async function TracesPage({
  searchParams,
}: {
  searchParams?: Promise<{ traceId?: string; workspaceId?: string }>;
}) {
  const { traceId, workspaceId } = (await searchParams) ?? {};
  if (traceId?.trim())
    redirect(
      `/operator/traces/${encodeURIComponent(traceId.trim())}${workspaceId ? `?workspaceId=${encodeURIComponent(workspaceId)}` : ""}`,
    );
  return <OperatorLookup kind="trace" workspaceId={workspaceId} />;
}
