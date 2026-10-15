import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { RunsView as BaseRunsView } from "@/components/operator/runs/RunsView";
import { RunArtifact } from "@/components/operator/runs/RunArtifact";

const RunsView = (props: React.ComponentProps<typeof BaseRunsView>) => (
  <BaseRunsView
    capabilities={["operator:read", "evaluations:run", "questions:ask"]}
    {...props}
  />
);

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("preflights exact frozen PDF selection and discloses blocked cases", async () => {
  const reference = {
    dataset_id: "pdf-set",
    workspace_id: "w",
    version: 1,
    format: "pdf-gold-v1",
    metric_contract: "pdf-metrics-v1",
    digest: "a".repeat(64),
  };
  const payloads: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/datasets"))
        return Response.json({
          items: [
            {
              id: "pdf-set",
              format: "pdf-gold-v1",
              reference,
              cases: [
                {
                  id: "answer",
                  question: "Sky color?",
                  expected_behavior: "ANSWER",
                },
                {
                  id: "refusal",
                  question: "Absent fact?",
                  expected_behavior: "REFUSAL",
                },
              ],
            },
          ],
        });
      if (url.includes("/profiles"))
        return Response.json([
          { profile_id: "live", kind: "live", status: "BLOCKED" },
        ]);
      if (url.includes("/preflight")) {
        payloads.push(JSON.parse(String(init?.body)));
        return Response.json({
          preflight_id: "pdf-p",
          status: "BLOCKED",
          reasons: ["PROVIDER_APPROVAL_REQUIRED"],
          context_only_case_ids: [],
          case_readiness: [
            {
              case_id: "answer",
              status: "BLOCKED",
              reasons: ["SOURCE_FAILED:version-1"],
              warnings: ["ANCHOR_BINDING_MISSING"],
            },
          ],
        });
      }
      return Response.json([]);
    }),
  );
  render(<RunsView workspaceId="w" />);
  await userEvent.click(
    await screen.findByRole("checkbox", { name: /Sky color/ }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Check readiness" }),
  );
  expect(
    await screen.findByText(/SOURCE_FAILED:version-1/),
  ).toBeInTheDocument();
  expect(payloads).toEqual([
    {
      dataset_id: "pdf-set",
      dataset_reference: reference,
      case_ids: ["answer"],
      profile_id: "live",
    },
  ]);
  expect(screen.getByRole("button", { name: "Start run" })).toBeDisabled();
});

it("renders PDF metric semantics and every population without merging scores", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        quality_status: "SEMANTIC_PENDING",
        dataset: { dataset_id: "pdf-set", version: 1, digest: "digest-1" },
        population: {
          dataset: 3,
          selected: 2,
          context_only: 0,
          attempted: 2,
          observed: 1,
          applicable: 2,
          evaluable: 1,
        },
        retrieval: {
          name: "evidence_group_coverage",
          scope: "full_ordered_fused_candidates",
          k: null,
          numerator: 1,
          denominator: 2,
          applicable_denominator: 4,
          value: 0.5,
        },
        generation_evidence_coverage: {
          name: "evidence_group_coverage",
          scope: "generation_evidence",
          k: null,
          numerator: 0,
          denominator: 2,
          applicable_denominator: 4,
          value: 0,
        },
        cases: [
          { case_id: "a", status: "OBSERVED", evaluable: true, reasons: [] },
          {
            case_id: "b",
            status: "FAILED",
            evaluable: false,
            reasons: ["MISSING_TRACE"],
          },
        ],
      }),
    ),
  );
  render(<RunArtifact workspaceId="w" runId="pdf-run" />);
  expect(
    await screen.findByText(/Scope: full_ordered_fused_candidates/),
  ).toBeInTheDocument();
  expect(screen.getAllByText(/Applicable groups: 4/)).toHaveLength(2);
  expect(screen.getByText(/evaluable: 1/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "b" })).toBeInTheDocument();
  expect(
    screen.getByRole("cell", { name: "MISSING_TRACE" }),
  ).toBeInTheDocument();
});

