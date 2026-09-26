import React from "react";
import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { readEntryWorkspace } from "@/lib/auth/workspace";
import {
  decodePreference,
  WORKSPACE_PREFERENCE_COOKIE,
} from "@/lib/auth/workspace-preference";
import { routes } from "@/lib/navigation/routes";

export default async function HomePage({
  searchParams,
}: {
  searchParams?: Promise<{ "signed-out"?: string }>;
}) {
  const session = await getSession();
  if ((await searchParams)?.["signed-out"] === "1" && !session) {
    return (
      <main>
        <h1>Signed out</h1>
        <p>Your Knora session has ended.</p>
        <Link href="/api/auth/login">Sign in</Link>
      </main>
    );
  }
  if (!session) redirect("/api/auth/login");
  if (!session.issuer) redirect("/workspaces");
  let destination: string;
  try {
    const hint = await decodePreference(
      (await cookies()).get(WORKSPACE_PREFERENCE_COOKIE)?.value,
      { issuer: session.issuer, subject: session.subject },
    );
    const selectedId = await readEntryWorkspace(
      {
        issuer: session.issuer,
        subject: session.subject,
        accessToken: session.accessToken,
      },
      hint,
    );
    destination = selectedId ? routes.workspace(selectedId) : "/workspaces";
  } catch {
    return (
      <main role="alert">Unable to select a Workspace. Retry this page.</main>
    );
  }
  redirect(destination);
}
