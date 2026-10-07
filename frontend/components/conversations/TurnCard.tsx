"use client";
import React from "react";
import Link from "next/link";
import type { TurnResponse } from "@/generated/knora-openapi";
import { CitationViewer } from "@/components/citations/CitationViewer";
import { routes } from "@/lib/navigation/routes";
import type { EvidenceSelection } from "@/lib/conversations/panel-preferences";
export function processingLabel(stage: string | null) {
  switch (stage) {
    case "retrieving":
      return "Retrieving evidence…";
    case "selecting_evidence":
      return "Selecting evidence…";
    case "generating":
      return "Generating answer…";
    default:
      return "Processing question…";
  }
}
export function TurnCard({
  turn,
  workspaceId,
  selection,
  onSelect,
  onSuggest,
  onRetry,
  disabled = false,
  sessionExpired = false,
}: {
  turn: TurnResponse;
  workspaceId: string;
  selection: EvidenceSelection | null;
  onSelect: (selection: EvidenceSelection) => void;
  onSuggest: (draft: string) => void;
  onRetry: () => void;
  disabled?: boolean;
  sessionExpired?: boolean;
}) {
  const working = ["queued", "processing", "pending"].includes(turn.status);
  const interrupted = turn.status === "interrupted";
  const failed = turn.status === "failed" || Boolean(turn.error_code);
  const refused =
    !working && !interrupted && !failed && turn.result?.decision === "REFUSAL";
  const answer =
    !working && !interrupted && !failed && turn.result?.decision === "ANSWER"
      ? turn.result.answer
      : null;
  return (
    <li
      className="m-0 flex flex-col gap-[22px]"
      aria-label={`Question ${turn.sequence}`}
    >
      <div className="flex min-h-[52px] items-start justify-end">
        <p className="max-w-full whitespace-pre-wrap break-words rounded-2xl bg-text-primary px-3.5 py-2.5 text-sm font-medium leading-5 text-surface">
          {turn.question}
        </p>
      </div>
      <article className="m-0 flex flex-col gap-2.5 rounded-none border-0 bg-transparent p-0">
        {working && !sessionExpired && (
          <div
            role="status"
            className="flex h-12 items-center gap-2 text-sm leading-[22px]"
          >
            {turn.stage === null ? (
              <div className="h-12 w-[37px] shrink-0 overflow-hidden">
                <img
                  src="/icons/figma/5b324.svg"
                  alt=""
                  width={888}
                  height={48}
                  className="block h-12 w-[888px] max-w-none"
                />
              </div>
            ) : (
              <div aria-hidden="true" className="flex shrink-0 gap-2">
                <img src="/icons/figma/97a8a.svg" width={7} height={7} alt="" />
                <img src="/icons/figma/cd6f9.svg" width={7} height={7} alt="" />
                <img src="/icons/figma/832ce.svg" width={7} height={7} alt="" />
              </div>
            )}
            {processingLabel(turn.stage)}
          </div>
        )}
        {answer && (
          <p className="whitespace-pre-wrap break-words text-sm leading-[22px]">
            {answer}
          </p>
        )}
        {refused && (
          <>
            <h2 className="font-display text-2xl font-semibold leading-8">
              {turn.result?.refusal_reason === "INSUFFICIENT_EVIDENCE"
                ? "I don’t have enough evidence to answer that."
                : "I can’t answer that from the available evidence."}
            </h2>
            <p className="text-sm leading-[22px]">
              Refused: {turn.result?.refusal_reason}
            </p>
            <span className="m-0 w-fit rounded-full border border-signature bg-signature/10 px-2 py-1 text-[11px] text-signature">
              {turn.result?.refusal_reason === "INSUFFICIENT_EVIDENCE"
                ? "Insufficient evidence"
                : "Controlled refusal"}
            </span>
            <div className="flex flex-wrap gap-2">
              <Link
                href={routes.documents(workspaceId)}
                className="m-0 rounded-lg border border-border px-2.5 py-1.5 text-[11px]"
              >
                Review indexed documents
              </Link>
              <button
                disabled={disabled}
                type="button"
                onClick={() => onSuggest("Find supporting evidence")}
                className="m-0 rounded-lg border border-border px-2.5 py-1.5 text-[11px]"
              >
                Find supporting evidence
              </button>
            </div>
          </>
        )}
        {interrupted && (
          <>
            <h2 className="font-display text-2xl font-semibold leading-8">
              The answer was interrupted.
            </h2>
            <p className="text-sm leading-[22px]">
              Outcome uncertain. Reload history before retrying the same
              question.
            </p>
            <span className="m-0 w-fit rounded-full border border-signature bg-signature/10 px-2 py-1 text-[11px] text-signature">
              Interrupted
            </span>
          </>
        )}
        {failed && (
          <>
            <h2 className="font-display text-2xl font-semibold leading-8">
              System error
            </h2>
            <p role="alert" className="text-sm leading-[22px]">
              {turn.error_code ?? "This request could not be completed."}
            </p>
          </>
        )}
        {(interrupted || failed) && (
          <button
            type="button"
            disabled={disabled}
            onClick={onRetry}
            className="m-0 w-fit rounded-lg border border-action px-2.5 py-1.5 text-[11px] text-action-text disabled:opacity-50"
          >
            Try again
          </button>
        )}
        {!working && !interrupted && !failed && turn.result?.citations && (
          <CitationViewer
            citations={turn.result.citations}
            workspaceId={workspaceId}
            selectedIndex={
              selection?.turnId === turn.id ? selection.citationIndex : null
            }
            onSelect={(index) =>
              onSelect({ turnId: turn.id, citationIndex: index })
            }
          />
        )}
        {answer && (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={disabled}
              onClick={() => onSuggest("Find supporting evidence")}
              className="m-0 rounded-lg border border-border px-2.5 py-1.5 text-[11px]"
            >
              Find supporting evidence
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onSuggest("Compare the documents")}
              className="m-0 rounded-lg border border-border px-2.5 py-1.5 text-[11px]"
            >
              Compare the documents
            </button>
          </div>
        )}
      </article>
    </li>
  );
}
