import React from "react";
import {
  render,
  screen,
  within,
  fireEvent,
  cleanup,
  act,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  OperatorEvaluationResponse,
  OperatorTraceResponse,
} from "@/generated/knora-openapi";
import { OperationsView } from "@/components/operator/OperationsView";
import { TraceView } from "@/components/operator/TraceView";
import { EvaluationView } from "@/components/operator/EvaluationView";
import {
  OperatorFrame,
  OperatorLookup,
} from "@/components/operator/OperatorFrame";
import { WorkspaceSelector } from "@/components/workspaces/WorkspaceSelector";
import { StatusBadge } from "@/components/ui/StatusBadge";
import TracesPage from "@/app/operator/traces/page";
import EvaluationsPage from "@/app/operator/evaluations/page";

const push = vi.fn();
const refresh = vi.fn();
let pathname = "/operator/traces";
let searchQuery = "";
vi.stubGlobal("React", React);
afterEach(() => {
  cleanup();
  push.mockClear();
  refresh.mockReset();
  pathname = "/operator/traces";
  searchQuery = "";
  vi.unstubAllGlobals();
});
vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useSearchParams: () => new URLSearchParams(searchQuery),
  useRouter: () => ({ push, refresh }),
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
  it("keeps full long Trace provenance, mapped sources and zero observations inspectable", () => {
    const source =
      "Complete backend source name with a long revision and descriptive document title.pdf";
    const chunkId =
      "opaque-chunk-identifier-with-the-entire-backend-revision-0000000000000000000000";
    render(
      <TraceView
        trace={{
          ...trace,
          trace_id:
            "opaque-trace-identifier-with-the-entire-backend-revision-0000000000000000000000",
          retrieval_configuration_id:
            "retrieval-configuration-with-complete-immutable-policy-version",
          candidates: [
            {
              ...trace.candidates[0],
              chunk_id: chunkId,
              source_key: source,
              content: "Complete evidence beginning. Complete evidence ending.",
              decision_reason: "CHUNK_COUNT_LIMIT",
              vector_contribution: { rank: 1, similarity: 0 },
              fts_contribution: { rank: 2, score: 0 },
            },
          ],
          alias_mapping: {
            E1: chunkId,
            E2: "mapped-chunk-without-a-candidate",
          },
          provider_metadata: {
            timing: {
              phases: {
                retrieval: { duration_ms: 0 },
                generation: { duration_ms: null },
              },
            },
          },
          candidate_decisions: [
            { chunk_id: chunkId, reason: "CHUNK_COUNT_LIMIT" },
          ],
        }}
      />,
    );
    expect(
      screen.getByRole("group", { name: "Trace summary signals" }),
    ).toHaveTextContent("0 ms");
    const context = screen.getByRole("region", { name: "Trace context" });
    expect(context).toHaveTextContent(
      "opaque-trace-identifier-with-the-entire-backend-revision-0000000000000000000000",
    );
    expect(context).toHaveTextContent(
      "retrieval-configuration-with-complete-immutable-policy-version",
    );
    const mapping = screen.getByRole("region", { name: "Citation mapping" });
    expect(mapping).toHaveTextContent(chunkId);
    expect(mapping).toHaveTextContent(source);
    expect(mapping).toHaveTextContent("mapped-chunk-without-a-candidate");
    expect(mapping).toHaveTextContent("Source unavailable");
    const timing = screen.getByRole("region", { name: "Phase timing" });
    expect(within(timing).getByText("0 ms")).toBeVisible();
    expect(within(timing).getByText("Unavailable")).toBeVisible();
    const candidate = screen.getByRole("region", {
      name: "Candidate provenance",
    });
    expect(candidate).toHaveTextContent(
      "Complete evidence beginning. Complete evidence ending.",
    );
    fireEvent.click(within(candidate).getByText("Retrieval details"));
    for (const value of [
      chunkId,
      "version-1",
      "set-1",
      "CHUNK_COUNT_LIMIT",
      '{"rank":1,"similarity":0}',
      '{"rank":2,"score":0}',
    ]) {
      expect(within(candidate).getByText(value, { exact: true })).toBeVisible();
    }
    fireEvent.click(screen.getByText("Candidate decisions", { exact: true }));
    expect(
      screen.getByText(
        `{"chunk_id":"${chunkId}","reason":"CHUNK_COUNT_LIMIT"}`,
        { exact: true },
      ),
    ).toBeVisible();
  });
  it.each([
    "ANSWER",
    "REFUSAL",
    "FAILED",
    "GENERATION_OUTPUT_INVALID",
    "UNKNOWN_RECORDED_OUTCOME",
  ])(
    "retains the complete observed decision %s and its existing semantic tone",
    (decision) => {
      render(<TraceView trace={{ ...trace, decision }} />);
      const result = screen.getByRole("region", { name: "Observed result" });
      const label = within(result).getByText(decision, { exact: true });
      expect(label.closest(".kn-status-badge")).toHaveAttribute(
        "data-kind",
        decision === "ANSWER" ? "success" : "warning",
      );
      expect(result).toHaveTextContent("Evidence [[E1]]");
    },
  );
  it.each([
    "SELECTED",
    "REDUNDANT_OVERLAP",
    "BUDGET_EXCEEDED",
    "ELIGIBLE_NOT_SELECTED",
    "BELOW_THRESHOLD",
    "UNKNOWN_RECORDED_CANDIDATE_DECISION_WITH_FULL_DETAIL",
  ])(
    "retains candidate decision %s with full evidence and provenance",
    (final_decision) => {
      render(
        <TraceView
          trace={{
            ...trace,
            candidates: [{ ...trace.candidates[0], final_decision }],
          }}
        />,
      );
      const candidate = within(
        screen.getByRole("region", { name: "Candidate provenance" }),
      );
      const label = candidate.getByText(final_decision, { exact: true });
      expect(label.closest(".kn-status-badge")).toHaveAttribute(
        "data-kind",
        final_decision === "SELECTED" ? "success" : "info",
      );
      expect(candidate.getByText("manual.pdf")).toBeVisible();
      expect(candidate.getByText("Evidence text")).toBeVisible();
      expect(candidate.getByText(/Rank 1 · Fusion 0/)).toBeVisible();
      fireEvent.click(candidate.getByText("Retrieval details"));
      for (const value of ["chunk-1", "version-1", "set-1"]) {
        expect(candidate.getByText(value, { exact: true })).toBeVisible();
      }
    },
  );
  it("preserves shared StatusBadge default text, semantic tone and decorative icon", () => {
    const { container } = render(
      <StatusBadge kind="success">Other consumer</StatusBadge>,
    );
    expect(screen.getByText("Other consumer")).toBeVisible();
    expect(
      container.querySelector('[data-kind="success"]'),
    ).toBeInTheDocument();
    expect(container.querySelector('[aria-hidden="true"]')).toHaveTextContent(
      "✓",
    );
    expect(container.querySelector('[aria-hidden="true"]')).toBeVisible();
  });
  it.each([
    ["/operator/operations", "a4e11"],
    ["/operator/traces/trace-1", "bab86"],
    ["/operator/evaluations/report-1", "bab86"],
  ])(
    "uses the source caret only in the Operator frame for %s",
    async (route, asset) => {
      pathname = route;
      const workspace = {
        id: "ws-1",
        name: "Research workspace",
        archived: false,
        revision: 7,
      };
      const requests = vi.fn(async (url: string, options?: RequestInit) => {
        if (options?.method && options.method !== "GET")
          throw new Error("Unexpected write");
        return new Response(
          JSON.stringify(
            url.endsWith("/ws-1")
              ? workspace
              : { items: [workspace], next_cursor: null },
          ),
          { status: 200 },
        );
      });
      vi.stubGlobal("fetch", requests);
      const { container, unmount } = render(
        <OperatorFrame workspaceId="ws-1" workspaceName={workspace.name}>
          <p>Operator data</p>
        </OperatorFrame>,
      );
      const trigger = await screen.findByRole("button", {
        name: "Switch workspace: Research workspace",
      });
      expect(trigger.querySelector("img")).toHaveAttribute(
        "src",
        `/icons/figma/${asset}.svg`,
      );
      fireEvent.click(
        screen.getByRole("button", { name: "Workspace actions" }),
      );
      expect(
        screen.getByRole("menuitem", { name: "Archive workspace" }),
      ).toBeVisible();
      fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
      fireEvent.click(trigger);
      expect(trigger.querySelector("img")).toHaveAttribute(
        "src",
        "/icons/figma/23c31.svg",
      );
      expect(
        screen.getByRole("button", { name: "+ Create workspace" }),
      ).toBeVisible();
      expect(
        screen.getByRole("link", { name: "Archived workspaces" }),
      ).toHaveAttribute("href", "/workspaces/archived");
      fireEvent.keyDown(container.querySelector(".workspace-selector")!, {
        key: "Escape",
      });
      expect(trigger).toHaveFocus();
      unmount();
      // A default consumer stays unchanged even if its current route is Operator.
      render(
        <WorkspaceSelector workspaceId="ws-1" workspaceName={workspace.name} />,
      );
      const defaultTrigger = await screen.findByRole("button", {
        name: "Switch workspace: Research workspace",
      });
      expect(defaultTrigger.querySelector("img")).toHaveAttribute(
        "src",
        "/icons/figma/21b31.svg",
      );
      expect(
        defaultTrigger.querySelector(".workspace-caret-small"),
      ).toBeInTheDocument();
      await waitFor(() => expect(requests).toHaveBeenCalled());
      expect(
        requests.mock.calls.every(
          ([, options]) => !options?.method || options.method === "GET",
        ),
      ).toBe(true);
    },
  );
  it("explains the recorded trace evidence on the actual async lookup route", async () => {
    render(await TracesPage({}));
    const guidance = screen.getByRole("region", {
      name: "What this trace shows",
    });
    expect(
      within(guidance).getByRole("heading", { name: "What this trace shows" }),
    ).toBeVisible();
    expect(guidance).toHaveTextContent(
      "Open an exact Trace ID to inspect one question’s recorded retrieval and validation evidence.",
    );
    expect(guidance).toHaveTextContent("DECISION & VALIDATION");
    expect(guidance).toHaveTextContent(
      "Final answer or refusal, plus the validation outcome.",
    );
    expect(guidance).toHaveTextContent("CANDIDATE PROVENANCE");
    expect(guidance).toHaveTextContent(
      "Ranked evidence with source, chunk, score, and selection decision.",
    );
    expect(guidance).toHaveTextContent("CITATIONS & TIMING");
    expect(guidance).toHaveTextContent(
      "Citation mapping and per-phase timing for the request.",
    );
    expect(screen.getByRole("textbox", { name: "Trace ID" })).toHaveValue("");
    expect(screen.getByRole("button", { name: "Open trace" })).toBeDisabled();
  });
  it("explains persisted report availability on the actual async lookup route", async () => {
    render(await EvaluationsPage({}));
    const guidance = screen.getByRole("region", {
      name: "What this report provides",
    });
    expect(
      within(guidance).getByRole("heading", {
        name: "What this report provides",
      }),
    ).toBeVisible();
    expect(guidance).toHaveTextContent(
      "Open an exact Report ID. Knora only shows persisted evaluation data that the backend actually provides.",
    );
    expect(guidance).toHaveTextContent("PERSISTED REPORT");
    expect(guidance).toHaveTextContent(
      "Evaluation data appears only when a persisted report is available.",
    );
    expect(guidance).toHaveTextContent("WORKSPACE SCOPED");
    expect(guidance).toHaveTextContent(
      "Report context stays tied to the workspace it was observed for.",
    );
    expect(guidance).toHaveTextContent("NO INVENTED METRICS");
    expect(guidance).toHaveTextContent(
      "Missing reports remain explicitly unavailable instead of becoming synthetic scores.",
    );
    expect(screen.getByRole("textbox", { name: "Report ID" })).toHaveValue("");
    expect(screen.getByRole("button", { name: "Open report" })).toBeDisabled();
  });
  it("retains encoded report lookup with an exact optional Workspace override", async () => {
    render(
      await EvaluationsPage({
        searchParams: Promise.resolve({ workspaceId: "ws /&" }),
      }),
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Report ID" }), {
      target: { value: " report /?& " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Open report" }));
    expect(push).toHaveBeenCalledWith(
      "/operator/evaluations/report%20%2F%3F%26?workspaceId=ws%20%2F%26",
    );
  });
  it("retains encoded trace and Workspace query redirects before rendering", async () => {
    await expect(
      TracesPage({
        searchParams: Promise.resolve({
          traceId: " trace /?& ",
          workspaceId: "ws /&",
        }),
      }),
    ).rejects.toThrow(
      "/operator/traces/trace%20%2F%3F%26?workspaceId=ws%20%2F%26",
    );
  });
  it("retains encoded report and Workspace query redirects before rendering", async () => {
    await expect(
      EvaluationsPage({
        searchParams: Promise.resolve({
          reportId: " report /?& ",
          workspaceId: "ws /&",
        }),
      }),
    ).rejects.toThrow(
      "/operator/evaluations/report%20%2F%3F%26?workspaceId=ws%20%2F%26",
    );
  });
  it.each([undefined, "ws /&"])(
    "completes an unchanged unavailable report retry for scope %s and permits a subsequent lookup",
    async (workspaceId) => {
      pathname = "/operator/evaluations/report-1";
      searchQuery = workspaceId
        ? new URLSearchParams({ workspaceId }).toString()
        : "";
      let complete!: (value: string) => void;
      let refreshedValue: string | null = null;
      const refreshed = new Promise<string>((resolve) => {
        complete = resolve;
      }).then((value) => {
        refreshedValue = value;
        return value;
      });
      function Observation({ value }: { value: Promise<string> | null }) {
        if (value && refreshedValue === null) throw value;
        return <p role="status">{refreshedValue ?? "Report unavailable"}</p>;
      }
      function NavigationBoundary() {
        const [observation, setObservation] =
          React.useState<Promise<string> | null>(null);
        refresh.mockImplementation(() => setObservation(refreshed));
        return (
          <>
            <OperatorLookup
              kind="report"
              identifier="report-1"
              workspaceId={workspaceId}
            />
            <React.Suspense fallback={<p>Loading observation</p>}>
              <Observation value={observation} />
            </React.Suspense>
          </>
        );
      }
      render(<NavigationBoundary />);
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Open report" }));
      });
      expect(refresh).toHaveBeenCalledOnce();
      expect(push).not.toHaveBeenCalled();
      expect(
        screen.getByRole("button", { name: "Opening report…" }),
      ).toBeDisabled();
      await act(async () => complete("Report remains unavailable"));
      expect(screen.getByRole("status")).toHaveTextContent(
        "Report remains unavailable",
      );
      expect(screen.getByRole("button", { name: "Open report" })).toBeEnabled();
      const input = screen.getByRole("textbox", { name: "Report ID" });
      expect(input).toBeEnabled();
      fireEvent.change(input, { target: { value: "report-2" } });
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Open report" }));
      });
      expect(push).toHaveBeenCalledWith(
        `/operator/evaluations/report-2${workspaceId ? `?workspaceId=${encodeURIComponent(workspaceId)}` : ""}`,
      );
    },
  );
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
  it("retains all six accounting meanings and every supplied valid bucket without inventing missing values", () => {
    const { container } = render(
      <OperationsView
        operations={{
          workspace_id: "ws-1",
          configuration_version: "ops-v1",
          metrics: {
            oldest_job_age: 0,
            claim_latency_count: 124,
            claim_latency_sum: 18.4,
            cleanup_attempt_total: 32,
            orphan_reconciliation_total: 0,
          },
          histograms: {
            latency: {
              count: 0,
              sum: 0,
              buckets: [
                [0.1, 0],
                [0.25, 91],
                [0.5, 118],
                [1, 124],
                [2, 125],
                [null, null],
                null,
                [4],
                [5, 126, 127],
                "malformed",
              ],
            },
          },
        }}
      />,
    );
    const accounting = container.querySelector("h3 + dl")!;
    expect(
      Array.from(accounting.querySelectorAll("dt"), (node) => node.textContent),
    ).toEqual([
      "Oldest job age",
      "Claim latency samples",
      "Claim latency sum",
      "Lease expiry recoveries",
      "Cleanup attempts",
      "Orphan reconciliations",
    ]);
    expect(
      Array.from(accounting.querySelectorAll("dd"), (node) => [
        node.textContent,
        node.getAttribute("data-state"),
      ]),
    ).toEqual([
      ["0 s", "available"],
      ["124", "available"],
      ["18.4 s", "available"],
      ["Unavailable", "unavailable"],
      ["32", "available"],
      ["0", "available"],
    ]);
    const histogram = container.querySelector(
      'dl[aria-label="Cumulative latency buckets"]',
    )!;
    expect(
      Array.from(histogram.querySelectorAll("dt"), (node) => node.textContent),
    ).toEqual([
      "≤ 0.1 s",
      "≤ 0.25 s",
      "≤ 0.5 s",
      "≤ 1 s",
      "≤ 2 s",
      "Bound unavailable",
    ]);
    expect(
      Array.from(histogram.querySelectorAll("dd"), (node) => node.textContent),
    ).toEqual(["0", "91", "118", "124", "125", "Unavailable"]);
    expect(screen.getByText("latency · 0 samples · 0 s total")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent(
      "ALERTSUnavailable in the current Operator contract.",
    );
  });
  it("keeps an absent histogram explicitly unavailable", () => {
    render(
      <OperationsView
        operations={{
          workspace_id: "ws-1",
          configuration_version: "ops-v1",
          metrics: {},
          histograms: {},
        }}
      />,
    );
    expect(screen.getByText("Latency histogram unavailable.")).toBeVisible();
    expect(
      screen.queryByLabelText("Cumulative latency buckets"),
    ).not.toBeInTheDocument();
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
  it.each([
    {
      availability: "available",
      observation_failure: "",
      boundary: "contract response",
      available: true,
      copy: "The backend reports this evaluation as available. No evaluation metrics are supplied by this observation.",
    },
    {
      availability: "unavailable",
      observation_failure: "EVALUATION_REPORT_UNAVAILABLE",
      boundary: "contract response",
      available: false,
      copy: "Persisted evaluation reports are not available in the current Operator contract. Knora does not invent quality scores, pass/fail results, or other evaluation metrics when the backend has no report to expose.",
    },
    {
      availability: "available",
      observation_failure:
        "OBSERVATION_FAILURE_WITH_COMPLETE_OPAQUE_BACKEND_REVISION_0000000000000000000000",
      boundary: "contract response",
      available: false,
      copy: "The backend could not supply this evaluation report. No evaluation metrics are available for this observation.",
    },
    {
      // Deliberately malformed runtime input characterizes existing defensive guards;
      // undefined observation fields are not supported by the generated contract.
      ...({
        availability: undefined,
        observation_failure: undefined,
      } as unknown as Pick<
        OperatorEvaluationResponse,
        "availability" | "observation_failure"
      >),
      boundary: "out-of-contract defensive runtime input",
      available: false,
      copy: "The backend could not supply this evaluation report. No evaluation metrics are available for this observation.",
    },
  ])(
    "preserves Evaluation context and complete copy for $availability / $observation_failure ($boundary)",
    ({ availability, observation_failure, available, copy }) => {
      const reportId =
        "opaque-report-identifier-with-complete-backend-revision-0000000000000000000000";
      const workspaceId =
        "opaque-workspace-identifier-with-complete-backend-revision-0000000000000000000000";
      render(
        <EvaluationView
          evaluation={{
            report_id: reportId,
            workspace_id: workspaceId,
            availability,
            observation_failure,
          }}
        />,
      );
      const result = screen.getByRole("region", {
        name: `Evaluation report ${available ? "available" : "unavailable"}`,
      });
      expect(within(result).getByText(copy, { exact: true })).toBeVisible();
      const context = within(
        screen.getByRole("region", { name: "Report context" }),
      );
      expect(
        context.getAllByRole("term").map((term) => term.textContent),
      ).toEqual([
        "Report ID",
        "Observed Workspace",
        "Availability",
        "Observation code",
      ]);
      expect(
        context.getAllByRole("definition").map((value) => value.textContent),
      ).toEqual([
        reportId,
        workspaceId,
        available ? "Available" : "Unavailable",
        observation_failure ?? "Unavailable",
      ]);
      expect(result.querySelector(".kn-status-badge")).toHaveAttribute(
        "data-kind",
        available ? "success" : "warning",
      );
      expect(screen.queryByRole("table")).not.toBeInTheDocument();
      expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name: /download/i }),
      ).not.toBeInTheDocument();
    },
  );
  it("disables empty trace lookup and encodes exact identifiers", async () => {
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
    expect(screen.getByRole("button", { name: "Open trace" })).toBeEnabled();
  });
  it("disables an empty report lookup", async () => {
    render(await EvaluationsPage({}));
    expect(screen.getByRole("button", { name: "Open report" })).toBeDisabled();
  });
});
