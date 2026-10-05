"use client";

import React, {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  ConversationResponse,
  TurnResponse,
} from "@/generated/knora-openapi";
import { EvidenceInspector } from "@/components/citations/EvidenceInspector";
import { ConversationPanels } from "./ConversationPanels";
import { ConversationRail } from "./ConversationRail";
import { TurnCard } from "./TurnCard";
import {
  ConversationComposer,
  ConversationEmpty,
} from "./ConversationComposer";
import type {
  EvidenceSelection,
  PanelIdentityScope,
} from "@/lib/conversations/panel-preferences";
import { browserRequest } from "@/lib/api/browser-client";

const pending = new Set(["queued", "processing", "pending"]);

const emptyConversations: ConversationResponse[] = [];
type ConversationViewProps = {
  workspaceId: string;
  conversation: ConversationResponse;
  workspaceArchived?: boolean;
  identityScope?: PanelIdentityScope;
  workspaceName?: string;
  workspaceSelector?: React.ReactNode;
  initialConversations?: ConversationResponse[];
  nextCursor?: string | null;
};
export function ConversationView(props: ConversationViewProps) {
  return (
    <ConversationViewState
      key={`${props.workspaceId}:${props.conversation.id}`}
      {...props}
    />
  );
}
function ConversationViewState({
  workspaceId,
  conversation,
  workspaceArchived = false,
  identityScope,
  workspaceName,
  workspaceSelector,
  initialConversations = emptyConversations,
  nextCursor = null,
}: ConversationViewProps) {
  const active = useRef(true);
  const [projection, setProjection] = useState(conversation);
  const [selection, setSelection] = useState<EvidenceSelection | null>(null);
  const [restoring, setRestoring] = useState(false);
  useEffect(() => {
    setProjection(conversation);
  }, [conversation]);
  const [turns, setTurns] = useState<TurnResponse[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [cursor, setCursor] = useState<string | null>(null);
  const [submissionUncertain, setSubmissionUncertain] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submissionConflict, setSubmissionConflict] = useState(false);
  const [serverArchived, setServerArchived] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);
  const authenticationRequired = useRef(false);
  const authenticationGeneration = useRef(0);
  const submitKey = useRef<string | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const base = `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations/${encodeURIComponent(conversation.id)}`;

  const requireAuthentication = useCallback(() => {
    authenticationGeneration.current += 1;
    authenticationRequired.current = true;
    setSessionExpired(true);
    setNotice(null);
    setError(null);
    if (pollTimer.current) clearTimeout(pollTimer.current);
  }, []);

  const pollTurn = useCallback(
    async function pollTurn(turnId: string) {
      if (!active.current || authenticationRequired.current) return;
      const generation = authenticationGeneration.current;
      try {
        const response = await browserRequest(
          `${base}/turns/${encodeURIComponent(turnId)}`,
        );
        if (!active.current || generation !== authenticationGeneration.current)
          return;
        if (response.status === 401) {
          requireAuthentication();
          return;
        }
        if (!response.ok) throw new Error("Turn status unavailable");
        const turn = (await response.json()) as TurnResponse;
        if (!active.current) return;
        if (
          !active.current ||
          authenticationRequired.current ||
          generation !== authenticationGeneration.current
        )
          return;
        setTurns((current) => {
          const others = current.filter((item) => item.id !== turn.id);
          return [...others, turn].sort((a, b) => a.sequence - b.sequence);
        });
        if (pending.has(turn.status)) {
          pollTimer.current = setTimeout(() => void pollTurn(turn.id), 2000);
        } else if (turn.status === "interrupted") {
          setNotice(
            "The result is uncertain. Check this Turn before submitting again.",
          );
        } else {
          setNotice(null);
        }
      } catch {
        if (!active.current || authenticationRequired.current) return;
        setNotice(
          "Unable to confirm this Turn. Reload history before retrying.",
        );
      }
    },
    [base, requireAuthentication],
  );

  const load = useCallback(async () => {
    const generation = authenticationGeneration.current;
    const recoveringSession = authenticationRequired.current;
    setLoading(true);
    if (pollTimer.current) clearTimeout(pollTimer.current);
    try {
      const response = await browserRequest(`${base}/turns?limit=50`);
      if (!active.current) return null;
      if (response.status === 401) {
        requireAuthentication();
        return null;
      }
      if (!response.ok) throw new Error("history unavailable");
      const page = (await response.json()) as {
        items: TurnResponse[];
        next_cursor: string | null;
      };
      if (!active.current || generation !== authenticationGeneration.current)
        return null;
      setTurns(page.items);
      setCursor(page.next_cursor);
      authenticationRequired.current = false;
      setSessionExpired(false);
      if (recoveringSession) setNotice(null);
      for (const turn of page.items) {
        if (pending.has(turn.status)) void pollTurn(turn.id);
      }
      setError(null);
      return page.items;
    } catch {
      if (!active.current || generation !== authenticationGeneration.current)
        return null;
      setError("Unable to load Conversation history. Retry this page.");
      return null;
    } finally {
      setLoading(false);
    }
  }, [base, pollTurn, requireAuthentication]);

  async function loadMore() {
    if (!cursor || authenticationRequired.current) return;
    const generation = authenticationGeneration.current;
    try {
      const response = await browserRequest(
        `${base}/turns?limit=50&cursor=${encodeURIComponent(cursor)}`,
      );
      if (!active.current) return null;
      if (response.status === 401) {
        requireAuthentication();
        return;
      }
      if (!response.ok) throw new Error("more Turns unavailable");
      const page = (await response.json()) as {
        items: TurnResponse[];
        next_cursor: string | null;
      };
      if (!active.current || generation !== authenticationGeneration.current)
        return;
      setTurns((current) => {
        const seen = new Set(current.map((turn) => turn.id));
        return [
          ...current,
          ...page.items.filter((turn) => !seen.has(turn.id)),
        ].sort((a, b) => a.sequence - b.sequence);
      });
      setCursor(page.next_cursor);
    } catch {
      if (!active.current || generation !== authenticationGeneration.current)
        return;
      setError("Unable to load more Turns. Retry.");
    }
  }

  useEffect(() => {
    active.current = true;
    void load();
    return () => {
      active.current = false;
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, [load]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = draft.trim();
    if (
      !question ||
      workspaceArchived ||
      projection.archived ||
      serverArchived ||
      authenticationRequired.current ||
      submitting ||
      submissionConflict
    )
      return;
    setSubmitting(true);
    setError(null);
    submitKey.current ??= crypto.randomUUID();
    try {
      if (submitKey.current && error) {
        if (!(await load())) return;
      }
      if (!active.current || authenticationRequired.current) return;
      const response = await browserRequest(`${base}/turns`, {
        method: "POST",
        headers: { "Idempotency-Key": submitKey.current },
        body: JSON.stringify({ question }),
      });
      if (!active.current) return null;
      if (response.status === 401) {
        setSubmissionUncertain(true);
        requireAuthentication();
        return;
      }
      if (response.status === 409) {
        const body = (await response.json()) as { error?: { code?: string } };
        if (body.error?.code === "CONVERSATION_BUSY") {
          setNotice("This conversation is processing a question");
          await load();
        } else if (
          body.error?.code === "WORKSPACE_ARCHIVED" ||
          body.error?.code === "CONVERSATION_ARCHIVED"
        ) {
          setServerArchived(true);
          setNotice(null);
        } else {
          setSubmissionUncertain(true);
          setSubmissionConflict(true);
          setError(body.error?.code ?? "TURN_CONFLICT");
        }
        return;
      }
      if (!response.ok) {
        setError(
          `Unable to submit question (${response.status}). Retry with the same draft.`,
        );
        return;
      }
      const turn = (await response.json()) as TurnResponse;
      if (!active.current) return;
      submitKey.current = null;
      setSubmissionUncertain(false);
      setSubmissionConflict(false);
      setDraft("");
      setTurns((current) => [
        ...current.filter((item) => item.id !== turn.id),
        turn,
      ]);
      if (pending.has(turn.status)) void pollTurn(turn.id);
    } catch {
      setSubmissionUncertain(true);
      setError(
        "Submission status is uncertain. Check history, then retry with the same draft.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const railConversations = useMemo(
    () => [
      projection,
      ...initialConversations.filter((item) => item.id !== projection.id),
    ],
    [initialConversations, projection],
  );
  const readOnly = workspaceArchived || projection.archived || serverArchived;
  const selectedTurn = selection
    ? turns.find((turn) => turn.id === selection.turnId)
    : null;
  const selectedCitation =
    selectedTurn?.result?.citations[selection?.citationIndex ?? -1] ?? null;
  useEffect(() => {
    if (selection && !selectedCitation) setSelection(null);
  }, [selection, selectedCitation]);
  function suggest(value: string) {
    if (!readOnly && !submissionUncertain && !submitting && !sessionExpired) {
      setDraft(value);
      document.getElementById("conversation-question")?.focus();
    }
  }
  async function retry(turn: TurnResponse) {
    const history = await load();
    if (!history || !active.current || authenticationRequired.current) return;
    const latest = history.find((item) => item.id === turn.id);
    if (
      latest &&
      (pending.has(latest.status) ||
        latest.status === "answered" ||
        latest.status === "refused")
    )
      return;
    if (!submissionUncertain) setDraft(turn.question);
    setNotice("History checked. Send the same question when ready.");
    document.getElementById("conversation-question")?.focus();
  }
  async function restore() {
    if (workspaceArchived || restoring || sessionExpired) return;
    setRestoring(true);
    try {
      const response = await browserRequest(`${base}/restore`, {
        method: "POST",
        headers: { "If-Match": String(projection.revision) },
      });
      if (!active.current) return;
      if (response.status === 401) {
        requireAuthentication();
        return;
      }
      if (!response.ok) throw new Error("restore failed");
      const updated = (await response.json()) as ConversationResponse;
      if (!active.current) return;
      if (updated.id !== projection.id || updated.workspace_id !== workspaceId)
        throw new Error("scope mismatch");
      setProjection(updated);
      setServerArchived(false);
      setError(null);
    } catch {
      if (active.current)
        setError("Unable to restore Conversation. Reload and retry.");
    } finally {
      if (active.current) setRestoring(false);
    }
  }
  return (
    <ConversationPanels
      workspaceId={workspaceId}
      identityScope={identityScope}
      selection={selection}
      rail={(mode, onChange, overlay) => (
        <ConversationRail
          workspaceId={workspaceId}
          workspaceName={workspaceName}
          workspaceSelector={workspaceSelector}
          conversations={railConversations}
          nextCursor={nextCursor}
          selectedId={projection.id}
          onChanged={(updated) => {
            if (updated.id === projection.id) setProjection(updated);
          }}
          workspaceArchived={workspaceArchived}
          mode={mode}
          onChange={onChange}
          overlay={overlay}
        />
      )}
      inspector={
        <EvidenceInspector
          workspaceId={workspaceId}
          citation={selectedCitation}
          turn={selectedTurn ?? turns.at(-1)}
        />
      }
      composer={
        <>
          {sessionExpired && (
            <div role="alert" className="px-6 py-3 text-sm">
              <p>
                Your session has expired. Keep this tab open to preserve your
                draft. Sign in in a new tab, then return here and reload history
                before retrying.
              </p>
              <a
                href="/api/auth/login"
                target="_blank"
                rel="noopener noreferrer"
                className="mr-3 text-action-text underline"
              >
                Sign in again
              </a>
              <button
                type="button"
                disabled={loading || submitting}
                onClick={() => void load()}
              >
                Reload history
              </button>
            </div>
          )}
          <ConversationComposer
            draft={draft}
            onChange={(value) => {
              if (!submissionUncertain && !submitting && !sessionExpired)
                setDraft(value);
            }}
            onSubmit={(event) => void submit(event)}
            readOnly={submissionUncertain || submitting || sessionExpired}
            disabled={
              !draft.trim() ||
              submissionConflict ||
              submitting ||
              sessionExpired ||
              loading
            }
            archived={readOnly}
            restoreDisabled={workspaceArchived || restoring || sessionExpired}
            onRestore={projection.archived ? () => void restore() : undefined}
          />
        </>
      }
    >
      <h1 className="sr-only">{projection.title}</h1>
      {loading && <p className="text-sm text-text-muted">Loading history…</p>}
      {!loading && !turns.length && !error && !sessionExpired && (
        <ConversationEmpty
          onSuggest={suggest}
          disabled={readOnly || submissionUncertain || submitting}
        />
      )}
      <ol className="m-0 flex flex-col gap-8 p-0">
        {turns.map((turn) => (
          <TurnCard
            key={turn.id}
            turn={turn}
            workspaceId={workspaceId}
            selection={selection}
            onSelect={setSelection}
            onSuggest={suggest}
            onRetry={() => void retry(turn)}
            disabled={
              readOnly ||
              submitting ||
              loading ||
              sessionExpired ||
              submissionConflict
            }
            sessionExpired={sessionExpired}
          />
        ))}
      </ol>
      {cursor && (
        <button
          type="button"
          className="mt-4 w-fit text-xs text-text-muted"
          disabled={sessionExpired || loading}
          onClick={() => void loadMore()}
        >
          Load more Turns
        </button>
      )}
      {notice && (
        <p role="status" className="mt-4 text-sm text-text-muted">
          {notice}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-4 text-sm text-status-error">
          {error}
        </p>
      )}
    </ConversationPanels>
  );
}
