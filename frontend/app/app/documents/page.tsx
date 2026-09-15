import { DocumentList } from "@/components/documents/DocumentList";
export default function DocumentsPage() { return <DocumentList workspaceId={process.env.NEXT_PUBLIC_DEFAULT_WORKSPACE_ID ?? "default"} />; }
