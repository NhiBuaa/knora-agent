import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvaluationView } from "../../components/operator/EvaluationView";
import { OperationsView } from "../../components/operator/OperationsView";
import { ToolObservationView } from "../../components/operator/ToolObservationView";

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

    expect(screen.getByText("Evaluation unavailable")).toBeInTheDocument();
    expect(screen.queryByText(/score/i)).not.toBeInTheDocument();
    expect(screen.getByText("EVALUATION_REPORT_UNAVAILABLE")).toBeInTheDocument();
  });

  it("does not display sensitive provider fields from operational payloads", () => {
    render(
      <OperationsView
        operations={{
          configuration_version: "ops-v1",
          histograms: { retrieval_latency_ms: { count: 1, sum: 0 } },
          metrics: { provider_api_key: "do-not-render", retrieval_latency_ms: 0 },
          workspace_id: "ws-1",
        }}
      />,
    );

    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.queryByText("do-not-render")).not.toBeInTheDocument();
  });

  it("renders M4 observations as read-only lifecycle evidence", () => {
    render(<ToolObservationView state="indeterminate_external_outcome" detail="Awaiting reconciliation" />);

    expect(screen.getByText("Indeterminate external outcome")).toBeInTheDocument();
    expect(screen.getByText("Awaiting reconciliation")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve|execute/i })).not.toBeInTheDocument();
  });
});
