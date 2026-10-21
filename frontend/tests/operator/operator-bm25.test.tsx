import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import type { OperatorTraceResponse } from "../../generated/knora-openapi";
import { TraceView } from "../../components/operator/TraceView";
import { isOperatorTrace } from "../../lib/operator/api";

afterEach(cleanup);

const lexicalTrace: OperatorTraceResponse = {
  trace_id: "lexical-trace",
  workspace_id: "workspace",
  retrieval_configuration_id: "retrieval-bm25-diagnostic-v1",
  embedding_configuration_id: null,
  embedding_set_ids: [],
  chunk_set_ids: ["chunks"],
  trace_schema_version: 3,
  branch_observation_schema_version: 2,
  candidate_decisions: [],
  branch_observations: [],
  decision: "ANSWER",
  answer: "Hạn mức 42. [[E1]]",
  alias_mapping: { E1: "chunk" },
  parsed_markers: ["E1"],
  validation_outcome: "valid",
  retrieval_latency_ms: 0,
  provider_metadata: {
    embedding: { status: "not_run" },
    retrieval: { mode: "bm25-only" },
  },
  candidates: [
    {
      chunk_id: "chunk",
      document_version_id: "version",
      chunk_set_id: "chunks",
      source_key: "policy.pdf",
      chunk_ordinal: 0,
      workspace_id: "workspace",
      content: "Hạn mức 42.",
      start_line: 1,
      end_line: 1,
      final_rank: 1,
      final_decision: "SELECTED",
      fusion_score: null,
      vector_contribution: null,
      fts_contribution: null,
      bm25_contribution: {
        raw_score: 0,
        branch_rank: 1,
        index_generation_id: "generation",
      },
    },
  ],
};

describe("BM25 operator contract", () => {
  it("accepts explicit null embedding provenance but rejects a missing field", () => {
    expect(isOperatorTrace(lexicalTrace)).toBe(true);
    expect(
      isOperatorTrace({
        ...lexicalTrace,
        embedding_configuration_id: undefined,
      }),
    ).toBe(false);
    expect(
      isOperatorTrace({ ...lexicalTrace, embedding_configuration_id: 7 }),
    ).toBe(false);
    expect(
      isOperatorTrace({
        ...lexicalTrace,
        embedding_configuration_id: "dense-profile",
      }),
    ).toBe(true);
  });

  it("shows a measured zero raw BM25 score and its full generation provenance", () => {
    render(<TraceView trace={lexicalTrace} />);
    expect(screen.getByText(/Rank 1 · BM25 raw 0/)).toBeVisible();
    const details = screen.getByText("Retrieval details").closest("details")!;
    details.open = true;
    const provenance = within(details);
    expect(provenance.getByText("BM25 raw score")).toBeVisible();
    expect(provenance.getByText("BM25 contribution")).toBeVisible();
    expect(
      provenance.getByText(/"index_generation_id":"generation"/),
    ).toBeVisible();
    expect(provenance.queryByText("Fusion score")).not.toBeInTheDocument();
    const context = screen.getByRole("heading", {
      name: "Trace context",
    }).parentElement!;
    expect(within(context).getByText("Not run")).toBeVisible();
    expect(screen.getByText("Hạn mức 42.")).toBeVisible();
  });

  it("does not coerce malformed BM25 raw scores into measured values", () => {
    const candidate = lexicalTrace.candidates[0];
    render(
      <TraceView
        trace={{
          ...lexicalTrace,
          candidates: [
            {
              ...candidate,
              bm25_contribution: {
                ...candidate.bm25_contribution,
                raw_score: "0",
              },
            },
          ],
        }}
      />,
    );
    expect(screen.getByText(/Rank 1 · BM25 raw Unavailable/)).toBeVisible();
  });
});
