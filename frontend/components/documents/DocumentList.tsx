"use client";

import React, { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { DocumentResponse, IngestionResponse, PdfSubmissionResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";

function errorMessage(action: string, status: number) { return `Unable to ${action} (${status})`; }

export function DocumentList({ workspaceId, capabilities = [] }: { workspaceId: string; capabilities?: string[] }) {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<(PdfSubmissionResponse | IngestionResponse) | null>(null);
  const uploadKey = useRef<string | null>(null);
  const canWrite = capabilities.includes("documents:write");
  const load = useCallback(async () => {
    const response = await browserRequest(`/v1/workspaces/${encodeURIComponent(workspaceId)}/documents`);
    if (!response.ok) { setError(errorMessage("load documents", response.status)); return; }
    const body = await response.json() as { documents: DocumentResponse[] };
    setDocuments(body.documents);
  }, [workspaceId]);
  useEffect(() => { void load(); }, [load]);
  async function mutate(document: DocumentResponse, action: "archive" | "unarchive") {
    setError(null);
    const response = await browserRequest(`/v1/workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(document.document_id)}/${action}`, { method: "POST", headers: { "If-Match": String(document.revision) } });
    if (response.status === 409) { await load(); setError("This document changed. Reload and try again."); return; }
    if (!response.ok) { setError(errorMessage(`${action} document`, response.status)); return; }
    await load();
  }
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!file) return; setError(null);
    const body = new FormData(); body.set("source_key", file.name); body.set("file", file);
    if (!uploadKey.current) uploadKey.current = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
    const response = await browserRequest(`/v1/workspaces/${encodeURIComponent(workspaceId)}/documents`, { method: "POST", headers: { "Idempotency-Key": uploadKey.current }, body });
    if (!response.ok) { setError(errorMessage("upload document", response.status)); return; }
    setUploadState(await response.json() as PdfSubmissionResponse | IngestionResponse); uploadKey.current = null; await load();
  }
  const visibleDocuments = documents.filter((document) => showArchived || !document.archived);
  return <section>
    <div className="toolbar"><h1>Documents</h1><label><input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} /> Show archived</label></div>
    {canWrite && <form onSubmit={(event) => void upload(event)}><label htmlFor="document-file">Document file</label><input id="document-file" type="file" accept=".pdf,.md,.markdown,.txt,.text" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><button type="submit" disabled={!file}>Upload document</button></form>}
    {uploadState && <p role="status">Upload: {"status" in uploadState ? uploadState.status : uploadState.outcome}{"ingestion_job_id" in uploadState ? ` · job ${uploadState.ingestion_job_id}` : ""}</p>}
    {error && <p role="alert">{error}</p>}{!visibleDocuments.length && !error && <p>No documents yet.</p>}
    <ul>{visibleDocuments.map((document) => <li key={document.document_id}><Link href={`/app/documents/${document.document_id}`}>{document.source_name}</Link><span> · {document.archived ? "archived" : "active"} · serving: {document.serving_state}</span>{document.ingestion_status && <span> · ingestion: {document.ingestion_status}</span>}{canWrite && <button onClick={() => void mutate(document, document.archived ? "unarchive" : "archive")}>{document.archived ? "Unarchive" : "Archive"}</button>}</li>)}</ul>
  </section>;
}
