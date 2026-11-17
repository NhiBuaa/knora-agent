"use client";

import { LeafLoading } from "@/components/ui/LeafLoading";
import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
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
  reprocessConfiguration,
  derivationIsActive,
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

const MAX_POLLING_RETRIES = 7;
const POLL_TIMEOUT_MS = 10000;
const POLLING_NETWORK_ERROR =
  "Unable to check ingestion status. Reload to see the latest job state.";

function createPollSignal(
  parentSignal: AbortSignal,
  timeoutMs = POLL_TIMEOUT_MS,
) {
  const timeoutController = new AbortController();
  const timer = setTimeout(() => {
    timeoutController.abort(new Error("Polling request timed out"));
  }, timeoutMs);
  const onParentAbort = () => timeoutController.abort(parentSignal.reason);
  if (parentSignal.aborted) {
    timeoutController.abort(parentSignal.reason);
  } else {
    parentSignal.addEventListener("abort", onParentAbort, { once: true });
  }
  return {
    signal: timeoutController.signal,
    cleanup: () => {
      clearTimeout(timer);
      parentSignal.removeEventListener("abort", onParentAbort);
    },
  };
}

function errorMessage(action: string, status: number) {
  return status === 401
    ? "Your session expired. Sign in again to continue."
    : `Unable to ${action} (${status})`;
}

