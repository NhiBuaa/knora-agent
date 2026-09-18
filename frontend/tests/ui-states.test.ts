import { describe, expect, it } from "vitest";
import { questionStateReducer, initialQuestionState } from "@/lib/ui-states";

describe("question state", () => {
  it("shows only a final_validated event as a cited answer", () => {
    const state = questionStateReducer(initialQuestionState, {
      stage: "final_validated", terminal: true,
      payload: { answer: "The answer", decision: "ANSWER", trace_id: "trace-1", workspace_id: "ws-1", citations: [{ evidence_id: "E1", excerpt: "source" }] },
    });
    expect(state.status).toBe("final");
    expect(state.answer).toBe("The answer");
    expect(state.citations).toHaveLength(1);
  });

  it("never exposes citations for refusal", () => {
    const state = questionStateReducer(initialQuestionState, {
      stage: "refusal", terminal: true,
      payload: { refusal_reason: "INSUFFICIENT_EVIDENCE", trace_id: "trace-2" },
    });
    expect(state.status).toBe("refusal");
    expect(state.citations).toEqual([]);
  });
});
