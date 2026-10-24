"use client";
import React from "react";
import Link from "next/link";
import type { TurnResponse } from "@/generated/knora-openapi";
import { CitationViewer } from "@/components/citations/CitationViewer";
import { routes } from "@/lib/navigation/routes";
import type { EvidenceSelection } from "@/lib/conversations/panel-preferences";
import { isVietnameseQuestion } from "@/lib/conversations/question-language";
import { copyableAnswerMarkdown } from "@/lib/conversations/message-copy";
import { AnswerContent } from "./AnswerContent";

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

type CopyState = "idle" | "copying" | "copied" | "error";

function CopyIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </svg>
  );
}

function CheckIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function AlertIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

interface CopyButtonProps {
  label: string;
  state: CopyState;
  vietnamese: boolean;
  onClick: () => void;
}

function CopyButton({ label, state, vietnamese, onClick }: CopyButtonProps) {
  const statusText =
    state === "copied"
      ? vietnamese
        ? "Đã sao chép"
        : "Copied"
      : state === "error"
        ? vietnamese
          ? "Không thể sao chép"
          : "Copy failed"
        : vietnamese
          ? "Sao chép"
          : "Copy";

  return (
    <button
      type="button"
      title={statusText}
      aria-label={label}
      disabled={state === "copying"}
      onClick={onClick}
      className="m-0 inline-flex h-7 w-7 items-center justify-center rounded-md border border-border bg-surface text-text-muted transition-colors hover:border-action hover:text-text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-action disabled:opacity-50"
    >
      {state === "copied" ? (
        <CheckIcon className="h-3.5 w-3.5 text-action" />
      ) : state === "error" ? (
        <AlertIcon className="h-3.5 w-3.5 text-signature" />
      ) : (
        <CopyIcon className="h-3.5 w-3.5" />
      )}
      <span className="sr-only">{statusText}</span>
    </button>
  );
}

