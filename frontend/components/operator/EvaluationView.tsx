import React from "react";
import type { OperatorEvaluationResponse } from "../../generated/knora-openapi";
import { observationState } from "../../lib/operator/presentation";

export function EvaluationView({
  evaluation,
}: {
  evaluation: OperatorEvaluationResponse;
}) {
  const state = observationState(evaluation);
  return (
    <section aria-labelledby="evaluation-heading">
      <h2 id="evaluation-heading">Evaluation report</h2>
      <p data-tone={state.tone}>
        {state.tone === "normal"
          ? "Evaluation available"
          : "Evaluation unavailable"}
      </p>
      <p>
        Report: <code>{evaluation.report_id}</code>
      </p>
      {state.detail && <p role="status">{state.detail}</p>}
      {state.tone === "normal" && (
        <p>Evaluation data is available from the backend projection.</p>
      )}
    </section>
  );
}
