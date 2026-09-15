"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import type { DocumentResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";

export function DocumentList({ workspaceId }: { workspaceId: string }) {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]); const [showArchived, setShowArchived] = useState(false); const [error, setError] = useState<string | null>(null);
  async function load() { const response = await browserRequest(`/v1/workspaces/${encodeURIComponent(workspaceId)}/documents`); if (!response.ok) { setError(`Unable to load documents (${response.status})`); return; } const body = await response.json() as { documents: DocumentResponse[] }; setDocuments(body.documents); }
  useEffect(() => { void load(); }, [workspaceId]);
  async function mutate(id: string, action: "archive" | "unarchive") { const response = await browserRequest(`/v1/workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(id)}/${action}`, { method: "POST" }); if (response.status === 409) { setError("This document changed. Reload and try again."); return; } if (!response.ok) { setError(`Unable to ${action} document (${response.status})`); return; } await load(); }
  return <section><div className="toolbar"><h1>Documents</h1><label><input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} /> Show archived</label></div>{error && <p role="alert">{error}</p>}{!documents.length && !error && <p>No documents yet.</p>}<ul>{documents.filter((document) => showArchived || !document.archived).map((document) => <li key={document.document_id}><Link href={`/app/documents/${document.document_id}`}>{document.source_name}</Link><span> · {document.archived ? "archived" : "active"} · serving: {document.serving_state}</span>{document.ingestion_status && <span> · ingestion: {document.ingestion_status}</span>}<button onClick={() => void mutate(document.document_id, document.archived ? "unarchive" : "archive")}>{document.archived ? "Unarchive" : "Archive"}</button></li>)}</ul></section>;
}
