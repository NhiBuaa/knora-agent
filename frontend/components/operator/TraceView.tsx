import React from "react";
import type { OperatorTraceResponse } from "../../generated/knora-openapi";
import { presentMetric } from "../../lib/operator/presentation";

export function TraceView({ trace }: { trace: OperatorTraceResponse }) {
  const latency = presentMetric(trace.retrieval_latency_ms);
  return (
    <article aria-labelledby="trace-heading">
      <h2 id="trace-heading">Question trace</h2>
      <p>Trace: <code>{trace.trace_id}</code></p>
      <p>Decision: {trace.decision}</p>
      {trace.refusal_reason && <p role="status">Refusal: {trace.refusal_reason}</p>}
      <p>Retrieval latency: <span data-state={latency.state}>{latency.value}</span></p>
      <p>Retrieval configuration: <code>{trace.retrieval_configuration_id}</code></p>
      <h3>Candidate provenance</h3>
      <ol>
        {trace.candidates.map((candidate) => (
          <li key={candidate.chunk_id}>
            <code>{candidate.source_key}#{candidate.chunk_ordinal}</code> — {candidate.final_decision}
          </li>
        ))}
      </ol>
    </article>
  );
}
