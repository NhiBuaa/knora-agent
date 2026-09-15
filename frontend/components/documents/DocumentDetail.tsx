"use client";
import { useEffect, useState } from "react";
import type { DocumentDeletionRequestResponse, DocumentResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";

export function DocumentDetail({ workspaceId, documentId }: { workspaceId: string; documentId: string }) {
  const [document, setDocument] = useState<DocumentResponse | null>(null); const [deletion, setDeletion] = useState<DocumentDeletionRequestResponse | null>(null); const [error, setError] = useState<string | null>(null);
  useEffect(() => { void (async () => { const response = await browserRequest(`/v1/workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(documentId)}`); if (!response.ok) { setError(`Unable to load document (${response.status})`); return; } setDocument(await response.json()); })(); }, [workspaceId, documentId]);
  async function requestDeletion() { const response = await browserRequest(`/v1/workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(documentId)}/deletion-request`, { method: "POST" }); if (response.status === 403) { setError("Deletion requests require operator access."); return; } if (!response.ok) { setError(`Unable to request deletion (${response.status})`); return; } setDeletion(await response.json()); }
  if (error) return <p role="alert">{error}</p>; if (!document) return <p>Loading document…</p>;
  return <article><h1>{document.source_name}</h1><dl><dt>Source key</dt><dd>{document.source_key}</dd><dt>State</dt><dd>{document.archived ? "archived" : "active"}</dd><dt>Serving</dt><dd>{document.serving_state}</dd><dt>Revision</dt><dd>{document.revision}</dd><dt>Ingestion</dt><dd>{document.ingestion_status ?? "not running"}</dd></dl>{document.ingestion_job_id && <p>Ingestion job: {document.ingestion_job_id}</p>}<button onClick={() => void requestDeletion()}>Request deletion</button>{deletion && <p role="status">Deletion request: {deletion.state}{deletion.failure_reason ? ` (${deletion.failure_reason})` : ""}</p>}</article>;
}
