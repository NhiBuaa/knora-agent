"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import type {
  DocumentDeletionRequestResponse,
  DocumentResponse,
  IngestionJobStatusResponse,
  IngestionResponse,
  PdfSubmissionResponse,
  ReprocessResponse,
} from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { routes } from "@/lib/navigation/routes";
import {
  documentStatus,
  jobIsActive,
  servingExplanation,
  sourceKind,
  statusClasses,
} from "@/lib/documents/presentation";
import { Button } from "@/components/ui/Button";
import { WorkspaceSelector } from "@/components/workspaces/WorkspaceSelector";
import { UploadDocumentDialog } from "./UploadDocumentDialog";
import { DocumentActionsMenu } from "./DocumentActionsMenu";
import { DeletionRequestDialog } from "./DeletionRequestDialog";
import "./documents.css";

function errorMessage(action: string, status: number) {
  return status === 401
    ? "Your session expired. Sign in again to continue."
    : `Unable to ${action} (${status})`;
}

export function DocumentList({
  workspaceId,
  workspaceName,
  capabilities = [],
  workspaceArchived = false,
}: {
  workspaceId: string;
  workspaceName?: string | null;
  capabilities?: string[];
  workspaceArchived?: boolean;
}) {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showArchived, setShowArchived] = useState(false);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadState, setUploadState] = useState<
    PdfSubmissionResponse | IngestionResponse | null
  >(null);
  const [busy, setBusy] = useState<string[]>([]);
  const [deleting, setDeleting] = useState<DocumentResponse | null>(null);
  const [deletionError, setDeletionError] = useState<string | null>(null);
  const [jobStates, setJobStates] = useState<
    Record<string, IngestionJobStatusResponse | { status: string }>
  >({});
  const scope = useRef<AbortController | null>(null);
  const uploadKey = useRef<string | null>(null);
  const reprocessKeys = useRef(new Map<string, string>());
  const deletionKeys = useRef(new Map<string, string>());
  const inFlight = useRef(new Set<string>());
  const polling = useRef(new Set<string>());
  const completed = useRef(new Set<string>());
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>());
  const canWrite =
    capabilities.includes("documents:write") && !workspaceArchived;
  const canDelete =
    capabilities.includes("documents:delete") && !workspaceArchived;
  const path = `/v1/workspaces/${encodeURIComponent(workspaceId)}`;

  const load = useCallback(
    async (controller: AbortController, initial = false) => {
      if (initial) setLoading(true);
      try {
        const response = await browserRequest(`${path}/documents`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (!response.ok) {
          setError(errorMessage("load documents", response.status));
          return;
        }
        const body = (await response.json()) as {
          documents: DocumentResponse[];
        };
        if (controller.signal.aborted) return;
        setDocuments(body.documents);
        setJobStates((previous) =>
          Object.fromEntries(
            Object.entries(previous).filter(([, job]) =>
              jobIsActive(job.status),
            ),
          ),
        );
      } catch {
        if (!controller.signal.aborted)
          setError("Unable to load documents. Retry this page.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    },
    [path],
  );

  useEffect(() => {
    const controller = new AbortController();
    scope.current = controller;
    setDocuments([]);
    setError(null);
    setUploadError(null);
    setDeletionError(null);
    setQuery("");
    setShowArchived(false);
    setUploadOpen(false);
    setFile(null);
    setUploadState(null);
    setDeleting(null);
    setJobStates({});
    setBusy([]);
    uploadKey.current = null;
    reprocessKeys.current.clear();
    deletionKeys.current.clear();
    inFlight.current.clear();
    polling.current.clear();
    completed.current.clear();
    void load(controller, true);
    const ownedTimers = timers.current;
    return () => {
      controller.abort();
      ownedTimers.forEach(clearTimeout);
      ownedTimers.clear();
    };
  }, [load]);

  const poll = useCallback(
    async function poll(
      documentId: string,
      jobId: string,
      controller: AbortController,
    ) {
      if (controller.signal.aborted) return;
      try {
        const response = await browserRequest(
          `${path}/ingestion-jobs/${encodeURIComponent(jobId)}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        if (!response.ok) {
          polling.current.delete(jobId);
          setError(errorMessage("check ingestion status", response.status));
          return;
        }
        const status = (await response.json()) as IngestionJobStatusResponse;
        if (controller.signal.aborted) return;
        setJobStates((previous) => ({ ...previous, [documentId]: status }));
        setUploadState((previous) =>
          previous &&
          "ingestion_job_id" in previous &&
          previous.ingestion_job_id === jobId
            ? { ...previous, status: status.status }
            : previous,
        );
        if (!jobIsActive(status.status)) {
          polling.current.delete(jobId);
          completed.current.add(jobId);
          await load(controller);
          return;
        }
        const timer = setTimeout(
          () => {
            timers.current.delete(timer);
            void poll(documentId, jobId, controller);
          },
          Math.max(1000, (status.poll_after_seconds || 2) * 1000),
        );
        timers.current.add(timer);
      } catch {
        if (!controller.signal.aborted) {
          polling.current.delete(jobId);
          setError(
            "Unable to check ingestion status. Reload to see the latest job state.",
          );
        }
      }
    },
    [path, load],
  );

  useEffect(() => {
    const controller = scope.current;
    if (!controller || controller.signal.aborted) return;
    for (const document of documents) {
      const jobId = document.ingestion_job_id;
      if (
        jobId &&
        jobIsActive(document.ingestion_status) &&
        !polling.current.has(jobId) &&
        !completed.current.has(jobId)
      ) {
        polling.current.add(jobId);
        void poll(document.document_id, jobId, controller);
      }
    }
  }, [documents, poll]);

  function begin(id: string) {
    if (inFlight.current.has(id)) return false;
    inFlight.current.add(id);
    setBusy([...inFlight.current]);
    return true;
  }
  function finish(id: string, controller: AbortController) {
    if (controller.signal.aborted) return;
    inFlight.current.delete(id);
    setBusy([...inFlight.current]);
  }
  function identity(keys: Map<string, string>, id: string) {
    let key = keys.get(id);
    if (!key) {
      key = crypto.randomUUID();
      keys.set(id, key);
    }
    return key;
  }
  function canReprocess(document: DocumentResponse) {
    return (
      canWrite &&
      !document.archived &&
      Boolean(
        document.current_document_version_id && document.reprocess_supported,
      ) &&
      !jobIsActive(document.ingestion_status) &&
      !jobIsActive(jobStates[document.document_id]?.status) &&
      !["requested", "processing", "succeeded"].includes(
        document.deletion_request?.state ?? "",
      )
    );
  }
  async function reprocess(document: DocumentResponse) {
    const controller = scope.current;
    const id = document.document_id;
    if (!controller || !canReprocess(document) || !begin(id)) return;
    setError(null);
    try {
      const response = await browserRequest(
        `${path}/document-versions/${encodeURIComponent(document.current_document_version_id!)}/reprocess`,
        {
          method: "POST",
          headers: { "Idempotency-Key": identity(reprocessKeys.current, id) },
          body: JSON.stringify({ config_mode: "deployed" }),
          signal: controller.signal,
        },
      );
      if (controller.signal.aborted) return;
      if (!response.ok) {
        if (response.status === 409) {
          reprocessKeys.current.delete(id);
          await load(controller);
        }
        if (!controller.signal.aborted)
          setError(
            response.status === 409
              ? "This document changed. Reload and try again."
              : errorMessage("re-index document", response.status),
          );
        return;
      }
      const result = (await response.json()) as ReprocessResponse;
      if (controller.signal.aborted) return;
      reprocessKeys.current.delete(id);
      setJobStates((previous) => ({
        ...previous,
        [id]: { status: result.status },
      }));
      if (!jobIsActive(result.status)) await load(controller);
      else if (!polling.current.has(result.ingestion_job_id)) {
        polling.current.add(result.ingestion_job_id);
        void poll(id, result.ingestion_job_id, controller);
      }
    } catch {
      if (!controller.signal.aborted)
        setError(
          "Unable to confirm re-index submission. Retry with the same request key.",
        );
    } finally {
      finish(id, controller);
    }
  }
  async function archive(document: DocumentResponse) {
    const controller = scope.current;
    const id = document.document_id;
    if (!controller || !canWrite || !begin(id)) return;
    setError(null);
    try {
      const response = await browserRequest(
        `${path}/documents/${encodeURIComponent(id)}/${document.archived ? "unarchive" : "archive"}`,
        {
          method: "POST",
          headers: { "If-Match": String(document.revision) },
          signal: controller.signal,
        },
      );
      if (controller.signal.aborted) return;
      if (response.status === 409) {
        await load(controller);
        if (!controller.signal.aborted)
          setError("This document changed. Reload and try again.");
        return;
      }
      if (!response.ok) {
        setError(errorMessage("update document", response.status));
        return;
      }
      await load(controller);
    } catch {
      if (!controller.signal.aborted)
        setError(
          "Unable to confirm the document change. Reload before retrying.",
        );
    } finally {
      finish(id, controller);
    }
  }
  async function requestDeletion() {
    const controller = scope.current;
    const document = deleting;
    if (!controller || !document || !canDelete || !begin(document.document_id))
      return;
    setDeletionError(null);
    try {
      const response = await browserRequest(
        `${path}/documents/${encodeURIComponent(document.document_id)}/deletion-request`,
        {
          method: "POST",
          headers: {
            "Idempotency-Key": identity(
              deletionKeys.current,
              document.document_id,
            ),
          },
          signal: controller.signal,
        },
      );
      if (controller.signal.aborted) return;
      if (!response.ok) {
        setDeletionError(errorMessage("request deletion", response.status));
        return;
      }
      const deletion =
        (await response.json()) as DocumentDeletionRequestResponse;
      if (controller.signal.aborted) return;
      deletionKeys.current.delete(document.document_id);
      setDocuments((previous) =>
        previous.map((item) =>
          item.document_id === document.document_id
            ? { ...item, deletion_request: deletion }
            : item,
        ),
      );
      setDeleting(null);
      await load(controller);
    } catch {
      if (!controller.signal.aborted)
        setDeletionError(
          "Unable to confirm deletion submission. Retry with the same request key.",
        );
    } finally {
      finish(document.document_id, controller);
    }
  }
  function closeUpload() {
    if (inFlight.current.has("upload")) return;
    setUploadOpen(false);
    setFile(null);
    setUploadError(null);
    uploadKey.current = null;
  }
  async function upload() {
    const controller = scope.current;
    if (!controller || !file || !canWrite || !begin("upload")) return;
    setUploadError(null);
    try {
      const body = new FormData();
      body.set("source_key", file.name);
      body.set("file", file);
      if (!uploadKey.current) uploadKey.current = crypto.randomUUID();
      const response = await browserRequest(`${path}/documents`, {
        method: "POST",
        headers: { "Idempotency-Key": uploadKey.current },
        body,
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (!response.ok) {
        if (response.status === 409) uploadKey.current = null;
        setUploadError(errorMessage("upload document", response.status));
        return;
      }
      const result = (await response.json()) as
        | PdfSubmissionResponse
        | IngestionResponse;
      if (controller.signal.aborted) return;
      setUploadState(result);
      uploadKey.current = null;
      setFile(null);
      setUploadOpen(false);
      await load(controller);
      if (
        !controller.signal.aborted &&
        "ingestion_job_id" in result &&
        jobIsActive(result.status) &&
        !polling.current.has(result.ingestion_job_id)
      ) {
        polling.current.add(result.ingestion_job_id);
        void poll(result.document_id, result.ingestion_job_id, controller);
      }
    } catch {
      if (!controller.signal.aborted)
        setUploadError(
          "Unable to confirm upload submission. Retry with the same file and request key.",
        );
    } finally {
      finish("upload", controller);
    }
  }
  const visible = documents.filter(
    (document) =>
      (showArchived || !document.archived) &&
      `${document.source_name} ${document.source_key}`
        .toLocaleLowerCase()
        .includes(query.trim().toLocaleLowerCase()),
  );
  return (
    <section
      aria-label="Documents"
      className="m-0 flex min-w-0 flex-col gap-7 rounded-none border-0 bg-transparent p-0 text-text-primary"
    >
      <header className="flex min-h-[108px] flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-[7px]">
          {workspaceName !== undefined && (
            <div className="relative w-fit max-w-full [&_.workspace-selector-heading]:min-h-4 [&_.workspace-selector-heading>.kn-menu]:hidden [&_.workspace-selector-trigger]:m-0 [&_.workspace-selector-trigger]:pr-3.5 [&_.workspace-selector-trigger]:text-[13px] [&_.workspace-selector-trigger]:leading-4 [&_.workspace-caret-small]:hidden [&_.workspace-caret-context]:hidden">
              <WorkspaceSelector
                workspaceId={workspaceId}
                workspaceName={workspaceName}
              />
              {/* eslint-disable-next-line @next/next/no-img-element -- Exact 8×5 original Documents caret. */}
              <img
                alt=""
                src="/icons/figma/d9407.svg"
                width={8}
                height={5}
                className="documents-workspace-caret"
              />
            </div>
          )}
          <h1 className="m-0 font-display text-[32px] leading-10 font-semibold">
            Documents
          </h1>
          <p className="m-0 text-sm leading-[17px] text-text-muted">
            {!canWrite && !workspaceArchived
              ? "Read documents in this workspace. Management actions are unavailable with your current access."
              : "Sources Knora can use when answering questions in this workspace."}
          </p>
        </div>
        {canWrite ? (
          <Button
            className="h-[38px] min-h-[38px] px-3 py-0 text-[13px]"
            onClick={() => setUploadOpen(true)}
          >
            <span aria-hidden="true">+</span>Upload document
          </Button>
        ) : (
          <span className="rounded-lg bg-[color-mix(in_srgb,var(--signature)_10%,var(--surface))] px-3.5 py-2.5 text-[13px] font-semibold text-signature">
            {workspaceArchived ? "Read-only" : "Limited permissions"}
          </span>
        )}
      </header>
      {workspaceArchived && (
        <p role="status" className="m-0 text-sm text-signature">
          This Workspace is read-only.
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <label className="flex h-10 w-full max-w-[430px] items-center gap-2 rounded-lg border border-border px-3 text-text-muted">
          <span aria-hidden="true">⌕</span>
          <input
            type="search"
            aria-label="Search documents"
            placeholder="Search documents…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="min-w-0 flex-1 border-0 bg-transparent p-0 text-xs text-text-primary placeholder:text-text-muted"
          />
        </label>
        <div className="flex items-center gap-[18px] text-xs text-text-muted">
          <span>
            {visible.length} {visible.length === 1 ? "document" : "documents"}
          </span>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              className="size-4 accent-action"
              checked={showArchived}
              onChange={(event) => setShowArchived(event.target.checked)}
            />
            Show archived
          </label>
        </div>
      </div>
      {uploadState && (
        <p role="status" className="m-0 text-sm">
          Upload:{" "}
          {"status" in uploadState ? uploadState.status : uploadState.outcome}
          {"ingestion_job_id" in uploadState
            ? ` · job ${uploadState.ingestion_job_id}`
            : ""}
        </p>
      )}
      {error && (
        <p role="alert" className="m-0 text-sm text-status-error">
          {error}
          {error.includes("session expired") && (
            <>
              {" "}
              <a
                href="/api/auth/login"
                target="_blank"
                rel="noopener noreferrer"
              >
                Sign in
              </a>
            </>
          )}
        </p>
      )}
      {loading && <p className="m-0">Loading documents…</p>}
      {!loading && !visible.length && !error && (
        <p className="m-0">
          {query.trim() ? "No documents found." : "No documents yet."}
        </p>
      )}
      {visible.length > 0 && (
        <div className="min-w-0 rounded-lg border border-border">
          <div className="hidden h-[42px] grid-cols-[minmax(0,1fr)_220px_130px] items-center gap-4 rounded-t-lg bg-surface-subtle pr-3 pl-[18px] text-[10px] font-semibold text-text-muted md:grid">
            <span>DOCUMENT</span>
            <span>STATUS</span>
            <span className="text-right">
              {canWrite || canDelete ? "ACTIONS" : "ACCESS"}
            </span>
          </div>
          <ul aria-label="Documents" className="m-0 list-none p-0">
            {visible.map((document) => {
              const observed = jobStates[document.document_id];
              const projection =
                observed && "serving_state" in observed
                  ? {
                      ...document,
                      ingestion_status: observed.status,
                      current_document_version_id:
                        observed.current_document_version_id,
                      serving_state: observed.serving_state,
                      served_document_version_id:
                        observed.served_document_version_id,
                    }
                  : observed
                    ? { ...document, ingestion_status: observed.status }
                    : document;
              const view = documentStatus(projection);
              const serving = servingExplanation(projection);
              const retry =
                canReprocess(document) &&
                (document.embedding_readiness === "reindex_required" ||
                  document.ingestion_status === "failed");
              return (
                <li
                  key={document.document_id}
                  className="m-0 grid min-h-[72px] grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 border-t border-border py-3 pr-3 pl-[18px] first:rounded-t-lg last:rounded-b-lg md:grid-cols-[minmax(0,1fr)_220px_130px]"
                >
                  <div className="col-span-2 flex min-w-0 flex-col gap-[5px] md:col-span-1">
                    <Link
                      className="text-sm leading-[18px] font-medium text-text-primary no-underline [overflow-wrap:anywhere] hover:text-action-text"
                      href={routes.document(workspaceId, document.document_id)}
                    >
                      {document.source_name}
                    </Link>
                    <p className="m-0 text-xs leading-[15px] text-text-muted">
                      {sourceKind(document.source_name).label} document
                      {document.answer_availability === "unavailable"
                        ? " · Not available for new answers"
                        : document.answer_availability === "available"
                          ? ""
                          : " · Answer availability unavailable"}
                    </p>
                  </div>
                  <div className="flex min-w-0 flex-col items-start gap-1">
                    <span
                      className={`rounded-full px-[9px] py-1 text-[11px] leading-[13px] font-medium ${statusClasses[view.tone]} ${view.label === "Needs re-index" ? "border border-signature" : ""}`}
                    >
                      {view.label}
                    </span>
                    {serving && (
                      <p className="m-0 text-xs text-text-muted [overflow-wrap:anywhere]">
                        {serving}
                      </p>
                    )}
                    {view.detail && (
                      <p className="m-0 text-xs text-signature [overflow-wrap:anywhere]">
                        {view.detail}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center justify-end gap-3.5">
                    {retry && (
                      <Button
                        variant="ghost"
                        className="min-h-8 border-0 px-0 py-0 text-xs !text-action-text"
                        aria-label={`${document.ingestion_status === "failed" ? "Try again" : "Re-index"} ${document.source_name}`}
                        disabled={busy.includes(document.document_id)}
                        onClick={() => void reprocess(document)}
                      >
                        {document.ingestion_status === "failed"
                          ? "Try again"
                          : "Re-index"}
                      </Button>
                    )}
                    {canWrite || canDelete ? (
                      <DocumentActionsMenu
                        document={document}
                        canWrite={canWrite}
                        canDelete={canDelete}
                        canReprocess={canReprocess(document)}
                        busy={busy.includes(document.document_id)}
                        onReprocess={() => void reprocess(document)}
                        onArchive={() => void archive(document)}
                        onDelete={() => {
                          setDeletionError(null);
                          setDeleting(document);
                        }}
                      />
                    ) : (
                      <span className="text-xs text-text-muted">View only</span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <UploadDocumentDialog
        open={uploadOpen}
        file={file}
        busy={busy.includes("upload")}
        error={uploadError}
        onFile={(selected) => {
          if (inFlight.current.has("upload")) return;
          setFile(selected);
          uploadKey.current = null;
          setUploadError(null);
        }}
        onClose={closeUpload}
        onUpload={() => void upload()}
      />
      <DeletionRequestDialog
        document={deleting}
        busy={Boolean(deleting && busy.includes(deleting.document_id))}
        error={deletionError}
        onClose={() => {
          if (deleting && !inFlight.current.has(deleting.document_id))
            setDeleting(null);
        }}
        onConfirm={() => void requestDeletion()}
      />
    </section>
  );
}
