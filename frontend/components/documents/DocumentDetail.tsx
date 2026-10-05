"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import type {
  DocumentDeletionRequestResponse,
  DocumentResponse,
  IngestionJobStatusResponse,
  ReprocessResponse,
} from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { routes } from "@/lib/navigation/routes";
import {
  answerAvailability,
  documentStatus,
  jobIsActive,
  lastProcessed,
  servingExplanation,
  sourceKind,
  statusClasses,
} from "@/lib/documents/presentation";
import { Button } from "@/components/ui/Button";
import { DeletionRequestDialog } from "./DeletionRequestDialog";
import "./documents.css";

type Props = {
  workspaceId: string;
  documentId: string;
  capabilities?: string[];
  workspaceArchived?: boolean;
};
function responseError(action: string, status: number) {
  return status === 401
    ? "Your session expired. Sign in again to continue."
    : `Unable to ${action} (${status})`;
}

export function DocumentDetail({
  workspaceId,
  documentId,
  capabilities = [],
  workspaceArchived = false,
}: Props) {
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<IngestionJobStatusResponse | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [deletionError, setDeletionError] = useState<string | null>(null);
  const [confirmDeletion, setConfirmDeletion] = useState(false);
  const [busy, setBusy] = useState(false);
  const scope = useRef<AbortController | null>(null);
  const mutation = useRef(false);
  const deletionKey = useRef<string | null>(null);
  const reprocessKey = useRef<string | null>(null);
  const path = `/v1/workspaces/${encodeURIComponent(workspaceId)}`;
  const documentPath = `${path}/documents/${encodeURIComponent(documentId)}`;
  const canDelete =
    capabilities.includes("documents:delete") && !workspaceArchived;
  const canWrite =
    capabilities.includes("documents:write") && !workspaceArchived;

  const load = useCallback(
    async (controller: AbortController) => {
      try {
        const response = await browserRequest(documentPath, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (!response.ok) {
          setError(responseError("load document", response.status));
          return;
        }
        const loaded = (await response.json()) as DocumentResponse;
        if (controller.signal.aborted) return;
        setDocument(loaded);
        if (loaded.ingestion_job_id && jobIsActive(loaded.ingestion_status))
          setJobId(loaded.ingestion_job_id);
        else setJobId(null);
      } catch {
        if (!controller.signal.aborted)
          setError("Unable to load document. Reload to try again.");
      }
    },
    [documentPath],
  );

  useEffect(() => {
    const controller = new AbortController();
    scope.current = controller;
    setDocument(null);
    setJobId(null);
    setJobStatus(null);
    setError(null);
    setDeletionError(null);
    setConfirmDeletion(false);
    setBusy(false);
    mutation.current = false;
    deletionKey.current = null;
    reprocessKey.current = null;
    void load(controller);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    const controller = scope.current;
    if (!jobId || !controller || controller.signal.aborted) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const response = await browserRequest(
          `${path}/ingestion-jobs/${encodeURIComponent(jobId)}`,
          { signal: controller.signal },
        );
        if (!active || controller.signal.aborted) return;
        if (!response.ok) {
          setError(responseError("load ingestion job", response.status));
          return;
        }
        const status = (await response.json()) as IngestionJobStatusResponse;
        if (!active || controller.signal.aborted) return;
        setJobStatus(status);
        if (jobIsActive(status.status))
          timer = setTimeout(
            () => void poll(),
            Math.max(1000, (status.poll_after_seconds || 2) * 1000),
          );
        else await load(controller);
      } catch {
        if (active && !controller.signal.aborted)
          setError(
            "Unable to load ingestion job. Reload to see the latest state.",
          );
      }
    };
    void poll();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [path, jobId, load]);

  function begin() {
    if (mutation.current) return false;
    mutation.current = true;
    setBusy(true);
    return true;
  }
  function finish(controller: AbortController) {
    if (controller.signal.aborted) return;
    mutation.current = false;
    setBusy(false);
  }
  async function requestDeletion() {
    const controller = scope.current;
    if (!controller || !document || !canDelete || !begin()) return;
    setDeletionError(null);
    setError(null);
    try {
      if (!deletionKey.current) deletionKey.current = crypto.randomUUID();
      const response = await browserRequest(
        `${documentPath}/deletion-request`,
        {
          method: "POST",
          headers: { "Idempotency-Key": deletionKey.current },
          signal: controller.signal,
        },
      );
      if (controller.signal.aborted) return;
      if (!response.ok) {
        setDeletionError(
          response.status === 403
            ? "Deletion requests require documents:delete access."
            : responseError("request deletion", response.status),
        );
        return;
      }
      const deletion =
        (await response.json()) as DocumentDeletionRequestResponse;
      if (controller.signal.aborted) return;
      setDocument((previous) =>
        previous ? { ...previous, deletion_request: deletion } : previous,
      );
      deletionKey.current = null;
      setConfirmDeletion(false);
      // The response carries the request outcome only. Answer availability stays
      // on the authoritative Document projection, never inferred from this request.
    } catch {
      if (!controller.signal.aborted)
        setDeletionError(
          "Unable to confirm deletion submission. Retry with the same request key.",
        );
    } finally {
      finish(controller);
    }
  }
  async function reprocess() {
    const controller = scope.current;
    if (
      !controller ||
      !document?.current_document_version_id ||
      !document.reprocess_supported ||
      !canWrite ||
      document.archived ||
      jobIsActive(jobStatus?.status ?? document.ingestion_status) ||
      !begin()
    )
      return;
    setError(null);
    try {
      if (!reprocessKey.current) reprocessKey.current = crypto.randomUUID();
      const response = await browserRequest(
        `${path}/document-versions/${encodeURIComponent(document.current_document_version_id)}/reprocess`,
        {
          method: "POST",
          headers: { "Idempotency-Key": reprocessKey.current },
          body: JSON.stringify({ config_mode: "current" }),
          signal: controller.signal,
        },
      );
      if (controller.signal.aborted) return;
      if (!response.ok) {
        if (response.status === 409) {
          reprocessKey.current = null;
          await load(controller);
        }
        if (!controller.signal.aborted)
          setError(
            response.status === 409
              ? "This document changed. Reload and try again."
              : responseError("reprocess document", response.status),
          );
        return;
      }
      const result = (await response.json()) as ReprocessResponse;
      if (controller.signal.aborted) return;
      reprocessKey.current = null;
      setJobStatus(null);
      setJobId(result.ingestion_job_id);
    } catch {
      if (!controller.signal.aborted)
        setError(
          "Unable to confirm reprocess submission. Retry with the same request key.",
        );
    } finally {
      finish(controller);
    }
  }
  async function archive() {
    const controller = scope.current;
    if (!controller || !document || !canWrite || !begin()) return;
    setError(null);
    try {
      const response = await browserRequest(
        `${documentPath}/${document.archived ? "unarchive" : "archive"}`,
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
        setError(responseError("update document", response.status));
        return;
      }
      const changed = (await response.json()) as DocumentResponse;
      if (!controller.signal.aborted) setDocument(changed);
    } catch {
      if (!controller.signal.aborted)
        setError(
          "Unable to confirm the document change. Reload before retrying.",
        );
    } finally {
      finish(controller);
    }
  }
  if (!document)
    return error ? (
      <p role="alert">
        {error}
        {error.includes("session expired") && (
          <>
            {" "}
            <a href="/api/auth/login" target="_blank" rel="noopener noreferrer">
              Sign in
            </a>
          </>
        )}
      </p>
    ) : (
      <p>Loading document…</p>
    );
  const observed =
    jobStatus && jobId
      ? {
          ...document,
          ingestion_status: jobStatus.status,
          serving_state: jobStatus.serving_state ?? document.serving_state,
          served_document_version_id:
            jobStatus.served_document_version_id === undefined
              ? document.served_document_version_id
              : jobStatus.served_document_version_id,
          current_document_version_id:
            jobStatus.current_document_version_id === undefined
              ? document.current_document_version_id
              : jobStatus.current_document_version_id,
        }
      : document;
  const status = documentStatus(observed);
  const kind = sourceKind(document.source_name);
  const serving = servingExplanation(observed);
  const deletion = document.deletion_request;
  const pendingDeletion =
    deletion?.state === "requested" ||
    deletion?.state === "processing" ||
    deletion?.state === "succeeded";
  const available = answerAvailability(document);
  const sourceSummary = document.archived
    ? "Archived — not used for grounded answers"
    : pendingDeletion && document.answer_availability === "unavailable"
      ? `${status.label} — not used for grounded answers`
      : document.answer_availability === "available"
        ? "Available for new answers in this workspace"
        : document.answer_availability === "unavailable"
          ? "Not available for new answers in this workspace"
          : "Answer availability unavailable";
  const actionClass =
    "h-[42px] min-h-[42px] w-full rounded-[7px] bg-surface py-0 text-sm font-medium";
  return (
    <article className="m-0 flex min-w-0 flex-col gap-6 rounded-none border-0 bg-transparent p-0 text-text-primary">
      <Link
        href={routes.documents(workspaceId)}
        className="w-fit text-sm leading-5 font-medium text-action-text no-underline"
      >
        ← Documents
      </Link>
      <header className="flex min-h-[92px] items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[30px] leading-[38px] font-semibold [overflow-wrap:anywhere]">
            {document.source_name}
          </h1>
          <p className="m-0 text-sm leading-[19px] text-text-muted">
            {kind.label} source · {sourceSummary}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full px-[9px] py-1 text-[11px] leading-[13px] font-medium ${statusClasses[status.tone]}`}
        >
          {status.label}
        </span>
      </header>
      <div className="h-px bg-border" />
      {workspaceArchived && (
        <p role="status" className="m-0 text-sm text-signature">
          This Workspace is read-only.
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
      <div className="grid min-w-0 gap-8 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-10">
        <div className="min-w-0">
          <section
            aria-label="Overview"
            className="m-0 rounded-none border-0 bg-transparent p-0"
          >
            <h2 className="m-0 mb-3 font-display text-lg leading-[25px] font-semibold">
              Overview
            </h2>
            <dl className="m-0 block border-t border-control-border text-sm [&>div]:grid [&>div]:min-h-12 [&>div]:grid-cols-[minmax(100px,210px)_minmax(0,1fr)] [&>div]:items-center [&>div]:gap-0 [&>div]:border-b [&>div]:border-border [&>div]:py-2 [&_dt]:font-normal [&_dt]:text-text-muted [&_dd]:m-0 [&_dd]:[overflow-wrap:anywhere]">
              <div>
                <dt>Status</dt>
                <dd
                  className={
                    status.tone === "success"
                      ? "flex items-center gap-2 text-action-text"
                      : status.tone === "normal"
                        ? "text-text-primary"
                        : "text-signature"
                  }
                >
                  {status.tone === "success" && (
                    <>
                      {/* eslint-disable-next-line @next/next/no-img-element -- Exact original Ready-detail status dot at 7×7. */}
                      <img
                        alt=""
                        src="/icons/figma/97a8a.svg"
                        width={7}
                        height={7}
                        className="size-[7px] shrink-0"
                      />
                    </>
                  )}
                  {status.label}
                </dd>
              </div>
              <div>
                <dt>Available for new answers</dt>
                <dd className="font-medium">{available}</dd>
              </div>
              <div>
                <dt>Source version</dt>
                <dd>
                  <span className="block">
                    Current:{" "}
                    {observed.current_document_version_id ?? "Unavailable"}
                  </span>
                  {observed.serving_state === "previous" && (
                    <span className="block">
                      Previous served:{" "}
                      {observed.served_document_version_id ?? "Unavailable"}
                    </span>
                  )}
                  {observed.serving_state === "current" && (
                    <span className="block text-xs text-text-muted">
                      Served:{" "}
                      {observed.served_document_version_id ?? "Unavailable"}
                    </span>
                  )}
                  {observed.serving_state === "unavailable" && (
                    <span className="block text-xs text-text-muted">
                      Served version: Unavailable
                    </span>
                  )}
                </dd>
              </div>
              <div>
                <dt>Last processed</dt>
                <dd>
                  {lastProcessed(
                    observed.served_document_version_id ===
                      document.served_document_version_id
                      ? document.last_processed_at
                      : null,
                  )}
                </dd>
              </div>
            </dl>
            {serving && (
              <p
                role="status"
                className="mt-3 mb-0 text-sm text-text-muted [overflow-wrap:anywhere]"
              >
                {serving}
              </p>
            )}
            {jobStatus?.failure_reason && (
              <p role="alert" className="mt-3 mb-0 text-sm text-signature">
                Ingestion failure: {jobStatus.failure_reason}
              </p>
            )}
            {jobStatus?.status === "retry_scheduled" &&
              jobStatus.next_attempt_at && (
                <p className="mt-3 mb-0 text-sm text-text-muted">
                  Next attempt: {jobStatus.next_attempt_at}
                </p>
              )}
          </section>
          <section
            aria-label="Source"
            className="m-0 mt-[34px] rounded-none border-0 bg-transparent p-0"
          >
            <h2 className="m-0 mb-3 font-display text-lg leading-[25px] font-semibold">
              Source
            </h2>
            <div className="flex min-h-[72px] items-center gap-3 border-y border-border">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-md border border-border bg-surface-subtle text-[10px] font-semibold text-text-muted">
                {kind.marker}
              </span>
              <Link
                className="text-sm leading-[18px] font-medium text-text-primary no-underline [overflow-wrap:anywhere]"
                href={routes.document(workspaceId, documentId)}
              >
                {document.source_name}
              </Link>
            </div>
            <details className="mt-3 text-xs text-text-muted">
              <summary className="cursor-pointer">Source details</summary>
              <dl className="mt-2 grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1 [&_dd]:[overflow-wrap:anywhere]">
                <dt>Source key</dt>
                <dd>{document.source_key}</dd>
                <dt>Revision</dt>
                <dd>{document.revision}</dd>
                <dt>Ingestion</dt>
                <dd>
                  {jobStatus?.status ??
                    document.ingestion_status ??
                    "Unavailable"}
                </dd>
                {jobId && (
                  <>
                    <dt>Ingestion job</dt>
                    <dd>{jobId}</dd>
                  </>
                )}
              </dl>
            </details>
          </section>
        </div>
        <aside className="min-w-0 border-t border-border pt-6 lg:border-t-0 lg:border-l-2 lg:pt-0 lg:pl-10">
          {pendingDeletion ? (
            <section
              aria-label="Deletion request"
              className="m-0 rounded-none border-0 bg-transparent p-0"
            >
              <h2 className="m-0 mb-3 border-b border-control-border pb-3 font-display text-lg leading-[25px] font-semibold">
                Deletion request
              </h2>
              <div className="mt-[18px] rounded-lg border border-border bg-[color-mix(in_srgb,var(--signature)_10%,var(--surface))] p-4">
                <p className="m-0 mb-2 text-[13px] font-semibold text-signature">
                  {status.label}
                </p>
                <p className="m-0 text-xs leading-[17px] text-text-muted">
                  {deletion?.state === "succeeded"
                    ? "The backend reports that this deletion request succeeded."
                    : "What happens next is governed by the deletion policy. This request is pending."}
                </p>
                {status.detail && (
                  <p className="mt-2 mb-0 text-xs text-signature">
                    {status.detail}
                  </p>
                )}
              </div>
            </section>
          ) : (
            <>
              <h2 className="m-0 mb-[18px] border-b border-control-border pb-3 font-display text-lg leading-[25px] font-semibold">
                Actions
              </h2>
              {canWrite &&
                !document.archived &&
                document.reprocess_supported &&
                document.current_document_version_id && (
                  <div className="mb-5">
                    <Button
                      variant="secondary"
                      className={`${actionClass} !border-action !text-action-text`}
                      disabled={
                        busy ||
                        jobIsActive(
                          jobStatus?.status ?? document.ingestion_status,
                        )
                      }
                      onClick={() => void reprocess()}
                    >
                      <span aria-hidden="true">↻</span>Reprocess document
                    </Button>
                    <p className="mt-2 mb-0 text-xs leading-[17px] text-text-muted">
                      Process the current source again.
                    </p>
                  </div>
                )}
              {canWrite && (
                <div>
                  <Button
                    variant="secondary"
                    className={`${actionClass} ${document.archived ? "!border-action !text-action-text" : "border-control-border"}`}
                    disabled={busy}
                    onClick={() => void archive()}
                  >
                    {document.archived
                      ? "Restore document"
                      : "Archive document"}
                  </Button>
                  <p className="mt-2 mb-0 text-xs leading-[17px] text-text-muted">
                    {document.archived
                      ? "Return this document to normal use in this workspace."
                      : "Hide this document from normal use. You can restore it later."}
                  </p>
                </div>
              )}
              {!canWrite && (
                <p className="m-0 text-sm text-text-muted">
                  View only. Management actions are unavailable with your
                  current access.
                </p>
              )}
              <section
                aria-label="Deletion request"
                className="m-0 mt-[34px] rounded-none border-0 border-t border-border bg-transparent px-0 pt-[22px] pb-0"
              >
                <h3 className="m-0 mb-2 font-sans text-[13px] leading-[18px] font-semibold text-signature">
                  Deletion
                </h3>
                {deletion && (
                  <>
                    <p className="m-0 mb-2 text-[13px] font-semibold text-signature">
                      {status.label}
                    </p>
                    {status.detail && (
                      <p className="m-0 mb-3 text-xs leading-[17px] text-signature">
                        {status.detail}
                      </p>
                    )}
                  </>
                )}
                <p className="m-0 mb-3.5 text-xs leading-[17px] text-text-muted">
                  Removal is handled as a request, not an immediate delete.
                </p>
                {canDelete && (
                  <Button
                    variant="secondary"
                    className={`${actionClass} h-10 min-h-10 border-signature text-signature`}
                    disabled={busy}
                    onClick={() => {
                      setDeletionError(null);
                      setConfirmDeletion(true);
                    }}
                  >
                    Request deletion
                  </Button>
                )}
              </section>
            </>
          )}
        </aside>
      </div>
      <DeletionRequestDialog
        document={confirmDeletion ? document : null}
        busy={busy}
        error={deletionError}
        onClose={() => {
          if (!mutation.current) setConfirmDeletion(false);
        }}
        onConfirm={() => void requestDeletion()}
      />
    </article>
  );
}
