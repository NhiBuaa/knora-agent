import React from "react";
import { redirect } from "next/navigation";
import type {
  WorkspaceListResponse,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { WorkspaceShell } from "@/components/workspaces/WorkspaceShell";
import { knoraRequest } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";
import { cookies } from "next/headers";
import { readThemePreference, THEME_COOKIE_NAME } from "@/lib/theme";
import "./shell.css";

export default async function WorkspacesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session) redirect("/api/auth/login");
  let firstPage: WorkspaceListResponse;
  try {
    firstPage = (await knoraRequest(
      "/v1/workspaces?archived=false&limit=20" as "/v1/workspaces",
      {
        accessToken: session.accessToken,
      },
    )) as WorkspaceListResponse;
  } catch {
    return (
      <main role="alert">Unable to load Workspaces. Retry this page.</main>
    );
  }
  return (
    <WorkspaceShell
      workspaces={firstPage.items as WorkspaceResponse[]}
      nextCursor={firstPage.next_cursor}
      capabilities={session.capabilities}
      subject={session.subject}
      themePreference={readThemePreference(
        (await cookies()).get(THEME_COOKIE_NAME)?.value,
      )}
    >
      {children}
    </WorkspaceShell>
  );
}