it("shows case gold anchors with a fixed original PDF link and runtime evidence separately", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        quality_status: "SEMANTIC_PENDING",
        status: "OBSERVED",
        question: "Sky color?",
        reference_answer: "Blue",
        expected: "ANSWER",
        dataset: { dataset_id: "pdf-set", version: 1, digest: "digest-1" },
        source_preparation: [
          {
            source_id: "source-1",
            document_version_id: "version-1",
            status: "READY",
          },
        ],
        evidence_groups: [
          {
            alternatives: [
              {
                document_version_id: "version-1",
                physical_page: 2,
                quote: "The sky is blue.",
              },
            ],
          },
        ],
        candidate_chunk_ids: ["chunk-1", "chunk-2"],
        generation_chunk_ids: ["chunk-1"],
        generation_evidence: [["E1", "The sky is blue."]],
        reasons: [],
      }),
    ),
  );
  render(<RunArtifact workspaceId="w" runId="pdf-run" caseId="answer" />);
  expect(await screen.findByText(/Reference answer: Blue/)).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: /Original PDF.*page 2/ }),
  ).toHaveAttribute(
    "href",
    "/api/operator/evaluation/datasets/pdf-set/sources/source-1/original?workspaceId=w#page=2",
  );
  expect(
    screen.getByText(/Retrieved chunks: chunk-1, chunk-2/),
  ).toBeInTheDocument();
  expect(screen.getByText(/Generation chunks: chunk-1/)).toBeInTheDocument();
});

it("keeps the checked selection fixed while preflight is pending", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/datasets"))
        return Response.json({
          items: [
            {
              id: "m3-dataset-v1",
              format: "m3-native-v1",
              reference: { format: "m3-native-v1" },
              cases: [
                {
                  id: "lexical-01",
                  question: "Refund period?",
                  expected_behavior: "ANSWER",
                },
              ],
            },
          ],
        });
      if (url.includes("/profiles"))
        return Response.json([
          { profile_id: "live", kind: "live", status: "BLOCKED" },
        ]);
      if (url.includes("/preflight")) return new Promise<Response>(() => {});
      return Response.json([]);
    }),
  );
  render(<RunsView workspaceId="evaluation-m3-v1" />);
  await userEvent.click(
    await screen.findByRole("checkbox", { name: /Refund period/ }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Check readiness" }),
  );
  expect(
    screen.getByRole("checkbox", { name: /Refund period/ }),
  ).toBeDisabled();
  expect(screen.getByRole("combobox", { name: "Dataset" })).toBeDisabled();
  expect(
    screen.getByRole("combobox", { name: "Runtime profile" }),
  ).toBeDisabled();
});

it("keeps evaluation controls disabled for a read-only operator", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/datasets"))
        return Response.json({
          items: [
            {
              id: "m3",
              format: "m3-native-v1",
              reference: { format: "m3-native-v1" },
              cases: [
                {
                  id: "a",
                  question: "Read only?",
                  expected_behavior: "ANSWER",
                },
              ],
            },
          ],
        });
      return Response.json([]);
    }),
  );
  render(<RunsView workspaceId="w" capabilities={["operator:read"]} />);
  await screen.findByRole("checkbox", { name: /Read only/ });
  expect(
    screen.getByRole("button", { name: "Check readiness" }),
  ).toBeDisabled();
  expect(screen.getByRole("button", { name: "Start run" })).toBeDisabled();
  expect(screen.getByText(/Read-only access/)).toBeInTheDocument();
});

it("clears a run immediately when workspace changes", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("workspaceId=other"))
        return new Promise<Response>(() => {});
      return Response.json({
        run_id: "run-1",
        execution_status: "COMPLETED",
        quality_status: "SEMANTIC_PENDING",
        selection: { selected_case_ids: ["private-case"] },
        observations: { "private-case": { status: "OBSERVED" } },
        report: null,
      });
    }),
  );
  const { rerender } = render(
    <RunsView workspaceId="evaluation-m3-v1" runId="run-1" />,
  );
  expect(
    await screen.findByRole("link", { name: "private-case" }),
  ).toBeInTheDocument();
  rerender(<RunsView workspaceId="other" runId="run-2" />);
  expect(
    screen.queryByRole("link", { name: "private-case" }),
  ).not.toBeInTheDocument();
});

