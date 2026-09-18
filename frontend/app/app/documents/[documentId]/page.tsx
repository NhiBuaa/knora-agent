import { DocumentDetail } from "@/components/documents/DocumentDetail";
import { getSession } from "@/lib/auth/session";
export default async function DocumentPage({ params }: { params: Promise<{ documentId: string }> }) { const session = await getSession(); const workspaceId = session?.workspaceIds[0]; if (!workspaceId) return <p role="alert">No workspace is available for this session.</p>; const { documentId } = await params; return <DocumentDetail workspaceId={workspaceId} documentId={documentId} capabilities={session?.capabilities ?? []} />; }