export function TurnCard({
  turn,
  workspaceId,
  selection,
  onSelect,
  onRetry,
  disabled = false,
  sessionExpired = false,
}: {
  turn: TurnResponse;
  workspaceId: string;
  selection: EvidenceSelection | null;
  onSelect: (selection: EvidenceSelection) => void;
  onRetry: () => void;
  disabled?: boolean;
  sessionExpired?: boolean;
}) {
  const vietnamese = isVietnameseQuestion(turn.question);
  const working = ["queued", "processing", "pending"].includes(turn.status);
  const interrupted = turn.status === "interrupted";
  const failed =
    !interrupted && (turn.status === "failed" || Boolean(turn.error_code));
  const refused =
    !working && !interrupted && !failed && turn.result?.decision === "REFUSAL";
  const answer =
    !working && !interrupted && !failed && turn.result?.decision === "ANSWER"
      ? turn.result.answer
      : null;

  const [questionCopyState, setQuestionCopyState] = React.useState<
    "idle" | "copying" | "copied" | "error"
  >("idle");
  const [answerCopyState, setAnswerCopyState] = React.useState<
    "idle" | "copying" | "copied" | "error"
  >("idle");
  const questionTimerRef = React.useRef<NodeJS.Timeout | null>(null);
  const answerTimerRef = React.useRef<NodeJS.Timeout | null>(null);

  React.useEffect(() => {
    return () => {
      if (questionTimerRef.current) clearTimeout(questionTimerRef.current);
      if (answerTimerRef.current) clearTimeout(answerTimerRef.current);
    };
  }, []);

  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const copyableAnswer = answer
    ? copyableAnswerMarkdown(
        answer,
        turn.result?.citations ?? [],
        workspaceId,
        origin,
      )
    : null;

  const refusalText = refused
    ? turn.result?.refusal_reason === "INSUFFICIENT_EVIDENCE"
      ? vietnamese
        ? "Tôi chưa có đủ bằng chứng để trả lời câu hỏi này."
        : "I don’t have enough evidence to answer that."
      : vietnamese
        ? "Tôi không thể trả lời câu hỏi này dựa trên bằng chứng hiện có."
        : "I can’t answer that from the available evidence."
    : null;

  async function handleCopyQuestion() {
    if (questionCopyState === "copying") return;
    if (questionTimerRef.current) {
      clearTimeout(questionTimerRef.current);
      questionTimerRef.current = null;
    }
    setQuestionCopyState("copying");
    try {
      if (!navigator?.clipboard?.writeText) {
        throw new Error("Clipboard API unavailable");
      }
      await navigator.clipboard.writeText(turn.question);
      setQuestionCopyState("copied");
      questionTimerRef.current = setTimeout(() => {
        setQuestionCopyState("idle");
      }, 2000);
    } catch {
      setQuestionCopyState("error");
      questionTimerRef.current = setTimeout(() => {
        setQuestionCopyState("idle");
      }, 3000);
    }
  }

  async function handleCopyAnswer(content: string) {
    if (answerCopyState === "copying") return;
    if (answerTimerRef.current) {
      clearTimeout(answerTimerRef.current);
      answerTimerRef.current = null;
    }
    setAnswerCopyState("copying");
    try {
      if (!navigator?.clipboard?.writeText) {
        throw new Error("Clipboard API unavailable");
      }
      await navigator.clipboard.writeText(content);
      setAnswerCopyState("copied");
      answerTimerRef.current = setTimeout(() => {
        setAnswerCopyState("idle");
      }, 2000);
    } catch {
      setAnswerCopyState("error");
      answerTimerRef.current = setTimeout(() => {
        setAnswerCopyState("idle");
      }, 3000);
    }
  }

  return (
    <li
      className="m-0 flex flex-col gap-[22px]"
      aria-label={`Question ${turn.sequence}`}
    >
      <div className="flex min-h-[52px] flex-col items-end gap-1.5">
        <p className="max-w-full whitespace-pre-wrap break-words rounded-2xl bg-text-primary px-3.5 py-2.5 text-sm font-medium leading-5 text-surface">
          {turn.question}
        </p>
        <CopyButton
          label={
            vietnamese
              ? `Sao chép câu hỏi ${turn.sequence}`
              : `Copy question ${turn.sequence}`
          }
          state={questionCopyState}
          vietnamese={vietnamese}
          onClick={handleCopyQuestion}
        />
      </div>
      <article className="m-0 flex flex-col gap-2.5 rounded-none border-0 bg-transparent p-0">
        {working && !sessionExpired && (
          <div
            role="status"
            className="flex h-12 items-center gap-2 text-sm leading-[22px]"
          >
            <div
              aria-hidden="true"
              className="kn-processing-dots flex shrink-0 gap-2"
            >
              <span />
              <span />
              <span />
            </div>
            {processingLabel(turn.stage)}
          </div>
        )}
        {answer && (
          <>
            <AnswerContent
              answer={answer}
              citations={turn.result?.citations ?? []}
              selectedIndex={
                selection?.turnId === turn.id ? selection.citationIndex : null
              }
              onSelect={(index) =>
                onSelect({ turnId: turn.id, citationIndex: index })
              }
            />
            {copyableAnswer !== null && (
              <div className="flex items-center gap-2">
                <CopyButton
                  label={
                    vietnamese
                      ? `Sao chép câu trả lời ${turn.sequence}`
                      : `Copy answer ${turn.sequence}`
                  }
                  state={answerCopyState}
                  vietnamese={vietnamese}
                  onClick={() => handleCopyAnswer(copyableAnswer)}
                />
              </div>
            )}
          </>
        )}
        {refused && (
          <>
            <h2 className="font-display text-2xl font-semibold leading-8">
              {refusalText}
            </h2>
            {refusalText && (
              <div className="flex items-center gap-2">
                <CopyButton
                  label={
                    vietnamese
                      ? `Sao chép câu trả lời ${turn.sequence}`
                      : `Copy answer ${turn.sequence}`
                  }
                  state={answerCopyState}
                  vietnamese={vietnamese}
                  onClick={() => handleCopyAnswer(refusalText)}
                />
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <span className="m-0 w-fit rounded-full border border-signature bg-signature/10 px-2 py-1 text-[11px] text-signature">
                {turn.result?.refusal_reason === "INSUFFICIENT_EVIDENCE"
                  ? vietnamese
                    ? "Chưa đủ bằng chứng"
                    : "Insufficient evidence"
                  : vietnamese
                    ? "Từ chối có kiểm soát"
                    : "Controlled refusal"}
              </span>
              <p className="m-0 text-xs text-text-muted">
                {vietnamese ? "Lý do từ chối" : "Refused"}:{" "}
                {turn.result?.refusal_reason}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                href={routes.documents(workspaceId)}
                className="kn-turn-action m-0 rounded-lg border border-border px-2.5 py-1.5 text-[11px] hover:bg-surface-subtle"
              >
                {vietnamese
                  ? "Xem tài liệu đã lập chỉ mục"
                  : "Review indexed documents"}
              </Link>
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
            className="kn-turn-action m-0 w-fit rounded-lg border border-action px-2.5 py-1.5 text-[11px] text-action-text disabled:opacity-50"
          >
            Try again
          </button>
        )}
        {!working &&
          !interrupted &&
          !failed &&
          !answer?.includes("[[") &&
          turn.result?.citations && (
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
      </article>
    </li>
  );
}
