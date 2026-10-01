"use client";

import React, {
  FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type {
  ConversationResponse,
  TurnResponse,
} from "@/generated/knora-openapi";
import { CitationViewer } from "@/components/citations/CitationViewer";
import { browserRequest } from "@/lib/api/browser-client";

const pending = new Set(["queued", "processing", "pending"]);

export function ConversationView({
  workspaceId,
  conversation,
  workspaceArchived = false,
}: {
  workspaceId: string;
  conversation: ConversationResponse;
  workspaceArchived?: boolean;
}) {
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
      if (authenticationRequired.current) return;
      try {
        const response = await browserRequest(
          `${base}/turns/${encodeURIComponent(turnId)}`,
        );
        if (response.status === 401) {
          requireAuthentication();
          return;
        }
        if (!response.ok) throw new Error("Turn status unavailable");
        const turn = (await response.json()) as TurnResponse;
        if (authenticationRequired.current) return;
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
        if (authenticationRequired.current) return;
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
      if (response.status === 401) {
        requireAuthentication();
        return null;
      }
      if (!response.ok) throw new Error("history unavailable");
      const page = (await response.json()) as {
        items: TurnResponse[];
        next_cursor: string | null;
      };
      if (generation !== authenticationGeneration.current) return null;
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
      setError("Unable to load Conversation history. Retry this page.");
      return null;
    } finally {
      setLoading(false);
    }
  }, [base, pollTurn, requireAuthentication]);

  async function loadMore() {
    if (!cursor || authenticationRequired.current) return;
    try {
      const response = await browserRequest(
        `${base}/turns?limit=50&cursor=${encodeURIComponent(cursor)}`,
      );
      if (response.status === 401) {
        requireAuthentication();
        return;
      }
      if (!response.ok) throw new Error("more Turns unavailable");
      const page = (await response.json()) as {
        items: TurnResponse[];
        next_cursor: string | null;
      };
      setTurns((current) => {
        const seen = new Set(current.map((turn) => turn.id));
        return [
          ...current,
          ...page.items.filter((turn) => !seen.has(turn.id)),
        ].sort((a, b) => a.sequence - b.sequence);
      });
      setCursor(page.next_cursor);
    } catch {
      setError("Unable to load more Turns. Retry.");
    }
  }

  useEffect(() => {
    void load();
    return () => {
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, [load]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = draft.trim();
    if (
      !question ||
      workspaceArchived ||
      conversation.archived ||
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
      if (authenticationRequired.current) return;
      const response = await browserRequest(`${base}/turns`, {
        method: "POST",
        headers: { "Idempotency-Key": submitKey.current },
        body: JSON.stringify({ question }),
      });
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

  return (
    <section>
      <h1>{conversation.title}</h1>
      {(workspaceArchived || conversation.archived || serverArchived) && (
        <p role="status">This Conversation is read-only.</p>
      )}
      {loading && <p>Loading history…</p>}
      {!loading && !turns.length && !error && !sessionExpired && (
        <p>No questions yet.</p>
      )}
      {sessionExpired && (
        <div role="alert">
          <p>
            Your session has expired. Keep this tab open to preserve your draft.
            Sign in in a new tab, then return here and reload history before
            retrying.
          </p>
          <a href="/api/auth/login" target="_blank" rel="noopener noreferrer">
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
      <ol>
        {turns.map((turn) => (
          <li key={turn.id}>
            <h2>Question {turn.sequence}</h2>
            <p>{turn.question}</p>
            {turn.result?.decision === "ANSWER" && turn.result.answer && (
              <p>{turn.result.answer}</p>
            )}
            {turn.result?.decision !== "ANSWER" &&
              turn.result?.refusal_reason && (
                <p>Refused: {turn.result.refusal_reason}</p>
              )}
            {turn.result?.citations && (
              <CitationViewer
                citations={turn.result.citations}
                workspaceId={workspaceId}
              />
            )}
            {pending.has(turn.status) && !sessionExpired && (
              <p role="status">Processing question…</p>
            )}
            {turn.status === "interrupted" && <p>Outcome uncertain</p>}
            {turn.error_code && <p role="alert">{turn.error_code}</p>}
          </li>
        ))}
      </ol>
      {cursor && (
        <button
          type="button"
          disabled={sessionExpired || loading}
          onClick={() => void loadMore()}
        >
          Load more Turns
        </button>
      )}
      {!workspaceArchived && !conversation.archived && !serverArchived && (
        <form onSubmit={(event) => void submit(event)}>
          <label htmlFor="conversation-question">Question</label>
          <textarea
            id="conversation-question"
            value={draft}
            readOnly={submissionUncertain || submitting || sessionExpired}
            onChange={(event) => {
              if (!submissionUncertain && !submitting && !sessionExpired)
                setDraft(event.target.value);
            }}
          />
          <button
            type="submit"
            disabled={
              !draft.trim() ||
              submissionConflict ||
              submitting ||
              sessionExpired ||
              loading
            }
          >
            Ask
          </button>
        </form>
      )}
      {notice && <p role="status">{notice}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
