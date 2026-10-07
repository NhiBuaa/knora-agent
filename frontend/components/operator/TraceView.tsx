import React from "react";
import type { OperatorTraceResponse } from "../../generated/knora-openapi";
import {
  presentMetric,
  projectedAccounting,
  projectedTiming,
} from "../../lib/operator/presentation";
import { ToolObservationView } from "./ToolObservationView";
import { StatusBadge } from "@/components/ui/StatusBadge";

const LIFECYCLE_STATES = new Set([
  "proposed",
  "approved",
  "rejected",
  "executing",
  "succeeded",
  "failed",
  "reconciliation",
  "indeterminate_external_outcome",
]);
const heading = "m-0 font-display text-xl leading-6 font-semibold";

function displayMilliseconds(value: string) {
  const match = /^(-?\d+(?:\.\d+)?) ms$/.exec(value);
  if (!match) return value;
  return `${new Intl.NumberFormat("en", { maximumFractionDigits: 3 }).format(Number(match[1]))} ms`;
}

function ContextRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid min-h-[38px] grid-cols-[minmax(0,170px)_minmax(0,1fr)] items-start gap-2.5 border-b border-border pt-[7px] pb-[13px] text-[13px] leading-[17px] max-sm:grid-cols-1">
      <dt className="font-normal text-text-muted">{label}</dt>
      <dd className="min-w-0 [overflow-wrap:anywhere]">{children}</dd>
    </div>
  );
}

