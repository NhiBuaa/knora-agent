"use client";

import { LeafLoading } from "@/components/ui/LeafLoading";
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
import { useRouter } from "next/navigation";
import { routes } from "@/lib/navigation/routes";
import { EvidenceInspector } from "@/components/citations/EvidenceInspector";
import { ConversationPanels } from "./ConversationPanels";
import { ConversationRail } from "./ConversationRail";
import { TurnCard } from "./TurnCard";
import {
  ConversationComposer,
  ConversationEmpty,
  WorkspaceReadOnlyComposer,
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
  draftMode?: boolean;
  conversation: ConversationResponse;
  workspaceArchived?: boolean;
  workspaceRevision?: number;
  identityScope?: PanelIdentityScope;
  workspaceName?: string;
  workspaceSelector?: React.ReactNode;
  initialConversations?: ConversationResponse[];
  nextCursor?: string | null;
};

export function ConversationView(props: ConversationViewProps) {
  const issuer = props.identityScope?.issuer ?? "";
  const subject = props.identityScope?.subject ?? "";
  return (
    <ConversationViewState
      key={`${issuer}:${subject}:${props.workspaceId}:${props.conversation.id}`}
      {...props}
    />
  );
}

function ConversationViewState({
  workspaceId,
  draftMode = false,
  conversation,
  workspaceArchived = false,
  workspaceRevision,
  identityScope,
  workspaceName,
  workspaceSelector,
  initialConversations = emptyConversations,
  nextCursor = null,
}: ConversationViewProps) {
  const router = useRouter();
  const active = useRef(true);
  const creationKey = useRef<string | null>(null);
  const admittedConversation = useRef<ConversationResponse | null>(
    draftMode ? null : conversation,
  );
  const submitBusy = useRef(false);
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
  const [loading, setLoading] = useState(!draftMode);
  const [cursor, setCursor] = useState<string | null>(null);
  const [submissionUncertain, setSubmissionUncertain] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submissionConflict, setSubmissionConflict] = useState(false);
  const [serverArchived, setServerArchived] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [checkingSession, setCheckingSession] = useState(false);
  const [identityChanged, setIdentityChanged] = useState(false);
  const [sessionLocked, setSessionLocked] = useState(false);

  const recoveryInFlight = useRef<Promise<void> | null>(null);
  const rerunRequested = useRef(false);
  const currentRecoveryRunToken = useRef(0);
  const needsIdentityCheck = useRef(false);

  const history = useRef<HTMLDivElement>(null);
  const historyPositioned = useRef(false);

  const expectedHeaders: Record<string, string> = useMemo(() => {
    const headers: Record<string, string> = {};
    if (identityScope?.issuer && identityScope?.subject) {
      headers["x-knora-expected-issuer"] = identityScope.issuer;
      headers["x-knora-expected-subject"] = identityScope.subject;
    }
    return headers;
  }, [identityScope?.issuer, identityScope?.subject]);

  useEffect(() => {
    if (loading || error || sessionExpired || historyPositioned.current) return;
    if (!turns.length) {
      historyPositioned.current = true;
      return;
    }
    const element = history.current;
    if (!element) return;
    let cancelled = false;
    let frame = 0;
    const cancel = () => {
      cancelled = true;
      historyPositioned.current = true;
    };
    for (const event of ["scroll", "wheel", "touchmove"])
      element.addEventListener(event, cancel, { passive: true });
    void (document.fonts?.ready ?? Promise.resolve()).then(() => {
      if (cancelled) return;
      frame = requestAnimationFrame(() => {
        frame = requestAnimationFrame(() => {
          if (cancelled) return;
          historyPositioned.current = true;
          element.scrollTop = element.scrollHeight;
        });
      });
    });
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      for (const event of ["scroll", "wheel", "touchmove"])
        element.removeEventListener(event, cancel);
    };
  }, [loading, error, sessionExpired, turns.length]);

  const authenticationRequired = useRef(false);
  const authenticationGeneration = useRef(0);
  const submitKey = useRef<string | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const base = `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations/${encodeURIComponent(projection.id)}`;

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
          `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations/${encodeURIComponent(admittedConversation.current?.id ?? projection.id)}/turns/${encodeURIComponent(turnId)}`,
          { headers: expectedHeaders },
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
    [expectedHeaders, requireAuthentication, workspaceId, projection.id],
  );

  const load = useCallback(async () => {
    const generation = authenticationGeneration.current;
    const recoveringSession = authenticationRequired.current;
    if (!admittedConversation.current?.id) {
      if (recoveringSession) {
        try {
          const response = await browserRequest(
            `/v1/workspaces/${encodeURIComponent(workspaceId)}`,
            { headers: expectedHeaders },
          );
          if (
            !active.current ||
            generation !== authenticationGeneration.current
          )
            return null;
          if (response.status === 401) {
            requireAuthentication();
            return null;
          }
          if (!response.ok) throw new Error("authentication read failed");
          authenticationRequired.current = false;
          setSessionExpired(false);
          setError(null);
        } catch {
          setError("Unable to verify your session. Retry.");
          return null;
        }
      }
      setLoading(false);
      return [];
    }
    setLoading(true);
    if (pollTimer.current) clearTimeout(pollTimer.current);
    try {
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations/${encodeURIComponent(admittedConversation.current.id)}/turns?limit=50`,
        { headers: expectedHeaders },
      );
      if (!active.current || generation !== authenticationGeneration.current)
        return null;
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
  }, [expectedHeaders, pollTurn, requireAuthentication, workspaceId]);

  const recoverSession = useCallback(async () => {
    if (!active.current) return;
    if (recoveryInFlight.current) {
      rerunRequested.current = true;
      return recoveryInFlight.current;
    }
    if (pollTimer.current) clearTimeout(pollTimer.current);

    const promise = (async () => {
      while (active.current) {
        rerunRequested.current = false;
        const generation = authenticationGeneration.current;
        const runToken = ++currentRecoveryRunToken.current;
        submitBusy.current = true;
        setCheckingSession(true);
        setSessionLocked(true);
        setError(null);

        let sessionData: { issuer: string; subject: string } | null = null;
        try {
          const res = await fetch("/api/auth/session", {
            cache: "no-store",
            headers: { "cache-control": "no-store" },
          });
          if (!active.current) return;
          if (
            generation !== authenticationGeneration.current ||
            rerunRequested.current
          ) {
            continue;
          }
          if (res.status === 503 || (!res.ok && res.status !== 401)) {
            setError("Unable to verify your session. Retry.");
            return;
          }
          if (res.status === 401) {
            requireAuthentication();
            return;
          }
          const data = (await res.json()) as {
            session: { issuer?: string; subject?: string } | null;
          };
          if (!active.current) return;
          if (
            generation !== authenticationGeneration.current ||
            rerunRequested.current
          ) {
            continue;
          }
          if (!data.session || !data.session.issuer || !data.session.subject) {
            requireAuthentication();
            return;
          }
          sessionData = {
            issuer: data.session.issuer,
            subject: data.session.subject,
          };
        } catch {
          if (!active.current) return;
          if (
            generation !== authenticationGeneration.current ||
            rerunRequested.current
          ) {
            continue;
          }
          setError("Unable to verify your session. Retry.");
          return;
        }

        if (!active.current) return;
        if (
          generation !== authenticationGeneration.current ||
          rerunRequested.current
        ) {
          continue;
        }

        const hasBaseline = Boolean(
          identityScope?.issuer && identityScope?.subject,
        );
        const sameIdentity =
          hasBaseline &&
          sessionData.issuer === identityScope?.issuer &&
          sessionData.subject === identityScope?.subject;

        if (!sameIdentity) {
          setIdentityChanged(true);
          setDraft("");
          setTurns([]);
          setSelection(null);
          creationKey.current = null;
          submitKey.current = null;
          admittedConversation.current = null;
          if (pollTimer.current) clearTimeout(pollTimer.current);
          if (typeof window !== "undefined") {
            window.location.replace("/workspaces");
          }
          return;
        }

        // Same identity -> GET history or unadmitted draft Workspace check
        try {
          if (!admittedConversation.current?.id) {
            const wsRes = await browserRequest(
              `/v1/workspaces/${encodeURIComponent(workspaceId)}`,
              { headers: expectedHeaders },
            );
            if (!active.current) return;
            if (
              generation !== authenticationGeneration.current ||
              rerunRequested.current
            ) {
              continue;
            }
            if (wsRes.status === 401) {
              requireAuthentication();
              return;
            }
            if (wsRes.status === 403) {
              setError(
                "You don't have permission to ask questions in this workspace.",
              );
              return;
            }
            if (!wsRes.ok) throw new Error("Workspace check failed");
            authenticationRequired.current = false;
            setSessionExpired(false);
            setSessionLocked(false);
            setError(null);
            setNotice(null);
            return;
          } else {
            const historyRes = await browserRequest(
              `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations/${encodeURIComponent(admittedConversation.current.id)}/turns?limit=50`,
              { headers: expectedHeaders },
            );
            if (!active.current) return;
            if (
              generation !== authenticationGeneration.current ||
              rerunRequested.current
            ) {
              continue;
            }
            if (historyRes.status === 401) {
              requireAuthentication();
              return;
            }
            if (historyRes.status === 403) {
              setError(
                "You don't have permission to ask questions in this workspace.",
              );
              return;
            }
            if (!historyRes.ok) throw new Error("History fetch failed");
            const page = (await historyRes.json()) as {
              items: TurnResponse[];
              next_cursor: string | null;
            };
            if (!active.current) return;
            if (
              generation !== authenticationGeneration.current ||
              rerunRequested.current
            ) {
              continue;
            }
            setTurns(page.items);
            setCursor(page.next_cursor);
            authenticationRequired.current = false;
            setSessionExpired(false);
            setSessionLocked(false);
            setError(null);
            setNotice(null);
            for (const turn of page.items) {
              if (pending.has(turn.status)) void pollTurn(turn.id);
            }
            return;
          }
        } catch {
          if (!active.current) return;
          if (
            generation !== authenticationGeneration.current ||
            rerunRequested.current
          ) {
            continue;
          }
          setError("Unable to load Conversation history. Retry this page.");
          return;
        }
      }
    })();

    recoveryInFlight.current = promise;
    try {
      await promise;
    } finally {
      recoveryInFlight.current = null;
      submitBusy.current = false;
      setCheckingSession(false);
    }
  }, [
    expectedHeaders,
    identityScope?.issuer,
    identityScope?.subject,
    pollTurn,
    requireAuthentication,
    workspaceId,
  ]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const onLeave = () => {
      needsIdentityCheck.current = true;
      if (pollTimer.current) clearTimeout(pollTimer.current);
      authenticationGeneration.current += 1;
    };
    const onReturn = () => {
      if (
        !document.hidden &&
        document.hasFocus() &&
        needsIdentityCheck.current
      ) {
        needsIdentityCheck.current = false;
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
          void recoverSession();
        }, 0);
      }
    };
    window.addEventListener("blur", onLeave);
    const onVisibilityChange = () => {
      if (document.hidden) {
        onLeave();
      } else {
        onReturn();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("focus", onReturn);
    return () => {
      window.removeEventListener("blur", onLeave);
      window.removeEventListener("focus", onReturn);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      if (timer) clearTimeout(timer);
    };
  }, [recoverSession]);

  async function loadMore() {
    if (!cursor || authenticationRequired.current) return;
    const generation = authenticationGeneration.current;
    try {
      const response = await browserRequest(
        `${base}/turns?limit=50&cursor=${encodeURIComponent(cursor)}`,
        { headers: expectedHeaders },
      );
      if (!active.current || generation !== authenticationGeneration.current)
        return null;
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
    await submitQuestion(draft);
  }

  async function submitQuestion(value: string) {
    const question = value.trim();
    if (
      !question ||
      !identityScope?.issuer ||
      !identityScope?.subject ||
      workspaceArchived ||
      projection.archived ||
      serverArchived ||
      authenticationRequired.current ||
      submitBusy.current ||
      submitting ||
      submissionConflict ||
      checkingSession ||
      sessionLocked
    )
      return;
    const generation = authenticationGeneration.current;
    submitBusy.current = true;
    setDraft(question);
    setSubmitting(true);
    setError(null);
    submitKey.current ??= crypto.randomUUID();
    try {
      if (submitKey.current && error) {
        if (!(await load())) return;
      }
      if (
        !active.current ||
        authenticationRequired.current ||
        generation !== authenticationGeneration.current
      )
        return;
      let target = admittedConversation.current;
      if (!target) {
        creationKey.current ??= crypto.randomUUID();
        const created = await browserRequest(
          `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations`,
          {
            method: "POST",
            headers: {
              "Idempotency-Key": creationKey.current,
              ...expectedHeaders,
            },
          },
        );
        if (!active.current || generation !== authenticationGeneration.current)
          return;
        if (created.status === 401) {
          try {
            const body = (await created.json()) as { detail?: string };
            if (
              !active.current ||
              generation !== authenticationGeneration.current
            ) {
              return;
            }
            if (body.detail === "SESSION_IDENTITY_MISMATCH") {
              void recoverSession();
              return;
            }
          } catch {
            // generic 401
          }
          if (
            !active.current ||
            generation !== authenticationGeneration.current
          ) {
            return;
          }
          setSubmissionUncertain(true);
          requireAuthentication();
          return;
        }
        if (created.status === 403) {
          setError(
            "You don't have permission to ask questions in this workspace.",
          );
          return;
        }
        if (!created.ok)
          throw new Error("Unable to confirm conversation creation");
        target = (await created.json()) as ConversationResponse;
        if (target.workspace_id !== workspaceId || !target.id)
          throw new Error("Creation scope mismatch");
        if (
          !active.current ||
          authenticationRequired.current ||
          generation !== authenticationGeneration.current
        )
          return;
        admittedConversation.current = target;
      }
      const response = await browserRequest(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/conversations/${encodeURIComponent(target.id)}/turns`,
        {
          method: "POST",
          headers: {
            "Idempotency-Key": submitKey.current,
            ...expectedHeaders,
          },
          body: JSON.stringify({ question }),
        },
      );
      if (!active.current || generation !== authenticationGeneration.current)
        return null;
      if (response.status === 401) {
        try {
          const body = (await response.json()) as { detail?: string };
          if (
            !active.current ||
            generation !== authenticationGeneration.current
          ) {
            return;
          }
          if (body.detail === "SESSION_IDENTITY_MISMATCH") {
            void recoverSession();
            return;
          }
        } catch {
          // generic 401
        }
        if (
          !active.current ||
          generation !== authenticationGeneration.current
        ) {
          return;
        }
        setSubmissionUncertain(true);
        requireAuthentication();
        return;
      }
      if (response.status === 409) {
        try {
          const body = (await response.json()) as { error?: { code?: string } };
          if (
            !active.current ||
            generation !== authenticationGeneration.current
          ) {
            return;
          }
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
        } catch {
          if (
            !active.current ||
            generation !== authenticationGeneration.current
          ) {
            return;
          }
          setSubmissionUncertain(true);
          setSubmissionConflict(true);
          setError("TURN_CONFLICT");
        }
        return;
      }
      if (response.status === 403) {
        setError(
          "You don't have permission to ask questions in this workspace.",
        );
        return;
      }
      if (!response.ok) {
        setError(
          `Unable to submit question (${response.status}). Retry with the same draft.`,
        );
        return;
      }
      const turn = (await response.json()) as TurnResponse;
      if (!active.current || generation !== authenticationGeneration.current)
        return;
      if (draftMode && !projection.id) {
        setProjection({
          ...target,
          title: question.replace(/\s+/g, " ").slice(0, 80),
        });
        router.replace(routes.conversation(workspaceId, target.id));
      }
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
      if (active.current && generation === authenticationGeneration.current) {
        setSubmissionUncertain(true);
        setError(
          "Submission status is uncertain. Check history, then retry with the same draft.",
        );
      }
    } finally {
      if (generation === authenticationGeneration.current) {
        submitBusy.current = false;
      }
      setSubmitting(false);
    }
  }

  const railConversations = useMemo(() => {
    if (!projection.id || projection.archived) return initialConversations;
    if (initialConversations.some((item) => item.id === projection.id))
      return initialConversations.map((item) =>
        item.id === projection.id ? projection : item,
      );
    return [...initialConversations, projection].sort(
      (a, b) =>
        b.updated_at.localeCompare(a.updated_at) || b.id.localeCompare(a.id),
    );
  }, [initialConversations, projection]);

  const readOnly = workspaceArchived || projection.archived || serverArchived;
  const selectedTurn = selection
    ? turns.find((turn) => turn.id === selection.turnId)
    : null;
  const selectedCitation =
    selectedTurn?.result?.citations[selection?.citationIndex ?? -1] ?? null;

  useEffect(() => {
    if (selection && !selectedCitation) setSelection(null);
  }, [selection, selectedCitation]);

  async function retry(turn: TurnResponse) {
    const historyList = await load();
    if (!historyList || !active.current || authenticationRequired.current)
      return;
    const latest = historyList.find((item) => item.id === turn.id);
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
    if (workspaceArchived || restoring || sessionExpired || checkingSession)
      return;
    const generation = authenticationGeneration.current;
    setRestoring(true);
    try {
      const response = await browserRequest(`${base}/restore`, {
        method: "POST",
        headers: {
          "If-Match": String(projection.revision),
          ...expectedHeaders,
        },
      });
      if (!active.current || generation !== authenticationGeneration.current)
        return;
      if (response.status === 401) {
        requireAuthentication();
        return;
      }
      if (!response.ok) throw new Error("restore failed");
      const updated = (await response.json()) as ConversationResponse;
      if (!active.current || generation !== authenticationGeneration.current)
        return;
      if (updated.id !== projection.id || updated.workspace_id !== workspaceId)
        throw new Error("scope mismatch");
      setProjection(updated);
      setServerArchived(false);
      setError(null);
    } catch {
      if (active.current && generation === authenticationGeneration.current)
        setError("Unable to restore Conversation. Reload and retry.");
    } finally {
      setRestoring(false);
    }
  }

  if (identityChanged) {
    return (
      <div
        className="flex flex-1 items-center justify-center p-6 text-sm text-text-muted"
        role="status"
      >
        Your account changed. Opening Workspaces…
      </div>
    );
  }

  return (
    <ConversationPanels
      workspaceId={workspaceId}
      historyRef={history}
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
          workspaceArchived={workspaceArchived}
          citation={selectedCitation}
          turn={selectedTurn ?? turns.at(-1)}
        />
      }
      composer={
        <>
          {checkingSession && (
            <p role="status" className="px-6 py-2 text-sm text-text-muted">
              Checking your session…
            </p>
          )}
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
                disabled={loading || submitting || checkingSession}
                onClick={() => void recoverSession()}
              >
                Reload history
              </button>
            </div>
          )}
          {workspaceArchived ? (
            <WorkspaceReadOnlyComposer
              key={`${workspaceId}:${workspaceRevision}`}
              workspaceId={workspaceId}
              workspaceRevision={workspaceRevision}
              sessionExpired={sessionExpired}
              onAuthenticationRequired={requireAuthentication}
            />
          ) : (
            <ConversationComposer
              draft={draft}
              onChange={(value) => {
                if (
                  !submissionUncertain &&
                  !submitting &&
                  !sessionExpired &&
                  !checkingSession
                )
                  setDraft(value);
              }}
              onSubmit={(event) => void submit(event)}
              readOnly={
                submissionUncertain ||
                submitting ||
                sessionExpired ||
                checkingSession ||
                sessionLocked
              }
              disabled={
                !draft.trim() ||
                !identityScope?.issuer ||
                !identityScope?.subject ||
                submissionConflict ||
                submitting ||
                sessionExpired ||
                checkingSession ||
                sessionLocked ||
                loading
              }
              archived={readOnly}
              restoreDisabled={
                workspaceArchived ||
                restoring ||
                sessionExpired ||
                checkingSession
              }
              onRestore={projection.archived ? () => void restore() : undefined}
            />
          )}
        </>
      }
    >
      <h1 className="sr-only">{projection.title}</h1>
      {loading && <LeafLoading label="Loading conversation history" />}
      {!loading && !turns.length && !error && !sessionExpired && (
        <ConversationEmpty />
      )}
      <ol className="m-0 flex flex-col gap-8 p-0">
        {turns.map((turn) => (
          <TurnCard
            key={turn.id}
            turn={turn}
            workspaceId={workspaceId}
            selection={selection}
            onSelect={(next) =>
              setSelection((current) =>
                current?.turnId === next.turnId &&
                current.citationIndex === next.citationIndex
                  ? null
                  : next,
              )
            }
            onRetry={() => void retry(turn)}
            disabled={
              readOnly ||
              submitting ||
              loading ||
              sessionExpired ||
              checkingSession ||
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
          disabled={sessionExpired || loading || checkingSession}
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
        <div role="alert" className="mt-4 text-sm text-status-error">
          <p>{error}</p>
          {(error === "Unable to verify your session. Retry." ||
            error === "Unable to load Conversation history. Retry this page." ||
            error.toLowerCase().includes("retry")) && (
            <button
              type="button"
              disabled={checkingSession || submitting || loading}
              onClick={() => void recoverSession()}
              className="mt-2 text-action-text underline"
            >
              Retry
            </button>
          )}
        </div>
      )}
    </ConversationPanels>
  );
}
