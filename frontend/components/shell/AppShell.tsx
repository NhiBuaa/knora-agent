"use client";

import React from "react";
import { usePathname } from "next/navigation";
import type { WorkspaceResponse } from "@/generated/knora-openapi";
import { AccountMenu } from "@/components/shell/AccountMenu";
import { MobileDrawer } from "@/components/shell/MobileDrawer";
import { WorkspaceSidebar } from "@/components/shell/WorkspaceSidebar";
import type { ThemePreference } from "@/lib/theme";
import { ProductHeader } from "./ProductHeader";

export function AppShell({
  workspaces,
  nextCursor,
  capabilities,
  subject,
  themePreference,
  children,
  workspaceSelector,
}: {
  workspaces: WorkspaceResponse[];
  nextCursor: string | null;
  capabilities: string[];
  subject: string;
  themePreference: ThemePreference;
  children: React.ReactNode;
  workspaceSelector?: React.ReactNode;
}) {
  const pathname = usePathname() ?? "";
  const parts = pathname.split("/").filter(Boolean);
  let workspaceId: string | null = null;
  if (parts[0] === "workspaces" && parts[1]) {
    try {
      const segment = decodeURIComponent(parts[1]);
      if (!["new", "archived"].includes(segment)) workspaceId = segment;
    } catch {
      /* A malformed route never becomes a workspace hint. */
    }
  }
  const activeSection =
    parts[0] === "operator"
      ? "operator"
      : parts[2] === "documents"
        ? "documents"
        : "conversations";
  const conversationSurface = Boolean(
    workspaceId && parts[2] === "conversations",
  );
  const navigation = (
    <WorkspaceSidebar
      workspaceSelector={workspaceSelector}
      workspaces={workspaces}
      capabilities={capabilities}
      nextCursor={nextCursor}
    />
  );
  return (
    <div
      className="workspace-shell"
      data-section={activeSection}
      data-rail={false}
      data-conversation-surface={conversationSurface}
    >
      <ProductHeader
        activeSection={activeSection}
        workspaceId={workspaceId}
        canOpenOperator={capabilities.includes("operator:read")}
        account={
          <>
            <MobileDrawer>{navigation}</MobileDrawer>
            <AccountMenu subject={subject} themePreference={themePreference} />
          </>
        }
      />
      <div className="workspace-shell-body">
        <main className="workspace-shell-main">{children}</main>
      </div>
    </div>
  );
}
