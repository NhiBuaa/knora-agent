"use client";

import React, {
  FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import type {
  DocumentResponse,
  IngestionJobStatusResponse,
  IngestionResponse,
  PdfSubmissionResponse,
  ReprocessResponse,
} from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";

function errorMessage(action: string, status: number) {
  return `Unable to ${action} (${status})`;
}

function jobIsActive(status: string | null | undefined) {
  return (
    status === "queued" ||
    status === "processing" ||
    status === "retry_scheduled"
  );
}

export function DocumentList({
  workspaceId,
  capabilities = [],
  workspaceArchived = false,
}: {
  workspaceId: string;
  capabilities?: string[];
  workspaceArchived?: boolean;
}) {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<
    (PdfSubmissionResponse | IngestionResponse) | null
  >(null);
  const uploadKey = useRef<string | null>(null);
  const reindexKeys = useRef<Map<string, string>>(new Map());
  const pollingJobs = useRef<Set<string>>(new Set());
  const pollTimers = useRef<Array<ReturnType<typeof setTimeout>>>([]);
  const [reindexStatus, setReindexStatus] = useState<Record<string, string>>(
    {},
  );
  const canWrite =
    capabilities.includes("documents:write") && !workspaceArchived;
  const load = useCallback(async () => {
    const response = await browserRequest(
      `/v1/workspaces/${encodeURIComponent(workspaceId)}/documents`,
    );
    if (!response.ok) {
      setError(errorMessage("load documents", response.status));
      return;
    }
    const body = (await response.json()) as { documents: DocumentResponse[] };
    setDocuments(body.documents);
  }, [workspaceId]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    const timers = pollTimers.current;
    return () => {
      timers.forEach(clearTimeout);
    };
  }, []);

  const pollReindex = useCallback(
    async function pollReindex(documentId: string, jobId: string) {
      try {
        const response = await browserRequest(
          `/v1/workspaces/${encodeURIComponent(workspaceId)}/ingestion-jobs/${encodeURIComponent(jobId)}`,
        );
        if (!response.ok) {
          pollingJobs.current.delete(jobId);
          setError(errorMessage("check re-index status", response.status));
          return;
        }
        const status = (await response.json()) as IngestionJobStatusResponse;
        setReindexStatus((previous) => ({
          ...previous,
          [documentId]: status.status,
        }));
        if (["succeeded", "failed", "superseded"].includes(status.status)) {
          pollingJobs.current.delete(jobId);
          await load();
          return;
        }
        const delay = Math.max(1000, (status.poll_after_seconds || 2) * 1000);
        pollTimers.current.push(
          setTimeout(() => void pollReindex(documentId, jobId), delay),
        );
      } catch {
        pollingJobs.current.delete(jobId);
        setError(
          "Unable to check re-index status. Reload to see the latest job state.",
        );
      }
    },
    [workspaceId, load],
  );
  useEffect(() => {
    for (const document of documents) {
      const jobId = document.ingestion_job_id;
      if (
        jobId &&
        jobIsActive(document.ingestion_status) &&
        document.embedding_readiness === "reindex_required" &&
        !pollingJobs.current.has(jobId)
      ) {
        pollingJobs.current.add(jobId);
        void pollReindex(document.document_id, jobId);
      }
    }
  }, [documents, pollReindex]);

  async function reindex(document: DocumentResponse) {
    if (
      !canWrite ||
      document.archived ||
      !document.reprocess_supported ||
      jobIsActive(document.ingestion_status) ||
      jobIsActive(reindexStatus[document.document_id])
    )
      return;
    const versionId = document.current_document_version_id;
    if (!versionId) return;
    setError(null);
    let key = reindexKeys.current.get(document.document_id);
    if (!key) {
      if (typeof crypto.randomUUID !== "function") {
        setError("A secure browser is required to re-index this document.");
        return;
      }
      key = crypto.randomUUID();
      reindexKeys.current.set(document.document_id, key);
    }
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/document-versions/${encodeURIComponent(versionId)}/reprocess`,
        {
          method: "POST",
          headers: { "Idempotency-Key": key },
          body: JSON.stringify({ config_mode: "deployed" }),
        },
      );
      if (!response.ok) {
        if (response.status === 409)
          reindexKeys.current.delete(document.document_id);
        setError(errorMessage("re-index document", response.status));
        return;
      }
      const result = (await response.json()) as ReprocessResponse;
      reindexKeys.current.delete(document.document_id);
      setReindexStatus((previous) => ({
        ...previous,
        [document.document_id]: result.status,
      }));
      if (["succeeded", "failed", "superseded"].includes(result.status)) {
        await load();
      } else {
        pollingJobs.current.add(result.ingestion_job_id);
        await pollReindex(document.document_id, result.ingestion_job_id);
      }
    } catch {
      setError(
        "Unable to confirm re-index submission. Retry with the same request key.",
      );
    }
  }
  async function mutate(
    document: DocumentResponse,
    action: "archive" | "unarchive",
  ) {
    setError(null);
    const response = await browserRequest(
      `/v1/workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(document.document_id)}/${action}`,
      { method: "POST", headers: { "If-Match": String(document.revision) } },
    );
    if (response.status === 409) {
      await load();
      setError("This document changed. Reload and try again.");
      return;
    }
    if (!response.ok) {
      setError(errorMessage(`${action} document`, response.status));
      return;
    }
    await load();
  }
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    setError(null);
    const body = new FormData();
    body.set("source_key", file.name);
    body.set("file", file);
    if (!uploadKey.current)
      uploadKey.current =
        typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random()}`;
    const response = await browserRequest(
      `/v1/workspaces/${encodeURIComponent(workspaceId)}/documents`,
      {
        method: "POST",
        headers: { "Idempotency-Key": uploadKey.current },
        body,
      },
    );
    if (!response.ok) {
      setError(errorMessage("upload document", response.status));
      return;
    }
    setUploadState(
      (await response.json()) as PdfSubmissionResponse | IngestionResponse,
    );
    uploadKey.current = null;
    await load();
  }
  const visibleDocuments = documents.filter(
    (document) => showArchived || !document.archived,
  );
  return (
    <section>
      <div className="toolbar">
        <h1>Documents</h1>
        <label>
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(event) => setShowArchived(event.target.checked)}
          />{" "}
          Show archived
        </label>
      </div>
      {canWrite && (
        <form onSubmit={(event) => void upload(event)}>
          <label htmlFor="document-file">Document file</label>
          <input
            id="document-file"
            type="file"
            accept=".pdf,.md,.markdown,.txt,.text"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <button type="submit" disabled={!file}>
            Upload document
          </button>
        </form>
      )}
      {uploadState && (
        <p role="status">
          Upload:{" "}
          {"status" in uploadState ? uploadState.status : uploadState.outcome}
          {"ingestion_job_id" in uploadState
            ? ` · job ${uploadState.ingestion_job_id}`
            : ""}
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {!visibleDocuments.length && !error && <p>No documents yet.</p>}
      <ul>
        {visibleDocuments.map((document) => (
          <li key={document.document_id}>
            <Link href={`/app/documents/${document.document_id}`}>
              {document.source_name}
            </Link>
            <span>
              {" "}
              · {document.archived ? "archived" : "active"} · serving:{" "}
              {document.serving_state}
            </span>
            {document.ingestion_status && (
              <span> · ingestion: {document.ingestion_status}</span>
            )}
            {document.embedding_readiness === "reindex_required" && (
              <span> · Re-index required</span>
            )}
            {document.embedding_readiness === "ready" && (
              <span> · Embedding ready</span>
            )}
            {reindexStatus[document.document_id] && (
              <span> · Re-index: {reindexStatus[document.document_id]}</span>
            )}
            {canWrite &&
              !document.archived &&
              document.reprocess_supported &&
              document.embedding_readiness === "reindex_required" &&
              !jobIsActive(document.ingestion_status) &&
              !jobIsActive(reindexStatus[document.document_id]) && (
                <button onClick={() => void reindex(document)}>
                  Re-index {document.source_name}
                </button>
              )}
            {canWrite && (
              <button
                onClick={() =>
                  void mutate(
                    document,
                    document.archived ? "unarchive" : "archive",
                  )
                }
              >
                {document.archived ? "Unarchive" : "Archive"}
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
