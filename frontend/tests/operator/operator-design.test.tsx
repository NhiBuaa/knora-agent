import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OperationsView } from "../../components/operator/OperationsView";
import { ToolObservationView } from "../../components/operator/ToolObservationView";

describe("operator operations presentation", () => {
  it("shows measured operational metrics and leaves absent observations unavailable", () => {
    render(
      <OperationsView
        operations={{
          configuration_version: "ops-v1",
          histograms: {
            claim_latency: {
              count: 2,
              sum: 0.03,
              buckets: [
                [0.01, 1],
                [0.05, 2],
              ],
            },
          },
          metrics: { queue_depth: 0, cleanup_failure_total: 2 },
          workspace_id: "ws-1",
        }}
      />,
    );
    expect(screen.getByText("Queue depth")).toBeInTheDocument();
    expect(screen.getByText("0", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText("Cleanup failures")).toBeInTheDocument();
    expect(screen.getAllByText("2", { selector: "dd" }).length).toBeGreaterThan(
      0,
    );
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.getByText("Claim latency sum")).toBeInTheDocument();
    expect(screen.getByText("0.01 s")).toBeInTheDocument();
  });

  it("keeps an indeterminate tool outcome distinct from success", () => {
    render(
      <ToolObservationView
        state="indeterminate_external_outcome"
        detail="Awaiting reconciliation"
      />,
    );
    expect(
      screen.getByText("Indeterminate external outcome"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Succeeded")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Execute" }),
    ).not.toBeInTheDocument();
  });
});