it("clears saved answer content immediately when artifact workspace changes", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("workspaceId=other"))
        return new Promise<Response>(() => {});
      return Response.json({
        status: "OBSERVED",
        public_answer: "Workspace one saved answer",
      });
    }),
  );
  const { rerender } = render(
    <RunArtifact workspaceId="w1" runId="run-1" caseId="case-1" />,
  );
  expect(
    await screen.findByText(/Workspace one saved answer/),
  ).toBeInTheDocument();
  rerender(<RunArtifact workspaceId="other" runId="run-2" caseId="case-2" />);
  expect(
    screen.queryByText(/Workspace one saved answer/),
  ).not.toBeInTheDocument();
});

it("refreshes a saved case checkpoint without dispatching Q&A", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(Response.json({ status: "NOT_RUN" }))
    .mockResolvedValueOnce(
      Response.json({
        status: "OBSERVED",
        trace_id: "new-trace",
        public_answer: "New saved checkpoint",
      }),
    );
  vi.stubGlobal("fetch", fetcher);
  render(<RunArtifact workspaceId="w" runId="r" caseId="a" />);
  await screen.findByText("Status: NOT_RUN");
  await userEvent.click(
    screen.getByRole("button", { name: "Refresh saved result" }),
  );
  expect(await screen.findByText(/New saved checkpoint/)).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(
    fetcher.mock.calls.every(
      (call) => !call[1]?.method || call[1].method === "GET",
    ),
  ).toBe(true);
});

it("selects native cases, shows blocked readiness, and never starts a blocked run", async () => {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url.includes("/datasets"))
        return Response.json({
          items: [
            { id: "draft", format: "pdf-gold-v1", reference: null, cases: [] },
            {
              id: "m3-dataset-v1",
              format: "m3-native-v1",
              reference: { format: "m3-native-v1" },
              cases: [
                {
                  id: "lexical-01",
                  question: "Refund period?",
                  expected_behavior: "ANSWER",
                },
                {
                  id: "refusal-04",
                  question: "CEO birthday?",
                  expected_behavior: "REFUSAL",
                },
              ],
            },
          ],
        });
      if (url.includes("/profiles"))
        return Response.json([
          { profile_id: "live", kind: "live", status: "BLOCKED" },
        ]);
      if (url.includes("/preflight"))
        return Response.json({
          status: "BLOCKED",
          reasons: ["PROVIDER_APPROVAL_REQUIRED"],
          preflight_id: "p",
        });
      return Response.json([]);
    }),
  );
  const user = userEvent.setup();
  render(<RunsView workspaceId="evaluation-m3-v1" />);
  await screen.findByRole("checkbox", { name: /Refund period/ });
  expect(screen.queryByText("draft")).not.toBeInTheDocument();
  await user.click(screen.getByRole("checkbox", { name: /Refund period/ }));
  await user.click(screen.getByRole("checkbox", { name: /CEO birthday/ }));
  await user.click(screen.getByRole("button", { name: "Check readiness" }));
  expect(
    await screen.findByText(/PROVIDER_APPROVAL_REQUIRED/),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Start run" })).toBeDisabled();
  expect(
    calls.some((call) => call.startsWith("POST") && call.includes("/runs")),
  ).toBe(false);
});

it("renders persisted failed case and pending report after reload", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        run_id: "run-1",
        execution_status: "COMPLETED",
        quality_status: "SEMANTIC_PENDING",
        selection: { selected_case_ids: ["lexical-01", "refusal-04"] },
        observations: {
          "lexical-01": {
            status: "FAILED",
            failure_code: "EVALUATION_OBSERVATION_FAILURE",
          },
          "refusal-04": {
            status: "OBSERVED",
            trace_id: "trace-1",
            decision: "REFUSAL",
          },
        },
        report: {
          retrieval: { denominator: 0 },
          quality_status: "SEMANTIC_PENDING",
        },
      }),
    ),
  );
  render(<RunsView workspaceId="evaluation-m3-v1" runId="run-1" />);
  expect(
    await screen.findByText(/EVALUATION_OBSERVATION_FAILURE/),
  ).toBeInTheDocument();
  expect(screen.getByText(/SEMANTIC_PENDING/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /trace-1/ })).toHaveAttribute(
    "href",
    "/operator/traces/trace-1?workspaceId=evaluation-m3-v1",
  );
  await waitFor(() =>
    expect(screen.getByRole("link", { name: /Report/ })).toBeInTheDocument(),
  );
});
