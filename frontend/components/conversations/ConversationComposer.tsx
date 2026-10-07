"use client";
import React, { type FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { WorkspaceResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import { resolveWorkspaceAfterMutation } from "@/components/workspaces/ArchiveWorkspaceDialog";

/** Archive state remains authoritative until the destination reloads its Workspace. */
export function WorkspaceReadOnlyComposer({
  workspaceId,
  workspaceRevision,
  sessionExpired = false,
  onAuthenticationRequired,
}: {
  workspaceId: string;
  workspaceRevision?: number;
  sessionExpired?: boolean;
  onAuthenticationRequired?: () => void;
}) {
  const router = useRouter();
  const active = useRef(true);
  const expired = useRef(sessionExpired);
  expired.current = sessionExpired;
  const inFlight = useRef(false);
  const restored = useRef(false);
  const [busy, setBusy] = useState(false);
  const [authenticationRequired, setAuthenticationRequired] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const validRevision =
    Number.isSafeInteger(workspaceRevision) && workspaceRevision! >= 0;
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  async function restore() {
    if (
      !validRevision ||
      sessionExpired ||
      authenticationRequired ||
      inFlight.current ||
      restored.current
    )
      return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/restore`,
        {
          method: "POST",
          headers: { "If-Match": String(workspaceRevision) },
        },
      );
      if (!active.current || expired.current) return;
      if (response.status === 401) {
        setAuthenticationRequired(true);
        onAuthenticationRequired?.();
        setError(
          "Your session has expired. Sign in again, then reload this page.",
        );
        return;
      }
      if (!response.ok) throw new Error("restore failed");
      const updated = (await response.json()) as WorkspaceResponse;
      if (!active.current || expired.current) return;
      if (
        updated.id !== workspaceId ||
        updated.archived !== false ||
        !Number.isSafeInteger(updated.revision) ||
        updated.revision <= workspaceRevision!
      )
        throw new Error("invalid restore projection");
      restored.current = true;
      const destination = await resolveWorkspaceAfterMutation(workspaceId);
      if (active.current && !expired.current) router.push(destination);
    } catch {
      if (active.current)
        setError(
          restored.current
            ? "Workspace restored. Reload to select an active Workspace."
            : "Unable to restore Workspace. Reload and retry.",
        );
    } finally {
      inFlight.current = false;
      if (active.current) setBusy(false);
    }
  }
  return (
    <div
      aria-label="Archived workspace controls"
      className="flex min-h-[72px] flex-wrap items-center justify-between gap-2 border-t border-border bg-surface px-4 py-3 min-[960px]:px-6"
    >
      <div className="min-w-0">
        <p
          role="status"
          className="m-0 text-[13px] font-semibold text-text-primary"
        >
          Archived workspace · Read-only
        </p>
        <p className="m-0 mt-0.5 text-[11px] text-text-muted">
          Restore the workspace to make changes again.
        </p>
      </div>
      <button
        type="button"
        disabled={
          !validRevision ||
          busy ||
          sessionExpired ||
          authenticationRequired ||
          restored.current
        }
        onClick={() => void restore()}
        className="m-0 flex h-10 w-[184px] max-w-full shrink-0 items-center justify-center rounded-[7px] border border-action bg-surface px-3 text-sm font-semibold text-action-text disabled:opacity-50"
      >
        Restore workspace
      </button>
      {error && (
        <p role="alert" className="m-0 w-full text-sm text-status-error">
          {error}
        </p>
      )}
    </div>
  );
}
export function ConversationComposer({
  draft,
  onChange,
  onSubmit,
  readOnly,
  disabled,
  archived,
  restoreDisabled,
  onRestore,
}: {
  draft: string;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  readOnly: boolean;
  disabled: boolean;
  archived: boolean;
  restoreDisabled: boolean;
  onRestore?: () => void;
}) {
  return (
    <div className="flex min-h-[72px] items-center border-t border-border bg-surface px-4 py-[11px] min-[960px]:px-6">
      {archived ? (
        <div
          aria-label={
            onRestore
              ? "Archived conversation controls"
              : "Read-only conversation controls"
          }
          className="flex min-h-12 w-full flex-wrap items-center justify-between gap-2 rounded-[10px] border border-border bg-surface-subtle py-1.5 pl-3.5 pr-2 text-[13px] text-text-muted"
        >
          <p role="status" className="m-0">
            {onRestore
              ? "Archived conversation · Read-only"
              : "This Conversation is read-only."}
          </p>
          {onRestore && (
            <button
              type="button"
              disabled={restoreDisabled}
              onClick={onRestore}
              className="m-0 flex min-h-[34px] w-[151px] max-w-full items-center justify-center rounded-lg border border-action bg-action/10 px-[7px] py-2 text-[13px] leading-4 font-semibold text-action-text disabled:opacity-50"
            >
              Restore conversation
            </button>
          )}
        </div>
      ) : (
        <form
          aria-label="Question composer"
          onSubmit={onSubmit}
          className="flex h-12 w-full items-center gap-2 rounded-[10px] border border-border bg-surface pl-3.5 pr-2"
        >
          <label htmlFor="conversation-question" className="sr-only">
            Question
          </label>
          <textarea
            id="conversation-question"
            rows={1}
            value={draft}
            readOnly={readOnly}
            onChange={(event) => onChange(event.target.value)}
            placeholder="Ask about the documents in this workspace…"
            className="kn-field__control my-0 min-h-0 w-full resize-none border-0 bg-transparent px-0 py-3 text-[13px] leading-5 text-text-primary placeholder:text-text-muted"
          />
          <button
            type="submit"
            aria-label="Ask"
            title="Send question"
            disabled={disabled}
            className="m-0 flex size-[34px] shrink-0 items-center justify-center rounded-lg border border-action bg-action p-0 text-base font-semibold text-action-foreground disabled:border-border disabled:bg-surface-subtle disabled:text-text-muted"
          >
            <span aria-hidden="true">↑</span>
          </button>
        </form>
      )}
    </div>
  );
}

export function ConversationEmpty({
  onSuggest,
  disabled = false,
}: {
  onSuggest: (value: string) => void;
  disabled?: boolean;
}) {
  const sheet = (
    <div className="relative h-[154px] w-[118px] overflow-hidden rounded-[10px] border border-border bg-surface">
      <div className="absolute left-[85px] top-[11px] size-5 rounded bg-surface-subtle" />
      <div className="absolute left-[13px] top-[17px] h-1.5 w-12 rounded bg-text-primary" />
      <div className="absolute left-[13px] top-[31px] h-1 w-[72px] rounded-sm bg-text-muted" />
      <div className="absolute left-[13px] top-[55px] h-[5px] w-[86px] rounded-sm bg-control-border" />
      <div className="absolute left-[13px] top-[68px] h-[5px] w-[76px] rounded-sm bg-border" />
      <div className="absolute left-[13px] top-[81px] h-[5px] w-[84px] rounded-sm bg-border" />
      <div className="absolute left-[13px] top-[94px] h-[5px] w-16 rounded-sm bg-border" />
      <div className="absolute left-[13px] top-[117px] flex h-[22px] w-[43px] items-center justify-center rounded-md bg-action/10 text-[9px] font-semibold leading-[11px] text-action-text">
        PDF
      </div>
    </div>
  );
  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-[15px] py-3 text-center">
      <div
        aria-hidden="true"
        className="relative h-[350px] w-[520px] max-[650px]:-my-12 max-[650px]:scale-[0.62]"
      >
        <img
          src="/brand/orbit-inner.png"
          alt=""
          width={330}
          height={210}
          className="absolute left-[95px] top-[72px] h-[210px] w-[330px] max-w-none"
        />
        <img
          src="/brand/orbit-outer.png"
          alt=""
          width={430}
          height={276}
          className="absolute left-[45px] top-[38px] h-[276px] w-[430px] max-w-none"
        />
        <div className="absolute left-[128.57px] top-[92px] flex h-[168.924px] w-[138.284px] items-center justify-center">
          <div className="rotate-[8deg]">{sheet}</div>
        </div>
        <div className="absolute left-[204px] top-[70px]">{sheet}</div>
        <div className="absolute left-[260px] top-[75.58px] flex h-[168.924px] w-[138.284px] items-center justify-center">
          <div className="-rotate-[8deg]">{sheet}</div>
        </div>
        <div className="absolute left-[212px] top-[132px] size-24 rounded-full border border-border bg-surface">
          <img
            src="/brand/knora-leaf-large.svg"
            width={54}
            height={54}
            alt=""
            className="absolute left-5 top-5 size-[54px] max-w-none"
          />
        </div>
        <span className="absolute left-[52px] top-[82px] rounded-[14px] border border-border bg-signature/10 px-[11px] py-[7px] text-[10px] font-semibold leading-[13px] text-signature">
          SOURCES
        </span>
        <span className="absolute left-[352px] top-[72px] rounded-[14px] border border-border bg-action/10 px-[11px] py-[7px] text-[10px] font-semibold leading-[13px] text-action-text">
          PAGE RANGES
        </span>
        <span className="absolute left-[54px] top-[244px] rounded-[14px] border border-border bg-surface-subtle px-[11px] py-[7px] text-[10px] font-semibold leading-[13px]">
          PROVENANCE
        </span>
        <span className="absolute left-[342px] top-[248px] rounded-[14px] border border-control-border bg-surface px-[11px] py-[7px] text-[10px] font-semibold leading-[13px]">
          VERIFY IN CONTEXT
        </span>
      </div>
      <h2 className="max-w-[650px] font-display text-[27px] font-semibold leading-[34px]">
        Grounded answers from your workspace
      </h2>
      <p className="max-w-[590px] text-sm leading-[22px] text-text-muted">
        Knora answers using your indexed documents and shows the evidence behind
        each response.
      </p>
      <p className="text-[9px] font-semibold leading-3 text-text-muted">
        TRY A QUESTION
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        {[
          "Summarize this workspace",
          "Compare the documents",
          "Find supporting evidence",
        ].map((prompt) => (
          <button
            type="button"
            key={prompt}
            disabled={disabled}
            onClick={() => onSuggest(prompt)}
            className="m-0 rounded-lg border border-border bg-surface px-3 py-2 text-[11px] font-medium leading-[14px] disabled:opacity-50"
          >
            {prompt}
          </button>
        ))}
      </div>
      <p className="max-w-[560px] rounded-[7px] bg-surface-subtle px-2.5 py-1.5 text-[10px] leading-[15px] text-text-muted">
        Answers stay grounded: sources, excerpts, page ranges, and provenance
        remain inspectable.
      </p>
    </div>
  );
}
