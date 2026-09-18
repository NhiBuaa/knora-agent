import Link from "next/link";
import { cookies } from "next/headers";
import { sessionFromCookies } from "../../lib/operator/api";

export default async function OperatorLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const session = sessionFromCookies({
    accessToken: cookieStore.get("knora_access_token")?.value,
    workspaceId: cookieStore.get("knora_workspace_id")?.value,
  });
  if (!session) {
    return <main><h1>Operator access</h1><p role="alert">Sign in to inspect operator observations.</p></main>;
  }
  return <main><nav aria-label="Operator navigation"><Link href="/operator">Overview</Link> <Link href="/operator/traces">Traces</Link> <Link href="/operator/evaluations">Evaluations</Link> <Link href="/operator/operations">Operations</Link></nav>{children}</main>;
}
