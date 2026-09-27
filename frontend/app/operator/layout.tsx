import React from "react";
import Link from "next/link";
import { cookies } from "next/headers";
import { ThemeControl } from "@/components/ui/ThemeControl";
import { readThemePreference, THEME_COOKIE_NAME } from "@/lib/theme";
import { getSession } from "../../lib/auth/session";
import { readEntryWorkspace } from "../../lib/auth/workspace";

export default async function OperatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session) {
    return (
      <main>
        <h1>Operator access</h1>
        <p role="alert">Sign in to inspect operator observations.</p>
      </main>
    );
  }
  let workspaceId: string | null = null;
  if (session.issuer) {
    try {
      workspaceId = await readEntryWorkspace(
        {
          issuer: session.issuer,
          subject: session.subject,
          accessToken: session.accessToken,
        },
        null,
      );
    } catch {
      return (
        <main role="status">
          Operator Workspace unavailable. Retry this page.
        </main>
      );
    }
  }
  if (!workspaceId) {
    return (
      <main>
        <h1>Operator access</h1>
        <p role="alert">
          This session is not authorized for an operator workspace.
        </p>
      </main>
    );
  }
  return (
    <main>
      <nav aria-label="Operator navigation">
        <Link href="/operator">Overview</Link>{" "}
        <Link href="/operator/traces">Traces</Link>{" "}
        <Link href="/operator/evaluations">Evaluations</Link>{" "}
        <Link href="/operator/operations">Operations</Link>
      </nav>
      <ThemeControl
        initialPreference={readThemePreference(
          (await cookies()).get(THEME_COOKIE_NAME)?.value,
        )}
      />
      {children}
    </main>
  );
}
