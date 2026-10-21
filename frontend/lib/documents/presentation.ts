import type {
  DocumentResponse,
  ReprocessRequest,
} from "@/generated/knora-openapi";

export type DocumentStatusView = {
  label: string;
  tone: "normal" | "success" | "warning" | "error";
  detail: string | null;
};

export function jobIsActive(status: string | null | undefined) {
  return (
    status === "queued" ||
    status === "processing" ||
    status === "retry_scheduled"
  );
}

export function derivationIsActive(document: {
  ingestion_status?: string | null;
  indexing_status?: string | null;
}) {
  return (
    jobIsActive(document.ingestion_status) ||
    jobIsActive(document.indexing_status)
  );
}

export function reprocessConfiguration(
  document: DocumentResponse,
  denseMode: "current" | "deployed",
): ReprocessRequest | null {
  if (document.derivation_kind !== "pdf_extraction")
    return { config_mode: denseMode };
  if (document.desired_lexical_generation_id) return { config_mode: "current" };
  return document.ingestion_job_id
    ? {
        config_mode: "same_as_job",
        config_source_job_id: document.ingestion_job_id,
      }
    : null;
}

export function deletionReason(reason: string | null | undefined) {
  return reason === "DOCUMENT_DELETION_POLICY_UNAVAILABLE"
    ? "Deletion policy unavailable. The request is blocked; the document has not been deleted."
    : (reason ?? null);
}

export function documentStatus(document: DocumentResponse): DocumentStatusView {
  const deletion = document.deletion_request;
  if (deletion) {
    const labels = {
      requested: "Deletion requested",
      blocked: "Deletion blocked",
      processing: "Deletion processing",
      succeeded: "Deletion succeeded",
      failed: "Deletion failed",
    } as const;
    return {
      label: labels[deletion.state],
      tone: deletion.state === "failed" ? "error" : "warning",
      detail: deletionReason(deletion.failure_reason),
    };
  }
  if (document.archived)
    return { label: "Archived", tone: "warning", detail: null };
  if (document.ingestion_status === "failed")
    return { label: "Processing failed", tone: "error", detail: null };
  if (document.ingestion_status === "queued")
    return { label: "Queued", tone: "normal", detail: null };
  if (document.ingestion_status === "processing")
    return { label: "Processing…", tone: "normal", detail: null };
  if (document.ingestion_status === "retry_scheduled")
    return { label: "Retry scheduled", tone: "normal", detail: null };
  if (document.indexing_status === "failed")
    return { label: "Indexing failed", tone: "error", detail: null };
  if (document.indexing_status === "queued")
    return { label: "Index queued", tone: "normal", detail: null };
  if (document.indexing_status === "processing")
    return { label: "Indexing…", tone: "normal", detail: null };
  if (document.indexing_status === "retry_scheduled")
    return { label: "Index retry scheduled", tone: "normal", detail: null };
  if (document.lexical_readiness === "reindex_required")
    return { label: "Needs re-index", tone: "warning", detail: null };
  if (document.lexical_readiness === "ready")
    return { label: "Ready", tone: "success", detail: null };
  if (document.embedding_readiness === "reindex_required")
    return { label: "Needs re-index", tone: "warning", detail: null };
  if (document.embedding_readiness === "ready")
    return { label: "Ready", tone: "success", detail: null };
  if (document.embedding_readiness === "not_indexed")
    return { label: "Not indexed", tone: "normal", detail: null };
  return { label: "Unavailable", tone: "normal", detail: null };
}

export function servingExplanation(document: DocumentResponse) {
  if (document.serving_state === "previous")
    return `Previous version still served${document.served_document_version_id ? `: ${document.served_document_version_id}` : " (version unavailable)"}.`;
  if (document.serving_state === "unavailable")
    return "No source version is currently served.";
  return null;
}

export function answerAvailability(document: DocumentResponse) {
  if (document.answer_availability === "available") return "Yes";
  if (document.answer_availability === "unavailable") return "No";
  return "Unavailable";
}

export function sourceKind(name: string) {
  const extension = name.split(".").pop()?.toLowerCase();
  if (extension === "pdf") return { marker: "PDF", label: "PDF" };
  if (extension === "md" || extension === "markdown")
    return { marker: "MD", label: "Markdown" };
  if (extension === "txt" || extension === "text")
    return { marker: "TXT", label: "Text" };
  return { marker: "FILE", label: "Document" };
}

export function lastProcessed(value: string | null | undefined) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return `${new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(date)} · ${new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" }).format(date)}`;
}

export const statusClasses = {
  normal: "bg-surface-subtle text-text-muted",
  success:
    "bg-[color-mix(in_srgb,var(--action)_12%,var(--surface))] text-action-text",
  warning:
    "bg-[color-mix(in_srgb,var(--signature)_10%,var(--surface))] text-signature",
  error:
    "bg-[color-mix(in_srgb,var(--signature)_8%,var(--surface))] text-signature",
} as const;
