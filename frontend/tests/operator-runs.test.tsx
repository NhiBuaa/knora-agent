import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { RunsView } from "@/components/operator/runs/RunsView";
import { RunArtifact } from "@/components/operator/runs/RunArtifact";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
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
