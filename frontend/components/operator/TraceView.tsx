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
  return (
    <article aria-labelledby="trace-heading">
      <h1 id="trace-heading">Question trace</h1>
      <StatusBadge
        kind={trace.decision.toUpperCase() === "ANSWER" ? "success" : "warning"}
      >
        {trace.decision}
      </StatusBadge>
      <dl>
        <dt>Trace ID</dt>
        <dd>
          <code>{trace.trace_id}</code>
        </dd>
        <dt>Observed Workspace</dt>
        <dd>
          <code>{trace.workspace_id}</code>
        </dd>
        <dt>Retrieval configuration</dt>
        <dd>
          <code>{trace.retrieval_configuration_id}</code>
        </dd>
        <dt>Embedding configuration</dt>
        <dd>
          <code>{trace.embedding_configuration_id}</code>
        </dd>
        <dt>Validation outcome</dt>
        <dd>{trace.validation_outcome}</dd>
      </dl>
      {trace.refusal_reason && (
        <p role="status">Refusal: {trace.refusal_reason}</p>
      )}
      {trace.answer && <p>{trace.answer}</p>}
      <p>
        Retrieval latency:{" "}
        <span data-state={latency.state}>
          {latency.state === "available"
            ? `${latency.value} ms`
            : latency.value}
        </span>
      </p>
      <details>
        <summary>Phase timing</summary>
        <dl>
          <dt>Clock resolution</dt>
          <dd>{timing.resolution}</dd>
          {timing.phases.map((phase) => (
            <React.Fragment key={phase.name}>
              <dt>{phase.name.replaceAll("_", " ")}</dt>
              <dd>{phase.duration}</dd>
            </React.Fragment>
          ))}
        </dl>
      </details>
      <details>
        <summary>Citation mapping</summary>
        <p>
          Parsed markers:{" "}
          {trace.parsed_markers.length
            ? trace.parsed_markers.join(", ")
            : "Unavailable"}
        </p>
        <dl>
          {Object.entries(trace.alias_mapping).map(([alias, chunkId]) => (
            <React.Fragment key={alias}>
              <dt>{alias}</dt>
              <dd>
                <code>
                  {typeof chunkId === "string" ? chunkId : "Unavailable"}
                </code>
              </dd>
            </React.Fragment>
          ))}
        </dl>
      </details>
      <details>
        <summary>Provider accounting</summary>
        <dl>
          <dt>Embedding cost</dt>
          <dd>{embedding.amount}</dd>
          <dt>Embedding pricing</dt>
          <dd>{embedding.pricingVersion}</dd>
          <dt>Embedding usage</dt>
          <dd>{embedding.usage}</dd>
          <dt>Generation cost</dt>
          <dd>{generation.amount}</dd>
          <dt>Generation pricing</dt>
          <dd>{generation.pricingVersion}</dd>
          <dt>Generation usage</dt>
          <dd>{generation.usage}</dd>
        </dl>
      </details>
      <ToolObservationView state={lifecycleState} detail={lifecycleDetail} />
      <h3>Candidate provenance</h3>
      {trace.candidates.length === 0 && <p>No candidates in this trace.</p>}
      <ol>
        {trace.candidates.map((candidate) => (
          <li key={candidate.chunk_id}>
            <p>
              <strong>{candidate.source_key}</strong>{" "}
              <StatusBadge
                kind={
                  candidate.final_decision === "SELECTED" ? "success" : "info"
                }
              >
                {candidate.final_decision}
              </StatusBadge>
            </p>
            <p>
              Chunk {candidate.chunk_ordinal} ·{" "}
              <span>
                Lines {candidate.start_line}-{candidate.end_line}
              </span>{" "}
              · Rank {candidate.final_rank}
            </p>
            <p>{candidate.content}</p>
            <details>
              <summary>Retrieval details</summary>
              <dl>
                <dt>Chunk ID</dt>
                <dd>
                  <code>{candidate.chunk_id}</code>
                </dd>
                <dt>Document Version</dt>
                <dd>
                  <code>{candidate.document_version_id}</code>
                </dd>
                <dt>Fusion score</dt>
                <dd>{candidate.fusion_score}</dd>
                <dt>Decision reason</dt>
                <dd>{candidate.decision_reason ?? "Unavailable"}</dd>
                <dt>Vector contribution</dt>
                <dd>
                  <code>
                    {candidate.vector_contribution
                      ? JSON.stringify(candidate.vector_contribution)
                      : "Unavailable"}
                  </code>
                </dd>
                <dt>Full-text contribution</dt>
                <dd>
                  <code>
                    {candidate.fts_contribution
                      ? JSON.stringify(candidate.fts_contribution)
                      : "Unavailable"}
                  </code>
                </dd>
              </dl>
            </details>
          </li>
        ))}
      </ol>
      {trace.candidate_decisions.length > 0 && (
        <details>
          <summary>Candidate decisions</summary>
          <ol>
            {trace.candidate_decisions.map((decision, index) => (
              <li key={index}>
                <code>{JSON.stringify(decision)}</code>
              </li>
            ))}
          </ol>
        </details>
      )}
    </article>
  );
}