export function TraceView({ trace }: { trace: OperatorTraceResponse }) {
  const latency = presentMetric(trace.retrieval_latency_ms);
  const embedding = projectedAccounting(trace.provider_metadata.embedding);
  const generation = projectedAccounting(trace.provider_metadata.generation);
  const timing = projectedTiming(trace.provider_metadata.timing);
  const lifecycleObservation = trace.branch_observations.find((observation) => {
    const state =
      typeof observation.lifecycle === "string"
        ? observation.lifecycle
        : typeof observation.state === "string"
          ? observation.state
          : typeof observation.status === "string"
            ? observation.status
            : undefined;
    return state !== undefined && LIFECYCLE_STATES.has(state);
  });
  const lifecycleState = lifecycleObservation
    ? typeof lifecycleObservation.lifecycle === "string"
      ? lifecycleObservation.lifecycle
      : typeof lifecycleObservation.state === "string"
        ? lifecycleObservation.state
        : (lifecycleObservation.status as string)
    : undefined;
  const lifecycleDetail = lifecycleObservation
    ? typeof lifecycleObservation.detail === "string"
      ? lifecycleObservation.detail
      : typeof lifecycleObservation.failure_code === "string"
        ? lifecycleObservation.failure_code
        : undefined
    : undefined;
  const answer = trace.decision.toUpperCase() === "ANSWER";
  return (
    <article
      aria-labelledby="trace-summary-heading"
      className="mt-5 mb-0 border-0 bg-transparent p-0"
    >
      <h2 id="trace-summary-heading" className={heading}>
        Trace summary
      </h2>
      <dl
        role="group"
        aria-label="Trace summary signals"
        className="mt-2.5 mb-0 grid grid-cols-4 gap-0 border-y border-border max-md:grid-cols-2"
      >
        {[
          ["Decision", trace.decision.toUpperCase(), answer],
          [
            "Validation outcome",
            trace.validation_outcome.toUpperCase(),
            trace.validation_outcome.toUpperCase() === "VALID",
          ],
          [
            "Retrieval latency",
            latency.state === "available"
              ? `${latency.value} ms`
              : latency.value,
            false,
          ],
          ["Candidates", String(trace.candidates.length), false],
        ].map(([label, value, success]) => (
          <div
            key={String(label)}
            className="min-h-[82px] min-w-0 border-r border-border px-[18px] pt-[14px] pb-[18px]"
          >
            <dt className="text-[13px] leading-[17px] font-normal text-text-muted [overflow-wrap:anywhere]">
              {label}
            </dt>
            <dd
              title={String(value)}
              className={`mt-[7px] text-[22px] leading-[26px] font-semibold [overflow-wrap:anywhere] ${success ? "text-action-text" : "text-text-primary"}`}
            >
              {displayMilliseconds(String(value))}
            </dd>
          </div>
        ))}
      </dl>
      <div className="mt-6 grid grid-cols-[minmax(0,780px)_minmax(0,380px)] gap-10 max-lg:grid-cols-1 max-lg:gap-8">
        <div className="min-w-0">
          <section
            aria-labelledby="observed-result-heading"
            className="m-0 border-0 bg-transparent p-0"
          >
            <div className="flex max-w-[760px] flex-wrap items-start justify-between gap-3">
              <h2 id="observed-result-heading" className={heading}>
                Observed result
              </h2>
              <StatusBadge
                kind={answer ? "success" : "warning"}
                className={
                  answer
                    ? "h-7 w-[110px] shrink-0 rounded-[7px]! border-0 px-2.5 py-0 text-xs leading-4 font-semibold whitespace-nowrap [&_[aria-hidden]]:hidden"
                    : "max-w-full [overflow-wrap:anywhere]"
                }
              >
                {trace.decision.toUpperCase()}
              </StatusBadge>
            </div>
            {trace.refusal_reason && (
              <p
                role="status"
                className="mt-2 mb-0 text-sm leading-5 text-signature"
              >
                Refusal: {trace.refusal_reason}
              </p>
            )}
            <p className="mt-1.5 mb-0 max-w-[630px] text-sm leading-5">
              {trace.answer ??
                (trace.refusal_reason
                  ? "No answer was returned."
                  : "Answer unavailable in this trace.")}
            </p>
            <div className="mt-2 flex min-h-6 flex-wrap items-center gap-2 text-xs leading-4 text-text-muted">
              <span>Citations</span>
              {trace.parsed_markers.length ? (
                trace.parsed_markers.map((marker) => (
                  <span
                    key={marker}
                    className="flex min-h-[22px] min-w-[38px] items-center justify-center rounded-full border border-border bg-surface-subtle px-2 font-medium"
                  >
                    {marker}
                  </span>
                ))
              ) : (
                <span>Unavailable</span>
              )}
            </div>
          </section>
          <section
            aria-labelledby="candidate-heading"
            className="mt-5 mb-0 border-0 bg-transparent p-0"
          >
            <h2 id="candidate-heading" className={heading}>
              Candidate provenance
            </h2>
            <p className="mt-1.5 mb-0 max-w-[730px] text-[13px] leading-[18px] text-text-muted">
              Ranked evidence considered by retrieval. Selected passages keep
              their source, score, and excerpt inspectable.
            </p>
            {trace.candidates.length === 0 && (
              <p className="mt-4 text-sm">No candidates in this trace.</p>
            )}
            <ol className="mt-4 mb-0 grid list-none gap-2 p-0">
              {trace.candidates.map((candidate) => (
                <li
                  key={candidate.chunk_id}
                  className="m-0 min-h-[102px] max-w-[760px] border-b border-border pt-1 pb-[21px]"
                >
                  <div className="flex min-h-7 flex-wrap items-start justify-between gap-3">
                    <strong className="mt-[3px] min-w-0 max-w-[420px] text-[15px] leading-5 font-semibold [overflow-wrap:anywhere]">
                      {candidate.source_key}
                    </strong>
                    <StatusBadge
                      className={
                        candidate.final_decision === "SELECTED"
                          ? "h-7 w-[150px] shrink-0 rounded-[7px]! border-0 px-2.5 py-0 text-xs leading-4 font-semibold whitespace-nowrap [&_[aria-hidden]]:hidden"
                          : "max-w-full [overflow-wrap:anywhere]"
                      }
                      kind={
                        candidate.final_decision === "SELECTED"
                          ? "success"
                          : "info"
                      }
                    >
                      {candidate.final_decision}
                    </StatusBadge>
                  </div>
                  <p className="mt-px mb-0 min-h-[17px] text-xs leading-4 text-text-muted [overflow-wrap:anywhere]">
                    Chunk {candidate.chunk_ordinal} ·{" "}
                    <span>
                      Lines {candidate.start_line}-{candidate.end_line}
                    </span>{" "}
                    · Rank {candidate.final_rank} · Fusion{" "}
                    {presentMetric(candidate.fusion_score).value}
                  </p>
                  <p className="mt-2.5 mb-0 min-h-5 max-w-[610px] text-[13px] leading-[18px] [overflow-wrap:anywhere]">
                    {candidate.content}
                  </p>
                  <details className="mt-2 text-xs leading-[18px] text-text-muted">
                    <summary>Retrieval details</summary>
                    <dl className="m-0 block">
                      <ContextRow label="Chunk ID">
                        <code>{candidate.chunk_id}</code>
                      </ContextRow>
                      <ContextRow label="Document Version">
                        <code>{candidate.document_version_id}</code>
                      </ContextRow>
                      <ContextRow label="Chunk Set">
                        <code>{candidate.chunk_set_id}</code>
                      </ContextRow>
                      <ContextRow label="Fusion score">
                        {presentMetric(candidate.fusion_score).value}
                      </ContextRow>
                      <ContextRow label="Decision reason">
                        {candidate.decision_reason ?? "Unavailable"}
                      </ContextRow>
                      <ContextRow label="Vector contribution">
                        <code>
                          {candidate.vector_contribution
                            ? JSON.stringify(candidate.vector_contribution)
                            : "Unavailable"}
                        </code>
                      </ContextRow>
                      <ContextRow label="Full-text contribution">
                        <code>
                          {candidate.fts_contribution
                            ? JSON.stringify(candidate.fts_contribution)
                            : "Unavailable"}
                        </code>
                      </ContextRow>
                    </dl>
                  </details>
                </li>
              ))}
            </ol>
          </section>
          <details className="mt-5 text-sm">
            <summary>M4 lifecycle evidence</summary>
            <ToolObservationView
              state={lifecycleState}
              detail={lifecycleDetail}
            />
            <p className="text-xs text-text-muted">
              Branch observation schema:{" "}
              {trace.branch_observation_schema_version}
            </p>
            <ol className="list-none p-0">
              {trace.branch_observations.map((observation, index) => (
                <li key={index} className="m-0 py-2">
                  <code className="text-xs [overflow-wrap:anywhere]">
                    {JSON.stringify(observation)}
                  </code>
                </li>
              ))}
            </ol>
          </details>
          {trace.candidate_decisions.length > 0 && (
            <details className="mt-3 text-sm">
              <summary>Candidate decisions</summary>
              <ol>
                {trace.candidate_decisions.map((decision, index) => (
                  <li key={index}>
                    <code className="text-xs [overflow-wrap:anywhere]">
                      {JSON.stringify(decision)}
                    </code>
                  </li>
                ))}
              </ol>
            </details>
          )}
        </div>
        <aside className="min-w-0">
          <section
            aria-labelledby="trace-context-heading"
            className="m-0 border-0 bg-transparent p-0"
          >
            <h2 id="trace-context-heading" className={heading}>
              Trace context
            </h2>
            <dl className="mt-2.5 mb-0 block">
              <ContextRow label="Trace ID">
                <code>{trace.trace_id}</code>
              </ContextRow>
              <ContextRow label="Retrieval configuration">
                <span className="font-medium">
                  {trace.retrieval_configuration_id}
                </span>
              </ContextRow>
              <ContextRow label="Embedding configuration">
                <span className="font-medium">
                  {trace.embedding_configuration_id}
                </span>
              </ContextRow>
              <ContextRow label="Trace schema">
                {presentMetric(trace.trace_schema_version).state === "available"
                  ? `v${trace.trace_schema_version}`
                  : "Unavailable"}
              </ContextRow>
            </dl>
          </section>
          <section
            aria-labelledby="citation-mapping-heading"
            className="mt-5 mb-0 border-0 bg-transparent p-0"
          >
            <h3
              id="citation-mapping-heading"
              className="m-0 font-display text-lg leading-[22px] font-semibold"
            >
              Citation mapping
            </h3>
            <dl className="mt-1 mb-0 block">
              {Object.entries(trace.alias_mapping).map(([alias, chunkId]) => {
                const source = trace.candidates.find(
                  (candidate) => candidate.chunk_id === chunkId,
                );
                return (
                  <div
                    key={alias}
                    className="grid grid-cols-[48px_minmax(0,1fr)] gap-2.5 py-1 text-[13px] leading-[18px]"
                  >
                    <dt className="font-normal text-text-muted">{alias}</dt>
                    <dd className="min-w-0 [overflow-wrap:anywhere]">
                      <code>
                        {typeof chunkId === "string" ? chunkId : "Unavailable"}
                      </code>
                      <p className="m-0">
                        {source?.source_key ?? "Source unavailable"}
                      </p>
                    </dd>
                  </div>
                );
              })}
            </dl>
            {!Object.keys(trace.alias_mapping).length && (
              <p className="mt-1 text-[13px] text-text-muted">
                Citation mapping unavailable.
              </p>
            )}
          </section>
          <section
            aria-labelledby="phase-timing-heading"
            className="mt-2.5 mb-0 border-0 bg-transparent p-0"
          >
            <h3
              id="phase-timing-heading"
              className="m-0 font-display text-lg leading-[22px] font-semibold"
            >
              Phase timing
            </h3>
            <dl className="mt-0 mb-0 block">
              {timing.phases.map((phase) => (
                <div
                  key={phase.name}
                  className="grid min-h-[26px] grid-cols-[minmax(0,1fr)_100px] items-center gap-3 border-b border-border text-[13px]"
                >
                  <dt className="font-normal capitalize">
                    {phase.name.replaceAll("_", " ")}
                  </dt>
                  <dd title={phase.duration} className="font-semibold">
                    {displayMilliseconds(phase.duration)}
                  </dd>
                </div>
              ))}
            </dl>
            {!timing.phases.length && (
              <p className="mt-1 text-[13px] text-text-muted">
                Phase timing unavailable.
              </p>
            )}
          </section>
          <details className="mt-4 text-sm">
            <summary>Additional provenance</summary>
            <dl className="m-0 block">
              <ContextRow label="Observed Workspace">
                <code>{trace.workspace_id}</code>
              </ContextRow>
              <ContextRow label="Chunk Sets">
                {Array.isArray(trace.chunk_set_ids)
                  ? trace.chunk_set_ids.join(", ") || "Unavailable"
                  : "Unavailable"}
              </ContextRow>
              <ContextRow label="Embedding Sets">
                {Array.isArray(trace.embedding_set_ids)
                  ? trace.embedding_set_ids.join(", ") || "Unavailable"
                  : "Unavailable"}
              </ContextRow>
              <ContextRow label="Clock resolution">
                {timing.resolution}
              </ContextRow>
            </dl>
          </details>
          <details className="mt-3 text-sm">
            <summary>Provider accounting</summary>
            <dl className="m-0 block">
              <ContextRow label="Embedding cost">{embedding.amount}</ContextRow>
              <ContextRow label="Embedding pricing">
                {embedding.pricingVersion}
              </ContextRow>
              <ContextRow label="Embedding usage">{embedding.usage}</ContextRow>
              <ContextRow label="Generation cost">
                {generation.amount}
              </ContextRow>
              <ContextRow label="Generation pricing">
                {generation.pricingVersion}
              </ContextRow>
              <ContextRow label="Generation usage">
                {generation.usage}
              </ContextRow>
            </dl>
          </details>
        </aside>
      </div>
    </article>
  );
}