function parseRetryAfter(response: Response, defaultDelayMs: number): number {
  const retryAfter = response.headers.get("Retry-After");
  if (!retryAfter) return defaultDelayMs;
  const seconds = Number(retryAfter);
  if (!Number.isNaN(seconds) && seconds >= 0) {
    return Math.min(30000, seconds * 1000);
  }
  const date = Date.parse(retryAfter);
  if (!Number.isNaN(date)) {
    const diff = date - Date.now();
    return Math.max(0, Math.min(30000, diff));
  }
  return defaultDelayMs;
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
  const router = useRouter();
  const searchParams = useSearchParams();
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showArchived, setShowArchived] = useState(
    () => searchParams?.get("archived") === "true",
  );
  const [query, setQuery] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [pollingError, setPollingError] = useState<string | null>(null);
  const error = actionError || pollingError;
  const [limitedPermissions, setLimitedPermissions] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadState, setUploadState] = useState<
    PdfSubmissionResponse | IngestionResponse | null
  >(null);
  const uploadStateRef = useRef<
    PdfSubmissionResponse | IngestionResponse | null
  >(uploadState);
  uploadStateRef.current = uploadState;
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
  const loadSeq = useRef(0);
  const lastAppliedSeq = useRef(0);
  const inFlight = useRef(new Set<string>());
  const inFlightPolls = useRef(new Set<string>());
  const polling = useRef(new Set<string>());
  const pollingErrors = useRef(new Map<string, string>());
  const completed = useRef(new Set<string>());
  const exhausted = useRef(new Set<string>());
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>());
  const jobTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const documentsRef = useRef<DocumentResponse[]>(documents);
  documentsRef.current = documents;
  const canWrite =
    capabilities.includes("documents:write") && !workspaceArchived;
  const canDelete =
    capabilities.includes("documents:delete") && !workspaceArchived;
  const path = `/v1/workspaces/${encodeURIComponent(workspaceId)}`;

  const syncPollingError = useCallback(() => {
    const uploadDocId =
      uploadStateRef.current && "document_id" in uploadStateRef.current
        ? uploadStateRef.current.document_id
        : null;
    const uploadJobId =
      uploadStateRef.current && "ingestion_job_id" in uploadStateRef.current
        ? uploadStateRef.current.ingestion_job_id
        : null;

    const activeJobIds = new Set<string>();
    for (const doc of documentsRef.current) {
      if (doc.ingestion_job_id && derivationIsActive(doc)) {
        activeJobIds.add(doc.ingestion_job_id);
      }
    }
    for (const id of polling.current) {
      activeJobIds.add(id);
    }
    for (const id of exhausted.current) {
      const doc = documentsRef.current.find((d) => d.ingestion_job_id === id);
      if (doc && derivationIsActive(doc)) {
        activeJobIds.add(id);
      } else if (
        id === uploadJobId &&
        uploadDocId &&
        !documentsRef.current.some(
          (d) => d.document_id === uploadDocId && d.ingestion_job_id !== id,
        )
      ) {
        activeJobIds.add(id);
      } else {
        exhausted.current.delete(id);
      }
    }
    for (const id of pollingErrors.current.keys()) {
      if (!activeJobIds.has(id)) {
        pollingErrors.current.delete(id);
      }
    }
    if (pollingErrors.current.size === 0) {
      setPollingError(null);
    } else {
      setPollingError(pollingErrors.current.values().next().value ?? null);
    }
  }, []);

  const isJobCurrent = useCallback((documentId: string, jobId: string) => {
    const upload = uploadStateRef.current;
    if (
      upload &&
      "document_id" in upload &&
      upload.document_id === documentId &&
      "ingestion_job_id" in upload &&
      upload.ingestion_job_id === jobId
    ) {
      return true;
    }
    const doc = documentsRef.current.find((d) => d.document_id === documentId);
    if (doc) {
      return Boolean(doc.ingestion_job_id && doc.ingestion_job_id === jobId);
    }
    return false;
  }, []);

  const load = useCallback(
    async (controller: AbortController, initial = false) => {
      const currentSeq = ++loadSeq.current;
      if (initial) setLoading(true);
      try {
        const response = await browserRequest(`${path}/documents`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (!response.ok) {
          if (currentSeq === loadSeq.current) {
            if (response.status === 403) {
              setLimitedPermissions(true);
              setActionError(null);
            } else {
              setLimitedPermissions(false);
              setActionError(errorMessage("load documents", response.status));
            }
          }
          return;
        }
        if (currentSeq === loadSeq.current) {
          setLimitedPermissions(false);
          setActionError(null);
        }
        const body = (await response.json()) as {
          documents?: DocumentResponse[];
        };
        if (controller.signal.aborted) return;
        const loadedDocs = (
          Array.isArray(body?.documents) ? body.documents : []
        ).map((doc) => {
          const upload = uploadStateRef.current;
          if (
            upload &&
            "document_id" in upload &&
            upload.document_id === doc.document_id &&
            "ingestion_job_id" in upload &&
            upload.ingestion_job_id &&
            jobIsActive(upload.status) &&
            doc.ingestion_job_id !== upload.ingestion_job_id
          ) {
            return {
              ...doc,
              ingestion_job_id: upload.ingestion_job_id,
              ingestion_status: upload.status,
            };
          }
          return doc;
        });
        if (currentSeq > lastAppliedSeq.current) {
          lastAppliedSeq.current = currentSeq;
          setDocuments(loadedDocs);
          documentsRef.current = loadedDocs;
          syncPollingError();
          setJobStates((previous) =>
            Object.fromEntries(
              Object.entries(previous).filter(([, job]) =>
                derivationIsActive({
                  ingestion_status: job.status,
                  indexing_status:
                    "indexing_status" in job ? job.indexing_status : null,
                }),
              ),
            ),
          );
        }
      } catch {
        if (!controller.signal.aborted && currentSeq === loadSeq.current)
          setActionError("Unable to load documents. Retry this page.");
      } finally {
        if (!controller.signal.aborted && currentSeq === loadSeq.current)
          setLoading(false);
      }
    },
    [path, syncPollingError],
  );

  useEffect(() => {
    const controller = new AbortController();
    scope.current = controller;
    setDocuments([]);
    setActionError(null);
    setPollingError(null);
    setLimitedPermissions(false);
    setUploadError(null);
    setDeletionError(null);
    setQuery("");
    setShowArchived(searchParams?.get("archived") === "true");
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
    inFlightPolls.current.clear();
    polling.current.clear();
    pollingErrors.current.clear();
    completed.current.clear();
    exhausted.current.clear();
    void load(controller, true);
    const ownedTimers = timers.current;
    const ownedJobTimers = jobTimers.current;
    return () => {
      controller.abort();
      ownedTimers.forEach(clearTimeout);
      ownedTimers.clear();
      ownedJobTimers.clear();
      inFlightPolls.current.clear();
    };
    // The query is an initialization preference; checkbox changes remain local state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  const poll = useCallback(
    async function poll(
      documentId: string,
      jobId: string,
      controller: AbortController,
      retryCount = 0,
    ) {
      if (controller.signal.aborted) return;
      if (inFlightPolls.current.has(jobId)) return;
      inFlightPolls.current.add(jobId);
      try {
        if (!isJobCurrent(documentId, jobId)) {
          polling.current.delete(jobId);
          pollingErrors.current.delete(jobId);
          exhausted.current.delete(jobId);
          syncPollingError();
          return;
        }
        const { signal: pollSignal, cleanup } = createPollSignal(
          controller.signal,
        );
        try {
          const response = await browserRequest(
            `${path}/ingestion-jobs/${encodeURIComponent(jobId)}`,
            { signal: pollSignal },
          );
          if (controller.signal.aborted) {
            cleanup();
            return;
          }
          if (!isJobCurrent(documentId, jobId)) {
            cleanup();
            polling.current.delete(jobId);
            pollingErrors.current.delete(jobId);
            exhausted.current.delete(jobId);
            syncPollingError();
            return;
          }
          if (!response.ok) {
            cleanup();
            const err = errorMessage("check ingestion status", response.status);
            pollingErrors.current.set(jobId, err);
            const isRetryableStatus =
              response.status >= 500 || response.status === 429;
            if (isRetryableStatus && retryCount < MAX_POLLING_RETRIES) {
              syncPollingError();
              const baseDelay = Math.min(
                10000,
                1500 * Math.pow(1.5, retryCount),
              );
              const defaultDelay = baseDelay + Math.random() * 500;
              const delay =
                response.status === 429
                  ? parseRetryAfter(response, defaultDelay)
                  : defaultDelay;
              const timer = setTimeout(() => {
                timers.current.delete(timer);
                if (jobTimers.current.get(jobId) === timer) {
                  jobTimers.current.delete(jobId);
                }
                void poll(documentId, jobId, controller, retryCount + 1);
              }, delay);
              timers.current.add(timer);
              jobTimers.current.set(jobId, timer);
              return;
            }
            polling.current.delete(jobId);
            exhausted.current.add(jobId);
            syncPollingError();
            return;
          }
          pollingErrors.current.delete(jobId);
          syncPollingError();
          const status = (await response.json()) as IngestionJobStatusResponse;
          cleanup();
          if (controller.signal.aborted) return;
          if (!isJobCurrent(documentId, jobId)) {
            polling.current.delete(jobId);
            pollingErrors.current.delete(jobId);
            exhausted.current.delete(jobId);
            syncPollingError();
            return;
          }
          setJobStates((previous) => ({ ...previous, [documentId]: status }));
          setUploadState((previous) =>
            previous &&
            "ingestion_job_id" in previous &&
            previous.ingestion_job_id === jobId
              ? { ...previous, status: status.status }
              : previous,
          );
          if (
            !derivationIsActive({
              ingestion_status: status.status,
              indexing_status: status.indexing_status,
            })
          ) {
            polling.current.delete(jobId);
            pollingErrors.current.delete(jobId);
            completed.current.add(jobId);
            syncPollingError();
            await load(controller);
            return;
          }
          const timer = setTimeout(
            () => {
              timers.current.delete(timer);
              if (jobTimers.current.get(jobId) === timer) {
                jobTimers.current.delete(jobId);
              }
              void poll(documentId, jobId, controller, 0);
            },
            Math.max(1000, (status.poll_after_seconds || 2) * 1000),
          );
          timers.current.add(timer);
          jobTimers.current.set(jobId, timer);
        } catch {
          cleanup();
          if (!controller.signal.aborted) {
            if (!isJobCurrent(documentId, jobId)) {
              polling.current.delete(jobId);
              pollingErrors.current.delete(jobId);
              exhausted.current.delete(jobId);
              syncPollingError();
              return;
            }
            pollingErrors.current.set(jobId, POLLING_NETWORK_ERROR);
            if (retryCount < MAX_POLLING_RETRIES) {
              syncPollingError();
              const baseDelay = Math.min(
                10000,
                1500 * Math.pow(1.5, retryCount),
              );
              const delay = baseDelay + Math.random() * 500;
              const timer = setTimeout(() => {
                timers.current.delete(timer);
                if (jobTimers.current.get(jobId) === timer) {
                  jobTimers.current.delete(jobId);
                }
                void poll(documentId, jobId, controller, retryCount + 1);
              }, delay);
              timers.current.add(timer);
              jobTimers.current.set(jobId, timer);
              return;
            }
            polling.current.delete(jobId);
            exhausted.current.add(jobId);
            syncPollingError();
          }
        }
      } finally {
        inFlightPolls.current.delete(jobId);
      }
    },
    [path, load, syncPollingError, isJobCurrent],
  );

  const retryPolling = useCallback(() => {
    const controller = scope.current;
    if (!controller || controller.signal.aborted) return;

    let targetJobId: string | null = null;
    for (const [id, msg] of pollingErrors.current.entries()) {
      if (msg === pollingError) {
        targetJobId = id;
        break;
      }
    }
    if (!targetJobId) {
      targetJobId = pollingErrors.current.keys().next().value ?? null;
    }
    if (!targetJobId) return;

    const doc = documentsRef.current.find(
      (d) => d.ingestion_job_id === targetJobId,
    );
    if (doc && derivationIsActive(doc)) {
      const existingTimer = jobTimers.current.get(targetJobId);
      if (existingTimer) {
        clearTimeout(existingTimer);
        timers.current.delete(existingTimer);
        jobTimers.current.delete(targetJobId);
      }
      exhausted.current.delete(targetJobId);
      completed.current.delete(targetJobId);
      if (!inFlightPolls.current.has(targetJobId)) {
        polling.current.add(targetJobId);
        void poll(doc.document_id, targetJobId, controller, 0);
      }
      return;
    }

    const upload = uploadStateRef.current;
    if (
      upload &&
      "ingestion_job_id" in upload &&
      upload.ingestion_job_id === targetJobId &&
      jobIsActive(upload.status)
    ) {
      const existingTimer = jobTimers.current.get(targetJobId);
      if (existingTimer) {
        clearTimeout(existingTimer);
        timers.current.delete(existingTimer);
        jobTimers.current.delete(targetJobId);
      }
      exhausted.current.delete(targetJobId);
      completed.current.delete(targetJobId);
      if (!inFlightPolls.current.has(targetJobId)) {
        polling.current.add(targetJobId);
        void poll(upload.document_id, targetJobId, controller, 0);
      }
    }
  }, [poll, pollingError]);

  useEffect(() => {
    const controller = scope.current;
    if (!controller || controller.signal.aborted) return;
    syncPollingError();
    for (const document of documents) {
      const jobId = document.ingestion_job_id;
      if (
        jobId &&
        derivationIsActive(document) &&
        !polling.current.has(jobId) &&
        !completed.current.has(jobId) &&
        !exhausted.current.has(jobId)
      ) {
        polling.current.add(jobId);
        void poll(document.document_id, jobId, controller);
      }
    }
  }, [documents, poll, syncPollingError]);

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
      reprocessConfiguration(document, "deployed") !== null &&
      !document.archived &&
      Boolean(
        document.current_document_version_id && document.reprocess_supported,
      ) &&
      !derivationIsActive(document) &&
      !derivationIsActive({
        ingestion_status: jobStates[document.document_id]?.status,
        indexing_status:
          "indexing_status" in (jobStates[document.document_id] ?? {})
            ? (jobStates[document.document_id] as IngestionJobStatusResponse)
                .indexing_status
            : null,
      }) &&
      !["requested", "processing", "succeeded"].includes(
        document.deletion_request?.state ?? "",
      )
    );
  }
  async function reprocess(document: DocumentResponse) {
    const controller = scope.current;
    const id = document.document_id;
    if (!controller || !canReprocess(document) || !begin(id)) return;
    setActionError(null);
    try {
      const response = await browserRequest(
        `${path}/document-versions/${encodeURIComponent(document.current_document_version_id!)}/reprocess`,
        {
          method: "POST",
          headers: { "Idempotency-Key": identity(reprocessKeys.current, id) },
          body: JSON.stringify(reprocessConfiguration(document, "deployed")),
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
          setActionError(
            response.status === 409
              ? "This document changed. Reload and try again."
              : errorMessage("re-index document", response.status),
          );
        return;
      }
      const result = (await response.json()) as ReprocessResponse;
      if (controller.signal.aborted) return;
      loadSeq.current++;
      lastAppliedSeq.current = loadSeq.current;
      setUploadState((current) =>
        current && "document_id" in current && current.document_id === id
          ? null
          : current,
      );
      reprocessKeys.current.delete(id);
      setDocuments((previous) =>
        previous.map((doc) =>
          doc.document_id === id
            ? {
                ...doc,
                ingestion_job_id: result.ingestion_job_id,
                ingestion_status: result.status,
              }
            : doc,
        ),
      );
      documentsRef.current = documentsRef.current.map((doc) =>
        doc.document_id === id
          ? {
              ...doc,
              ingestion_job_id: result.ingestion_job_id,
              ingestion_status: result.status,
            }
          : doc,
      );
      setJobStates((previous) => ({
        ...previous,
        [id]: { status: result.status },
      }));
      if (!jobIsActive(result.status)) await load(controller);
      else if (!polling.current.has(result.ingestion_job_id)) {
        completed.current.delete(result.ingestion_job_id);
        exhausted.current.delete(result.ingestion_job_id);
        polling.current.add(result.ingestion_job_id);
        void poll(id, result.ingestion_job_id, controller);
      }
    } catch {
      if (!controller.signal.aborted)
        setActionError(
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
    setActionError(null);
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
          setActionError("This document changed. Reload and try again.");
        return;
      }
      if (response.status !== 200) {
        setActionError(errorMessage("update document", response.status));
        return;
      }
      if (document.archived) router.push(routes.document(workspaceId, id));
      else await load(controller);
    } catch {
      if (!controller.signal.aborted)
        setActionError(
          "Unable to confirm the document change. Reload before retrying.",
        );
    } finally {
      finish(id, controller);
    }
  }
  async function restoreArchivedDocument(documentId: string) {
    const controller = scope.current;
    if (!controller || !canWrite || !begin(documentId)) return;
    setActionError(null);
    try {
      let doc = documents.find((d) => d.document_id === documentId);
      if (!doc) {
        const response = await browserRequest(
          `${path}/documents/${encodeURIComponent(documentId)}`,
          { signal: controller.signal },
        );
        if (response.ok) {
          doc = (await response.json()) as DocumentResponse;
        }
      }
      if (!doc) {
        setActionError("Unable to find document to restore.");
        return;
      }
      const response = await browserRequest(
        `${path}/documents/${encodeURIComponent(documentId)}/unarchive`,
        {
          method: "POST",
          headers: { "If-Match": String(doc.revision) },
          signal: controller.signal,
        },
      );
      if (controller.signal.aborted) return;
      if (response.status === 409) {
        await load(controller);
        if (!controller.signal.aborted)
          setActionError("This document changed. Reload and try again.");
        return;
      }
      if (!response.ok) {
        setActionError(errorMessage("restore document", response.status));
        return;
      }
      setUploadState((current) =>
        current?.document_id === documentId ? null : current,
      );
      await load(controller);
    } catch {
      if (!controller.signal.aborted)
        setActionError("Unable to restore document. Reload before retrying.");
    } finally {
      finish(documentId, controller);
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
      loadSeq.current++;
      lastAppliedSeq.current = loadSeq.current;
      setUploadState(result);
      if ("ingestion_job_id" in result && result.ingestion_job_id) {
        setDocuments((previous) =>
          previous.map((doc) =>
            doc.document_id === result.document_id
              ? {
                  ...doc,
                  ingestion_job_id: result.ingestion_job_id,
                  ingestion_status: result.status,
                }
              : doc,
          ),
        );
        documentsRef.current = documentsRef.current.map((doc) =>
          doc.document_id === result.document_id
            ? {
                ...doc,
                ingestion_job_id: result.ingestion_job_id,
                ingestion_status: result.status,
              }
            : doc,
        );
      }
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
        completed.current.delete(result.ingestion_job_id);
        exhausted.current.delete(result.ingestion_job_id);
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
  const visible = (documents ?? []).filter(
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
        {canWrite && !limitedPermissions ? (
          <Button
            className="h-[38px] min-h-[38px] w-[154px] shrink-0 !px-2.5 py-0 text-[13px]"
            onClick={() => setUploadOpen(true)}
          >
            <span aria-hidden="true" className="text-[15px]">
              +
            </span>
            Upload document
          </Button>
        ) : (
          <span className="rounded-lg bg-[color-mix(in_srgb,var(--signature)_10%,var(--surface))] px-3.5 py-2.5 text-[13px] font-semibold text-signature">
            {workspaceArchived ? "Read-only" : "Limited permissions"}
          </span>
        )}
      </header>
      {limitedPermissions && !workspaceArchived && (
        <p role="status" className="m-0 text-sm text-signature">
          You don&apos;t have permission to view documents in this workspace.
        </p>
      )}
      {workspaceArchived && (
        <p role="status" className="m-0 text-sm text-signature">
          This Workspace is read-only.
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <label className="kn-search-field flex h-10 w-full max-w-[430px] items-center gap-2 rounded-lg border border-border px-3 text-text-muted">
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
        <div role="status" className="m-0 flex flex-col gap-2">
          {uploadState.document_archived ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-status-warning/40 bg-[color-mix(in_srgb,var(--status-warning)_10%,var(--surface))] p-3.5 text-sm text-text-primary shadow-xs">
              <div className="flex items-center gap-2.5">
                <span
                  className="inline-flex size-2 shrink-0 rounded-full bg-status-warning"
                  aria-hidden="true"
                />
                <span className="font-medium">
                  This document already exists and is archived. Restore it to
                  use it again.
                </span>
              </div>
              {canWrite && (
                <Button
                  variant="primary"
                  className="h-8 px-3 text-xs"
                  disabled={busy.includes(uploadState.document_id)}
                  loading={busy.includes(uploadState.document_id)}
                  onClick={() =>
                    void restoreArchivedDocument(uploadState.document_id)
                  }
                >
                  Restore document
                </Button>
              )}
            </div>
          ) : (
            <p className="m-0 text-sm">
              Upload:{" "}
              {"status" in uploadState
                ? uploadState.status
                : uploadState.outcome}
              {"ingestion_job_id" in uploadState
                ? ` · job ${uploadState.ingestion_job_id}`
                : ""}
            </p>
          )}
        </div>
      )}
      {actionError && (
        <p role="alert" className="m-0 text-sm text-status-error">
          <span>{actionError}</span>
          {actionError.includes("session expired") && (
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
      {pollingError && (
        <p role="alert" className="m-0 text-sm text-status-error">
          <span>{pollingError}</span>
          <button
            type="button"
            className="ml-2 font-medium underline hover:text-action-text cursor-pointer bg-transparent border-0 p-0 text-inherit"
            onClick={retryPolling}
          >
            Retry
          </button>
          {pollingError.includes("session expired") && (
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
      {loading && <LeafLoading label="Loading documents" />}
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
                      indexing_status: observed.indexing_status,
                      lexical_readiness: observed.lexical_readiness,
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
                  document.lexical_readiness === "reindex_required" ||
                  document.indexing_status === "failed" ||
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
                        aria-label={`${document.ingestion_status === "failed" || document.indexing_status === "failed" ? "Try again" : "Re-index"} ${document.source_name}`}
                        disabled={busy.includes(document.document_id)}
                        loading={busy.includes(document.document_id)}
                        onClick={() => void reprocess(document)}
                      >
                        {document.ingestion_status === "failed" ||
                        document.indexing_status === "failed"
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
