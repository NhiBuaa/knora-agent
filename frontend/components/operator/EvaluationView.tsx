import React from "react";
import type { OperatorEvaluationResponse } from "../../generated/knora-openapi";
import { observationState } from "../../lib/operator/presentation";
import { Notice } from "@/components/ui/Notice";
import { StatusBadge } from "@/components/ui/StatusBadge";

export function EvaluationView({
  evaluation,
}: {
  evaluation: OperatorEvaluationResponse;
}) {
  const state = observationState(evaluation);
  return (
    <section aria-labelledby="evaluation-heading">
      <h1 id="evaluation-heading">Evaluation report</h1>
      <StatusBadge kind={state.tone === "normal" ? "success" : "warning"}>
        {state.tone === "normal"
          ? "Evaluation available"
          : "Evaluation unavailable"}
      </StatusBadge>
      <dl>
        <dt>Report ID</dt>
        <dd>
          <code>{evaluation.report_id}</code>
        </dd>
        <dt>Observed Workspace</dt>
        <dd>
          <code>{evaluation.workspace_id}</code>
        </dd>
      </dl>
      {state.detail && (
        <Notice kind="warning" title="Observation failed">
          <details>
            <summary>Technical details</summary>
            <code>{state.detail}</code>
          </details>
        </Notice>
      )}
    </section>
  );
}
