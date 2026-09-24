import Link from "next/link";
import { getSession } from "@/lib/auth/session";
import { ToolLifecycleDisplay } from "@/components/tools/ToolLifecycle";

export const dynamic = "force-dynamic";

export default async function WorkspacePage() {
  const session = await getSession();
  const workspaceId = session?.workspaceIds[0];
  return <section><h1>Workspace</h1><p>Manage documents and ask questions in your selected workspace.</p><p>Selected workspace: {workspaceId ?? "unavailable"}</p><Link href="/app/documents">Manage documents</Link> · <Link href="/app/questions">Ask a question</Link>{workspaceId ? <ToolLifecycleDisplay workspaceId={workspaceId} /> : <p role="alert">No workspace is available for this session.</p>}</section>;
}
