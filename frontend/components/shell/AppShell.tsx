import React from "react";
import type { WorkspaceResponse } from "@/generated/knora-openapi";
import { AccountMenu } from "@/components/shell/AccountMenu";
import { MobileDrawer } from "@/components/shell/MobileDrawer";
import { WorkspaceSidebar } from "@/components/shell/WorkspaceSidebar";
import type { ThemePreference } from "@/lib/theme";

export function AppShell({
  workspaces,
  nextCursor,
  capabilities,
  subject,
  themePreference,
  children,
}: {
  workspaces: WorkspaceResponse[];
  nextCursor: string | null;
  capabilities: string[];
  subject: string;
  themePreference: ThemePreference;
  children: React.ReactNode;
}) {
  const navigation = (
    <WorkspaceSidebar
      workspaces={workspaces}
      capabilities={capabilities}
      nextCursor={nextCursor}
    />
  );
  return (
    <div className="workspace-shell">
      <div className="workspace-shell-desktop">
        {navigation}
        <AccountMenu subject={subject} themePreference={themePreference} />
      </div>
      <MobileDrawer>
        <WorkspaceSidebar
          workspaces={workspaces}
          capabilities={capabilities}
          nextCursor={nextCursor}
        />
        <AccountMenu subject={subject} themePreference={themePreference} />
      </MobileDrawer>
      <main className="workspace-shell-main">{children}</main>
    </div>
  );
}
