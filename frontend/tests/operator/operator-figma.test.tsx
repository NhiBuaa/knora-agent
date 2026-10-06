import React from "react";
import {
  render,
  screen,
  within,
  fireEvent,
  cleanup,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { OperatorTraceResponse } from "@/generated/knora-openapi";
import { OperationsView } from "@/components/operator/OperationsView";
import { TraceView } from "@/components/operator/TraceView";
import { EvaluationView } from "@/components/operator/EvaluationView";
import TracesPage from "@/app/operator/traces/page";
import EvaluationsPage from "@/app/operator/evaluations/page";

const push = vi.fn();
vi.stubGlobal("React", React);
afterEach(() => {
  cleanup();
  push.mockClear();
});
vi.mock("next/navigation", () => ({
  usePathname: () => "/operator/traces",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push, refresh: vi.fn() }),
  redirect: (url: string) => {
    throw new Error(url);
  },
}));

const trace: OperatorTraceResponse = {
  trace_id: "trace-1",
  workspace_id: "ws-1",
  trace_schema_version: 2,
  branch_observation_schema_version: 1,
  branch_observations: [],
  retrieval_configuration_id: "retrieval-v1",
  embedding_configuration_id: "embed-v1",
  chunk_set_ids: ["set-1"],
  embedding_set_ids: ["embedding-set-1"],
  retrieval_latency_ms: 0,
  decision: "ANSWER",
  validation_outcome: "valid",
  answer: "Evidence [[E1]]",
  parsed_markers: ["E1"],
  alias_mapping: { E1: "chunk-1" },
  candidate_decisions: [],
  provider_metadata: {
    timing: {
      clock_resolution_ms: 0.001,
      phases: { generation: { duration_ms: 27 } },
    },
  },
  candidates: [
    {
      chunk_id: "chunk-1",
      chunk_ordinal: 2,
      chunk_set_id: "set-1",
      document_version_id: "version-1",
      workspace_id: "ws-1",
      source_key: "manual.pdf",
      start_line: 7,
      end_line: 9,
      final_rank: 1,
      final_decision: "SELECTED",
      fusion_score: 0,
      content: "Evidence text",
    },
  ],
};

describe("Figma operator data surfaces", () => {
  it("formats measured millisecond precision for the columns and retains the raw values", () => {
    render(
      <TraceView
        trace={{
          ...trace,
          retrieval_latency_ms: 27.797764000069947,
          provider_metadata: {
            timing: {
              phases: { generation: { duration_ms: 0.030992000120022567 } },
            },
          },
        }}
      />,
    );
    expect(screen.getByText("27.798 ms")).toHaveAttribute(
      "title",
      "27.797764000069947 ms",
    );
    expect(screen.getByText("0.031 ms")).toHaveAttribute(
      "title",
      "0.030992000120022567 ms",
    );
  });
  it("shows missing schema and derivation metadata as unavailable without failing the trace", () => {
    render(
      <TraceView
        trace={{
          ...trace,
          trace_schema_version: undefined as never,
          chunk_set_ids: undefined as never,
          embedding_set_ids: undefined as never,
        }}
      />,
    );
    expect(
      screen.getByRole("region", { name: "Trace context" }),
    ).toHaveTextContent("Unavailable");
    expect(screen.queryByText("vundefined")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Additional provenance", { exact: true }));
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(1);
  });
  it("groups runtime signals separately from accounting and preserves measured zero", () => {
    render(
      <OperationsView
        operations={{
          workspace_id: "ws-1",
          configuration_version: "ops-v1",
          histograms: { latency: { buckets: [[null, 0]] } },
          metrics: { queue_depth: 0, retry_rate: 0.024 },
        }}
      />,
    );
    const signals = screen.getByRole("group", { name: "Runtime signals" });
    expect(within(signals).getByText("0")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(within(signals).getByText("2.4%")).toBeVisible();
    expect(within(signals).getAllByText("Unavailable")).toHaveLength(2);
    expect(screen.getByText("Bound unavailable")).toBeVisible();
    expect(screen.queryByText("null")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Execution accounting" }),
    ).toBeVisible();
  });
  it("shows citation-to-source mapping and schema/configuration provenance without opening disclosures", () => {
    render(<TraceView trace={trace} />);
    expect(
      screen.getByRole("heading", { name: "Trace summary" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Observed result" }),
    ).toBeVisible();
    const context = screen.getByRole("region", { name: "Trace context" });
    expect(within(context).getByText("v2")).toBeVisible();
    expect(within(context).getByText("retrieval-v1")).toBeVisible();
    const mapping = screen.getByRole("region", { name: "Citation mapping" });
    expect(within(mapping).getByText("E1")).toBeVisible();
    expect(within(mapping).getByText("chunk-1")).toBeVisible();
    expect(within(mapping).getByText("manual.pdf")).toBeVisible();
    expect(screen.getByText("version-1")).toBeInTheDocument();
    expect(screen.getByText("27 ms")).toBeVisible();
  });
  it.each(["REFUSAL", "FAILED"])(
    "keeps %s and empty candidates explicit",
    (decision) => {
      render(
        <TraceView
          trace={{
            ...trace,
            decision,
            answer: null,
            refusal_reason:
              decision === "REFUSAL" ? "INSUFFICIENT_EVIDENCE" : null,
            candidates: [],
            parsed_markers: [],
            alias_mapping: {},
          }}
        />,
      );
      expect(
        screen.getByRole("heading", { name: "Observed result" }),
      ).toBeVisible();
      expect(screen.getByText("No candidates in this trace.")).toBeVisible();
      expect(screen.queryByText("Evidence text")).not.toBeInTheDocument();
      expect(
        within(screen.getByRole("region", { name: "Observed result" }))
          .getByText(decision)
          .closest(".kn-status-badge"),
      ).not.toHaveAttribute("data-kind", "success");
    },
  );
  it("shows actual unavailable evaluation code with a report context and no invented download", () => {
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
    ).toBeVisible();
    expect(
      screen.getByRole("region", { name: "Report context" }),
    ).toHaveTextContent("EVALUATION_REPORT_UNAVAILABLE");
    expect(
      screen.queryByRole("link", { name: /download/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });
  it("disables empty trace lookup, encodes exact identifiers, and exposes pending navigation", async () => {
    render(
      await TracesPage({
        searchParams: Promise.resolve({ workspaceId: "ws /&" }),
      }),
    );
    const submit = screen.getByRole("button", { name: "Open trace" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: "Trace ID" }), {
      target: { value: "trace /?&" },
    });
    fireEvent.click(submit);
    expect(push).toHaveBeenCalledWith(
      "/operator/traces/trace%20%2F%3F%26?workspaceId=ws%20%2F%26",
    );
    expect(
      screen.getByRole("button", { name: "Opening trace…" }),
    ).toBeDisabled();
  });
  it("disables an empty report lookup", async () => {
    render(await EvaluationsPage({}));
    expect(screen.getByRole("button", { name: "Open report" })).toBeDisabled();
  });
});
