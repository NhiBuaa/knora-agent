"use client";

import React, { useEffect, useRef, useState } from "react";
import type { DocumentDeletionRequestResponse, DocumentResponse, IngestionJobStatusResponse, ReprocessResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";

type Props = { workspaceId: string; documentId: string; capabilities?: string[] };
function requestId() { return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`; }

export function DocumentDetail({ workspaceId, documentId, capabilities = [] }: Props) {
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [deletion, setDeletion] = useState<DocumentDeletionRequestResponse | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<IngestionJobStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const deletionKey = useRef<string | null>(null);
  const reprocessKey = useRef<string | null>(null);
  useEffect(() => {
    let active = true;
    void (async () => { const response = await browserRequest(`/v1/workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(documentId)}`); if (!active) return; if (!response.ok) { setError(`Unable to load document (${response.status})`); return; } const loaded = await response.json() as DocumentResponse; setDocument(loaded); if (loaded.ingestion_job_id) setJobId(loaded.ingestion_job_id); })();
    return () => { active = false; };
  }, [workspaceId, documentId]);
  useEffect(() => {
    if (!jobId) return; let active = true; let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => { const response = await browserRequest(`/v1/workspaces/${encodeURIComponent(workspaceId)}/ingestion-jobs/${encodeURIComponent(jobId)}`); if (!active) return; if (!response.ok) { setError(`Unable to load ingestion job (${response.status})`); return; } const status = await response.json() as IngestionJobStatusResponse; setJobStatus(status); if (status.poll_after_seconds > 0 && !["succeeded", "superseded", "failed"].includes(status.status)) timer = setTimeout(() => void poll(), status.poll_after_seconds * 1000); };
    void poll(); return () => { active = false; if (timer) clearTimeout(timer); };
  }, [workspaceId, jobId]);
  async function requestDeletion() {
    if (!deletionKey.current) deletionKey.current = requestId();
    const response = await browserRequest(`/v1/workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(documentId)}/deletion-request`, { method: "POST", headers: { "Idempotency-Key": deletionKey.current } });
    if (response.status === 403) { setError("Deletion requests require documents:delete access."); return; }
    if (!response.ok) { setError(`Unable to request deletion (${response.status})`); return; }
    setDeletion(await response.json() as DocumentDeletionRequestResponse); deletionKey.current = null;
  }
  async function reprocess() {
    if (!document?.current_document_version_id) return;
    if (!reprocessKey.current) reprocessKey.current = requestId();
    const response = await browserRequest(`/v1/workspaces/${encodeURIComponent(workspaceId)}/document-versions/${encodeURIComponent(document.current_document_version_id)}/reprocess`, { method: "POST", headers: { "Idempotency-Key": reprocessKey.current }, body: JSON.stringify({ config_mode: "current" }) });
    if (!response.ok) { setError(`Unable to reprocess document (${response.status})`); return; }
    const result = await response.json() as ReprocessResponse; reprocessKey.current = null; setJobStatus(null); setJobId(result.ingestion_job_id);
  }
  if (error && !document) return <p role="alert">{error}</p>; if (!document) return <p>Loading document…</p>;
  const canDelete = capabilities.includes("documents:delete"); const canWrite = capabilities.includes("documents:write");
  return <article><h1>{document.source_name}</h1><dl><dt>Source key</dt><dd>{document.source_key}</dd><dt>State</dt><dd>{document.archived ? "archived" : "active"}</dd><dt>Serving</dt><dd>{document.serving_state}</dd><dt>Revision</dt><dd>{document.revision}</dd><dt>Ingestion</dt><dd>{jobStatus?.status ?? document.ingestion_status ?? "unavailable"}</dd></dl>{jobId && <p>Ingestion job: {jobId}</p>}{jobStatus?.failure_reason && <p role="alert">Ingestion failure: {jobStatus.failure_reason}</p>}{canWrite && document.current_document_version_id && <button onClick={() => void reprocess()}>Reprocess document</button>}{canDelete && <button onClick={() => void requestDeletion()}>Request deletion</button>}{deletion && <p role="status">Deletion request: {deletion.state}{deletion.failure_reason ? ` (${deletion.failure_reason})` : ""}</p>}{error && <p role="alert">{error}</p>}</article>;
}
