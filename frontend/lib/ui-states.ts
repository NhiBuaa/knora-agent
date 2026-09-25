import type {
  CitationResponse,
  DocumentResponse,
  IngestionJobStatusResponse,
  QuestionResponse,
} from "@/generated/knora-openapi";

export type QuestionStage =
  | "started"
  | "retrieving"
  | "selecting_evidence"
  | "generating"
  | "final_validated"
  | "refusal"
  | "failure";
export type QuestionEvent = {
  stage: QuestionStage;
  payload: Record<string, unknown>;
  terminal?: boolean;
};
export type QuestionStatus =
  | "idle"
  | "progress"
  | "final"
  | "refusal"
  | "failure"
  | "interrupted";
export type QuestionState = {
  status: QuestionStatus;
  stage?: Exclude<QuestionStage, "final_validated" | "refusal" | "failure">;
  answer: string | null;
  citations: CitationResponse[];
  refusalReason: string | null;
  traceId: string | null;
  errorCode: string | null;
};

export const initialQuestionState: QuestionState = {
  status: "idle",
  answer: null,
  citations: [],
  refusalReason: null,
  traceId: null,
  errorCode: null,
};

export function questionStateReducer(
  state: QuestionState,
  event: QuestionEvent,
): QuestionState {
  if (
    state.status === "final" ||
    state.status === "refusal" ||
    state.status === "failure" ||
    state.status === "interrupted"
  )
    return state;
  if (event.stage === "final_validated" && event.terminal) {
    return {
      status: "final",
      answer:
        typeof event.payload.answer === "string" ? event.payload.answer : "",
      citations: Array.isArray(event.payload.citations)
        ? (event.payload.citations as CitationResponse[])
        : [],
      refusalReason: null,
      traceId: stringValue(event.payload.trace_id),
      errorCode: null,
    };
  }
  if (event.stage === "refusal" && event.terminal)
    return {
      status: "refusal",
      answer: null,
      citations: [],
      refusalReason: stringValue(event.payload.refusal_reason) ?? "REFUSED",
      traceId: stringValue(event.payload.trace_id),
      errorCode: null,
    };
  if (event.stage === "failure" && event.terminal)
    return {
      status: "failure",
      answer: null,
      citations: [],
      refusalReason: null,
      traceId: null,
      errorCode: stringValue(event.payload.error_code) ?? "INTERNAL_ERROR",
    };
  return {
    ...state,
    status: "progress",
    stage:
      event.stage === "started" ||
      event.stage === "retrieving" ||
      event.stage === "selecting_evidence" ||
      event.stage === "generating"
        ? event.stage
        : state.stage,
  };
}

export function interruptedQuestionState(state: QuestionState): QuestionState {
  if (
    state.status === "final" ||
    state.status === "refusal" ||
    state.status === "failure"
  )
    return state;
  return {
    ...state,
    status: "interrupted",
    answer: null,
    citations: [],
    errorCode: "STREAM_INTERRUPTED",
  };
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export type DocumentWithJob = DocumentResponse & {
  job?: IngestionJobStatusResponse;
};
export type {
  CitationResponse,
  DocumentResponse,
  IngestionJobStatusResponse,
  QuestionResponse,
};
