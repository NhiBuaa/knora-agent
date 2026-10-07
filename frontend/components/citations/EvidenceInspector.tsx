"use client";
import React from "react";
import Link from "next/link";
import type { CitationResponse, TurnResponse } from "@/generated/knora-openapi";
import { routes } from "@/lib/navigation/routes";
import { processingLabel } from "@/components/conversations/TurnCard";
export function EvidenceInspector({
  workspaceId,
  citation,
  turn,
  workspaceArchived = false,
}: {
  workspaceId: string;
  citation?: CitationResponse | null;
  turn?: TurnResponse | null;
  workspaceArchived?: boolean;
}) {
  const working =
    turn && ["queued", "processing", "pending"].includes(turn.status);
  const interrupted = turn?.status === "interrupted";
  const failed = turn?.status === "failed" || Boolean(turn?.error_code);
  const refused = turn?.result?.decision === "REFUSAL";
  const insufficient =
    refused && turn?.result?.refusal_reason === "INSUFFICIENT_EVIDENCE";
  const retainedAnswerContext =
    workspaceArchived && !citation && turn?.result?.decision === "ANSWER";
  const heading = citation
    ? citation.source_name
    : working
      ? turn.stage === "retrieving"
        ? "Searching indexed documents"
        : "Processing question"
      : interrupted || failed
        ? "Evidence unavailable"
        : refused
          ? "No supporting citation"
          : turn?.result?.decision === "ANSWER"
            ? "Select a citation"
            : "Evidence will appear here";
  const label = citation
    ? citation.heading_path.join(" / ") || "Source excerpt"
    : working
      ? processingLabel(turn.stage).replace("…", "")
      : interrupted
        ? "ANSWER INTERRUPTED"
        : failed
          ? "SYSTEM ERROR"
          : insufficient
            ? "INSUFFICIENT EVIDENCE"
            : refused
              ? "CONTROLLED REFUSAL"
              : turn
                ? "VERIFY THE ANSWER"
                : "READY FOR VERIFICATION";
  const message = citation
    ? citation.excerpt
    : working
      ? "Evidence will be available when the server completes this question."
      : interrupted
        ? "No citation was produced because the answer did not complete."
        : failed
          ? "The request could not be completed. Reload history to check its status."
          : refused
            ? "Knora did not generate an unsupported answer."
            : turn
              ? "Choose a citation in the answer to inspect the exact supporting passage and its source context."
              : "When Knora uses a document to answer, the supporting passage will appear here for you to inspect.";
  return (
    <aside
      aria-label="Evidence Inspector"
      className="flex min-h-full flex-col bg-surface text-text-primary"
    >
      <header className="flex h-16 shrink-0 items-center px-[18px]">
        <h2 className="font-display text-base font-semibold">
          Evidence Inspector
        </h2>
      </header>
      <div className="flex flex-col gap-3.5 p-[18px]">
        <p className="text-[10px] font-semibold text-text-muted">
          {citation ? "SELECTED SOURCE" : "EVIDENCE"}
        </p>
        <h3 className="break-words text-sm font-semibold leading-5">
          {heading}
        </h3>
        {citation ? (
          <div className="flex flex-wrap gap-[7px] text-[11px] text-text-muted">
            {citation.page_start != null && (
              <span className="rounded-full border border-border bg-surface-subtle px-2 py-1">
                page {citation.page_start}
                {citation.page_end != null &&
                citation.page_end !== citation.page_start
                  ? `–${citation.page_end}`
                  : ""}
              </span>
            )}
            <span className="rounded-full border border-border bg-surface-subtle px-2 py-1">
              lines {citation.start_line}–{citation.end_line}
            </span>
          </div>
        ) : refused ? (
          <p className="w-fit rounded-full border border-border bg-surface-subtle px-2 py-1 text-[11px] text-text-muted">
            Available evidence reviewed
          </p>
        ) : null}
        <blockquote
          className={`m-0 flex flex-col gap-2 rounded-lg border border-border px-3.5 py-[13px] ${retainedAnswerContext ? "min-h-[96px] w-[340px] max-w-[calc(100%+2px)]" : "min-h-[146px]"} ${refused || interrupted ? "bg-signature/10" : "bg-surface-subtle"}`}
        >
          <p className="text-[10px] font-semibold uppercase text-text-muted">
            {label}
          </p>
          <p className="whitespace-pre-wrap break-words text-[13px] leading-5">
            {message}
          </p>
        </blockquote>
        {citation && (
          <>
            <Link
              href={routes.document(workspaceId, citation.document_id)}
              className="flex min-h-[34px] items-center justify-between rounded-lg border border-border px-3 text-xs font-medium"
            >
              <span>Open document</span>
              <span aria-hidden="true">↗</span>
            </Link>
            <p className="break-words text-[11px] text-text-muted">
              Historical document version:{" "}
              <span>{citation.document_version_id}</span>
            </p>
            <details className="text-xs">
              <summary className="cursor-pointer text-text-muted">
                Provenance
              </summary>
              <dl className="mt-3 grid grid-cols-[auto_1fr] gap-2 break-all">
                <dt>Evidence</dt>
                <dd>{citation.evidence_id}</dd>
                <dt>Source key</dt>
                <dd>{citation.source_key}</dd>
                <dt>Checksum</dt>
                <dd>{citation.content_checksum}</dd>
                <dt>Offsets</dt>
                <dd>
                  {citation.start_offset ?? "—"}–{citation.end_offset ?? "—"}
                </dd>
              </dl>
            </details>
          </>
        )}
        {workspaceArchived && (
          <div
            aria-label="Read-only Workspace notice"
            className="flex min-h-[82px] w-[340px] max-w-[calc(100%+2px)] shrink-0 flex-col gap-2 rounded-lg border border-border bg-surface-subtle px-3.5 py-[13px] min-[960px]:h-[82px]"
          >
            <p className="m-0 text-[10px] font-semibold leading-normal text-text-muted">
              READ-ONLY WORKSPACE
            </p>
            <p className="m-0 text-[13px] leading-5 text-text-primary">
              Workspace archived. Restore it to ask new questions or make
              changes.
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}
