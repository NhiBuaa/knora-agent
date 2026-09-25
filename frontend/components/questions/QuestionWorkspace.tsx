"use client";
import { FormEvent, useState } from "react";
import type { QuestionResponse } from "@/generated/knora-openapi";
import { browserRequest } from "@/lib/api/browser-client";
import {
  consumeQuestionStream,
  QuestionStreamError,
  streamUnavailable,
} from "@/lib/questions/sse";
import {
  initialQuestionState,
  interruptedQuestionState,
  questionStateReducer,
  type QuestionState,
} from "@/lib/ui-states";
import { CitationViewer } from "@/components/citations/CitationViewer";

type Turn = { question: string; state: QuestionState };
export function QuestionWorkspace({ workspaceId }: { workspaceId: string }) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [state, setState] = useState(initialQuestionState);
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = question.trim();
    if (!value || busy) return;
    setBusy(true);
    setState(initialQuestionState);
    let current = initialQuestionState;
    const apply = (next: QuestionState) => {
      current = next;
      setState(next);
    };
    try {
      const response = await browserRequest("/v1/questions/stream", {
        method: "POST",
        body: JSON.stringify({ workspace_id: workspaceId, question: value }),
      });
      if (streamUnavailable(response)) {
        const fallback = await browserRequest("/v1/questions", {
          method: "POST",
          body: JSON.stringify({ workspace_id: workspaceId, question: value }),
        });
        if (!fallback.ok)
          throw new QuestionStreamError("STREAM_HTTP_ERROR", fallback.status);
        const result = (await fallback.json()) as QuestionResponse;
        apply(
          questionStateReducer(current, {
            stage:
              result.decision === "REFUSAL" ? "refusal" : "final_validated",
            terminal: true,
            payload: result as unknown as Record<string, unknown>,
          }),
        );
      } else
        await consumeQuestionStream(response, (event) =>
          apply(questionStateReducer(current, event)),
        );
      setTurns((history) => [...history, { question: value, state: current }]);
      setQuestion("");
    } catch (error) {
      if (
        error instanceof QuestionStreamError &&
        error.code === "STREAM_INTERRUPTED"
      )
        apply(interruptedQuestionState(current));
      else
        apply({
          ...current,
          status: "failure",
          answer: null,
          citations: [],
          errorCode: error instanceof Error ? error.message : "REQUEST_FAILED",
        });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section>
      <h1>Ask Knora</h1>
      <form onSubmit={submit}>
        <label htmlFor="question">Question</label>
        <textarea
          id="question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !question.trim()}>
          {busy ? "Working…" : "Ask"}
        </button>
      </form>
      {state.status !== "idle" && <QuestionResult state={state} />}
      {turns.map((turn, index) => (
        <article key={`${turn.question}-${index}`}>
          <h2>{turn.question}</h2>
          <QuestionResult state={turn.state} />
        </article>
      ))}
    </section>
  );
}
function QuestionResult({ state }: { state: QuestionState }) {
  if (state.status === "progress")
    return <p role="status">Processing: {state.stage}</p>;
  if (state.status === "final")
    return (
      <div>
        <p>{state.answer}</p>
        <CitationViewer citations={state.citations} />
        <small>Trace: {state.traceId}</small>
      </div>
    );
  if (state.status === "refusal")
    return <p role="status">No answer: {state.refusalReason}</p>;
  if (state.status === "interrupted")
    return (
      <p role="alert">The request was interrupted. It was not completed.</p>
    );
  if (state.status === "failure")
    return <p role="alert">Request failed: {state.errorCode}</p>;
  return null;
}
