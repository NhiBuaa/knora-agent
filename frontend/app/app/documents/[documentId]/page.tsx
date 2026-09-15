import { DocumentDetail } from "@/components/documents/DocumentDetail";
export default async function DocumentPage({ params }: { params: { documentId: string } }) { return <DocumentDetail workspaceId={process.env.NEXT_PUBLIC_DEFAULT_WORKSPACE_ID ?? "default"} documentId={params.documentId} />; }
