import React from "react";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { EvaluationView } from "../../components/operator/EvaluationView";
import { OperationsView } from "../../components/operator/OperationsView";
import { ToolObservationView } from "../../components/operator/ToolObservationView";
import { TraceView } from "../../components/operator/TraceView";
afterEach(cleanup);

describe("operator views", () => {
  it("renders an unavailable evaluation without inventing a score", () => {
    render(
      <EvaluationView
        evaluation={{
          availability: "unavailable",
          observation_failure: "EVALUATION_REPORT_UNAVAILABLE",
          report_id: "report-1",
          workspace_id: "ws-1",
        }}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Evaluation report unavailable" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /download/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("EVALUATION_REPORT_UNAVAILABLE"),
    ).toBeInTheDocument();
    expect(screen.getByText("Observation code")).toBeInTheDocument();
  });

  it("does not display sensitive provider fields from operational payloads", () => {
    render(
      <OperationsView
        operations={{
          configuration_version: "ops-v1",
          histograms: { retrieval_latency_ms: { count: 1, sum: 0 } },
          metrics: {
            provider_api_key: "do-not-render",
            retrieval_latency_ms: {
              value: 0,
              provider_api_key: "nested-secret",
            },
          },
          workspace_id: "ws-1",
        }}
      />,
    );

    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.queryByText("do-not-render")).not.toBeInTheDocument();
    expect(screen.queryByText("nested-secret")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Unavailable in the current Operator contract.",
    );
  });

  it("renders M4 observations as read-only lifecycle evidence", () => {
    render(
      <ToolObservationView
        state="indeterminate_external_outcome"
        detail="Awaiting reconciliation"
      />,
    );

    expect(
      screen.getByText("Indeterminate external outcome"),
    ).toBeInTheDocument();
    expect(screen.getByText("Awaiting reconciliation")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /approve|execute/i }),
    ).not.toBeInTheDocument();
  });

  it("renders an explicit unavailable state when no M4 relation is supplied", () => {
    render(<ToolObservationView />);

    expect(screen.getByText("M4 observation unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(
        "No authorized lifecycle relation was supplied by the backend.",
      ),
    ).toBeInTheDocument();
  });

  it("renders the backend lifecycle observation on a trace detail view", () => {
    render(
      <TraceView
        trace={{
          alias_mapping: {},
          branch_observation_schema_version: 1,
          branch_observations: [
            {
              branch: "tool",
              status: "approved",
              detail: "Backend recorded approval",
            },
          ],
          candidate_decisions: [],
          candidates: [],
          chunk_set_ids: [],
          decision: "ANSWER",
          embedding_configuration_id: "embed-v1",
          embedding_set_ids: [],
          parsed_markers: [],
          provider_metadata: {},
          retrieval_configuration_id: "retrieval-v1",
          retrieval_latency_ms: 0,
          trace_id: "trace-1",
          trace_schema_version: 2,
          validation_outcome: "valid",
          workspace_id: "ws-1",
        }}
      />,
    );

    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.getByText("Backend recorded approval")).toBeInTheDocument();
  });

  it("keeps candidate source locator and measured zero distinct from missing metadata", () => {
    render(
      <TraceView
        trace={{
          alias_mapping: { E1: "chunk-1" },
          branch_observation_schema_version: 1,
          branch_observations: [],
          candidate_decisions: [{ chunk_id: "chunk-1", reason: "SELECTED" }],
          candidates: [
            {
              chunk_id: "chunk-1",
              chunk_ordinal: 2,
              chunk_set_id: "set-1",
              content: "Evidence text",
              document_version_id: "version-1",
              end_line: 9,
              final_decision: "SELECTED",
              final_rank: 1,
              fusion_score: 0,
              source_key: "manual.pdf",
              start_line: 7,
              workspace_id: "ws-1",
            },
          ],
          chunk_set_ids: ["set-1"],
          decision: "answer",
          embedding_configuration_id: "embed-v1",
          embedding_set_ids: [],
          parsed_markers: ["E1"],
          provider_metadata: {
            generation: {
              cost: {
                amount_usd: "0.012",
                currency: "USD",
                pricing_version: "price-v2",
              },
              usage: { prompt_tokens: 10, completion_tokens: 5 },
            },
            timing: {
              clock_resolution_ms: 0.001,
              phases: { generation: { duration_ms: 27 } },
            },
          },
          retrieval_configuration_id: "retrieval-v1",
          retrieval_latency_ms: 0,
          trace_id: "trace-1",
          trace_schema_version: 2,
          validation_outcome: "valid",
          workspace_id: "ws-1",
        }}
      />,
    );
    expect(
      within(
        screen.getByRole("region", { name: "Candidate provenance" }),
      ).getByText("manual.pdf"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("0 ms").length).toBeGreaterThan(0);
    expect(screen.getByText("Lines 7-9")).toBeInTheDocument();
    expect(screen.getByText("Evidence text")).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Observed result" }))
        .getByText("ANSWER")
        .closest(".kn-status-badge"),
    ).toHaveAttribute("data-kind", "success");
    expect(screen.getByText("0.012 USD")).toBeInTheDocument();
    expect(screen.getByText("price-v2")).toBeInTheDocument();
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
    expect(screen.getByText("27 ms")).toBeInTheDocument();
    expect(screen.getByText("0.001 ms")).toBeInTheDocument();
    expect(
      within(
        screen.getByRole("region", { name: "Citation mapping" }),
      ).getByText("E1"),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("chunk-1", { selector: "dd code" }).length,
    ).toBeGreaterThan(0);
  });
});
