import { DocumentList } from "@/components/documents/DocumentList";
import { getSession } from "@/lib/auth/session";
export default async function DocumentsPage() {
  const session = await getSession();
  const workspaceId = session?.workspaceIds[0];
  if (!workspaceId)
    return <p role="alert">No workspace is available for this session.</p>;
  return (
    <DocumentList
      workspaceId={workspaceId}
      capabilities={session?.capabilities ?? []}
    />
  );
}
