import React from "react";
import { OperationsContent } from "./content";

export default async function OperationsPage({
  searchParams,
}: {
  searchParams?: Promise<{ workspaceId?: string }>;
}) {
  const { workspaceId } = (await searchParams) ?? {};
  return <OperationsContent workspaceId={workspaceId} />;
}
