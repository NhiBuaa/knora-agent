import React from "react";
import { DatasetWorkbench } from "@/components/operator/datasets/DatasetWorkbench";
import { getSession } from "@/lib/auth/session";

export default async function DatasetsPage({
  searchParams,
}: {
  searchParams?: Promise<{ workspaceId?: string; datasetId?: string }>;
}) {
  const { workspaceId, datasetId } = (await searchParams) ?? {};
  const session = await getSession();
  return (
    <DatasetWorkbench
      workspaceId={workspaceId}
      initialDatasetId={datasetId}
      capabilities={session?.capabilities ?? []}
    />
  );
}
