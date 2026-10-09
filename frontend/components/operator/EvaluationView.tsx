import React from "react";
import type { OperatorEvaluationResponse } from "../../generated/knora-openapi";
import { observationState } from "../../lib/operator/presentation";
import { StatusBadge } from "@/components/ui/StatusBadge";

export function EvaluationView({
  evaluation,
}: {
  evaluation: OperatorEvaluationResponse;
}) {
  const state = observationState(evaluation);
  const available = state.tone === "normal";
  const contractUnavailable =
    evaluation.observation_failure === "EVALUATION_REPORT_UNAVAILABLE";
  const rows = [
    ["Report ID", evaluation.report_id],
    ["Observed Workspace", evaluation.workspace_id],
    ["Availability", available ? "Available" : "Unavailable"],
    ["Observation code", evaluation.observation_failure ?? "Unavailable"],
  ];
  return (
    <section
      aria-labelledby="evaluation-heading"
      className="mt-[33px] mb-0 grid grid-cols-[minmax(0,760px)_minmax(0,380px)] gap-[60px] border-0 bg-transparent p-0 max-lg:grid-cols-1 max-lg:gap-8"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-[18px]">
          <h2
            id="evaluation-heading"
            className="m-0 font-sans text-[26px] leading-8 font-semibold"
          >
            Evaluation report {available ? "available" : "unavailable"}
          </h2>
          <StatusBadge
            kind={available ? "success" : "warning"}
            className={
              available
                ? undefined
                : "h-7 w-[92px] shrink-0 justify-center rounded-lg px-2 font-semibold whitespace-nowrap [&_[aria-hidden]]:hidden"
            }
          >
            {available ? "Available" : "Unavailable"}
          </StatusBadge>
        </div>
        <p className="mt-3 mb-0 min-h-[70px] max-w-[680px] text-base leading-5 text-text-muted">
          {contractUnavailable
            ? "Persisted evaluation reports are not available in the current Operator contract. Knora does not invent quality scores, pass/fail results, or other evaluation metrics when the backend has no report to expose."
            : available
              ? "The backend reports this evaluation as available. No evaluation metrics are supplied by this observation."
              : "The backend could not supply this evaluation report. No evaluation metrics are available for this observation."}
        </p>
      </div>
      <section
        aria-labelledby="report-context-heading"
        className="m-0 min-w-0 border-0 bg-transparent p-0"
      >
        <h2
          id="report-context-heading"
          className="m-0 font-sans text-[22px] leading-6 font-semibold"
        >
          Report context
        </h2>
        <dl className="mt-2.5 mb-0 block">
          {rows.map(([label, value]) => (
            <div
              key={label}
              className="grid min-h-10 grid-cols-[minmax(0,170px)_minmax(0,1fr)] items-start gap-2.5 border-b border-border pt-2.5 pb-[5px] text-sm leading-6 max-sm:grid-cols-1"
            >
              <dt className="font-normal text-text-muted">{label}</dt>
              <dd
                data-source-overflow={
                  label === "Observation code" ? "figma" : undefined
                }
                className={`min-w-0 [overflow-wrap:anywhere] ${label === "Availability" && !available ? "font-semibold text-signature" : label === "Observation code" ? "text-xs leading-6 text-text-muted min-[1200px]:min-w-[300px]" : "font-medium"}`}
              >
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </section>
    </section>
  );
}
