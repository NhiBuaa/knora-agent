import { DocumentDetail } from "@/components/documents/DocumentDetail";
import { getSession } from "@/lib/auth/session";
export default async function DocumentPage({ params }: { params: { documentId: string } }) { const session = await getSession(); const workspaceId = session?.workspaceIds[0]; if (!workspaceId) return <p role="alert">No workspace is available for this session.</p>; return <DocumentDetail workspaceId={workspaceId} documentId={params.documentId} canRequestDeletion={session?.capabilities.includes("operator:read") ?? false} />; }
