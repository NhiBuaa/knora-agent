import React from "react";
import { DatasetWorkbench } from "@/components/operator/datasets/DatasetWorkbench";

export default async function DatasetsPage({
  searchParams,
}: {
  searchParams?: Promise<{ workspaceId?: string; datasetId?: string }>;
}) {
  const { workspaceId, datasetId } = (await searchParams) ?? {};
  return (
    <DatasetWorkbench workspaceId={workspaceId} initialDatasetId={datasetId} />
  );
}
