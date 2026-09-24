import Link from "next/link";
import { getSession } from "../../lib/auth/session";
import { selectWorkspace } from "../../lib/auth/workspace";

export default async function OperatorLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  if (!session) {
    return <main><h1>Operator access</h1><p role="alert">Sign in to inspect operator observations.</p></main>;
  }
  if (!selectWorkspace(session.workspaceIds)) {
    return <main><h1>Operator access</h1><p role="alert">This session is not authorized for an operator workspace.</p></main>;
  }
  return <main><nav aria-label="Operator navigation"><Link href="/operator">Overview</Link> <Link href="/operator/traces">Traces</Link> <Link href="/operator/evaluations">Evaluations</Link> <Link href="/operator/operations">Operations</Link></nav>{children}</main>;
}
