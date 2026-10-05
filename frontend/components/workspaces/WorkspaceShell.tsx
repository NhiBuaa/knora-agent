"use client";

import React from "react";
import { usePathname } from "next/navigation";
import type { WorkspaceResponse } from "@/generated/knora-openapi";
import { AppShell } from "@/components/shell/AppShell";
import { WorkspaceSelector } from "./WorkspaceSelector";

export function WorkspaceShell({
  selectedWorkspace,
  ...props
}: React.ComponentProps<typeof AppShell> & {
  selectedWorkspace?: WorkspaceResponse | null;
}) {
  const parts = (usePathname() ?? "").split("/").filter(Boolean);
  let workspaceId: string | null = null;
  if (parts[0] === "workspaces" && parts[1]) {
    try {
      const id = decodeURIComponent(parts[1]);
      if (!["new", "archived"].includes(id)) workspaceId = id;
    } catch {
      /* Malformed route is no hint. */
    }
  } else if (parts[0] === "operator")
    workspaceId = selectedWorkspace?.id ?? null;
  const selected =
    parts[0] === "operator"
      ? selectedWorkspace
      : props.workspaces.find((workspace) => workspace.id === workspaceId);
  return (
    <AppShell
      {...props}
      workspaceSelector={
        <WorkspaceSelector
          workspaceId={workspaceId}
          workspaceName={selected?.name ?? null}
        />
      }
    />
  );
}
