import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { DeepEvalScoring } from "@/components/operator/runs/DeepEvalScoring";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const props = {
  workspaceId: "w1",
  runId: "r1",
  caseIds: ["answer", "refusal"],
  canScore: true,
};

it("shows scoring unavailable without an approved server-side profile", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ profiles: [], batches: [] })),
  );
  render(<DeepEvalScoring {...props} />);
  expect(
    await screen.findByText(/No judge profile is configured/),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Score saved answers" }),
  ).not.toBeInTheDocument();
  expect(screen.getByText(/never runs Q&A again/)).toBeInTheDocument();
});

it("preflights selected saved cases and renders uncalibrated per-case metric results", async () => {
  const fetcher = vi.fn(async (input: string, init?: RequestInit) => {
    if (!init?.method)
      return Response.json({
        profiles: [
          { profile_id: "fixture", kind: "offline", model: "fixture-model" },
        ],
        batches: [],
      });
    if (input.includes("preflight"))
      return Response.json({
        preflight_id: "p1",
        status: "READY",
        reasons: [],
        input_digest: "exact-saved-input",
        cases: [{ case_id: "answer", status: "NOT_RUN", metrics: {} }],
      });
    return Response.json({
      id: "batch-1",
      status: "COMPLETED",
      input_digest: "exact-saved-input",
      quality_status: "UNCALIBRATED",
      scorer: { model: "fixture-model", prompt_version: "v1" },
      results: {
        answer: {
          status: "COMPLETED",
          trace_id: "trace-1",
          metrics: {
            correctness: {
              status: "scored",
              score: 0.8,
              rationale: "Fixture judgment",
            },
            faithfulness: { status: "not_applicable", score: null },
          },
        },
      },
    });
  });
  vi.stubGlobal("fetch", fetcher);
  render(<DeepEvalScoring {...props} />);
  await userEvent.click(
    await screen.findByRole("checkbox", { name: "answer" }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Check scoring readiness" }),
  );
  expect(await screen.findByText(/Readiness: READY/)).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Score saved answers" }),
  );
  expect(await screen.findByText(/Quality: UNCALIBRATED/)).toBeInTheDocument();
  expect(screen.getByText(/correctness: scored — 0.8/)).toBeInTheDocument();
  expect(
    screen.getByText(/faithfulness: not_applicable — N\/A/),
  ).toBeInTheDocument();
  expect(screen.getByText("Fixture judgment")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Trace trace-1" })).toHaveAttribute(
    "href",
    "/operator/traces/trace-1?workspaceId=w1",
  );
  await waitFor(() =>
    expect(
      fetcher.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(2),
  );
  const mutations = fetcher.mock.calls
    .filter(([, init]) => init?.method === "POST")
    .map(([url, init]) => [url, JSON.parse(init!.body as string)]);
  expect(mutations).toEqual([
    [
      "/api/operator/evaluation/runs/r1/scoring/preflight?workspaceId=w1",
      { case_ids: ["answer"], profile_id: "fixture" },
    ],
    [
      "/api/operator/evaluation/runs/r1/scoring?workspaceId=w1",
      { preflight_id: "p1", request_id: expect.any(String) },
    ],
  ]);
});

it("keeps read-only results visible without scoring controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        profiles: [{ profile_id: "fixture" }],
        batches: [
          {
            id: "uncertain",
            status: "INDETERMINATE",
            quality_status: "UNCALIBRATED",
            results: {
              answer: {
                status: "INDETERMINATE",
                reason: "JUDGE_RESULT_UNAVAILABLE",
                metrics: {},
              },
            },
          },
        ],
      }),
    ),
  );
  render(<DeepEvalScoring {...props} canScore={false} />);
  expect(
    await screen.findByText(/JUDGE_RESULT_UNAVAILABLE/),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Check scoring readiness" }),
  ).not.toBeInTheDocument();
});
