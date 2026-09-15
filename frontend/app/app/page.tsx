import Link from "next/link";
import { getSession } from "@/lib/auth/session";
import { ToolLifecycleDisplay } from "@/components/tools/ToolLifecycle";
export default async function WorkspacePage() {
  const session = await getSession();
  return <section><h1>Workspace</h1><p>Manage documents and ask questions in your selected workspace.</p><p>Selected workspace: {session?.workspaceIds[0] ?? "unavailable"}</p><Link href="/app/documents">Manage documents</Link> · <Link href="/app/questions">Ask a question</Link><ToolLifecycleDisplay lifecycle={{}} /></section>;
}
