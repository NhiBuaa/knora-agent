import React from "react";
import { cookies } from "next/headers";
import type {
  WorkspaceListResponse,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import { AppShell } from "@/components/shell/AppShell";
import { KnoraApiError, knoraRequest } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";
import {
  decodePreference,
  WORKSPACE_PREFERENCE_COOKIE,
} from "@/lib/auth/workspace-preference";
import { readThemePreference, THEME_COOKIE_NAME } from "@/lib/theme";
import "../workspaces/shell.css";

export default async function OperatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session?.issuer)
    return <main role="alert">Sign in to inspect operator observations.</main>;
  if (!session.capabilities.includes("operator:read"))
    return <main role="alert">Operator access denied.</main>;

  const cookieStore = await cookies();
  let page: WorkspaceListResponse;
  let selected: WorkspaceResponse | null = null;
  try {
    page = (await knoraRequest(
      "/v1/workspaces?archived=false&limit=20" as "/v1/workspaces",
      { accessToken: session.accessToken },
    )) as WorkspaceListResponse;
    const hint = await decodePreference(
      cookieStore.get(WORKSPACE_PREFERENCE_COOKIE)?.value,
      { issuer: session.issuer, subject: session.subject },
    );
    if (hint) {
      try {
        selected = (await knoraRequest(
          `/v1/workspaces/${encodeURIComponent(hint)}` as "/v1/workspaces/{workspace_id}",
          { accessToken: session.accessToken },
        )) as WorkspaceResponse;
        if (selected.id !== hint) selected = null;
      } catch (error) {
        if (
          !(error instanceof KnoraApiError) ||
          ![403, 404].includes(error.status)
        )
          throw error;
      }
    }
  } catch {
    return (
      <main role="status">
        Operator Workspace unavailable. Retry this page.
      </main>
    );
  }
  return (
    <AppShell
      workspaces={page.items}
      nextCursor={page.next_cursor}
      capabilities={session.capabilities}
      subject={session.subject}
      themePreference={readThemePreference(
        cookieStore.get(THEME_COOKIE_NAME)?.value,
      )}
    >
      {selected ? (
        <p>
          Navigation preference: <strong>{selected.name}</strong>
          {selected.archived ? " (archived)" : ""}
        </p>
      ) : null}
      {children}
    </AppShell>
  );
}
