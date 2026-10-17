import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { RagasProposals } from "@/components/operator/datasets/RagasProposals";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const props = {
  workspaceId: "w1",
  datasetId: "d1",
  revision: 2,
  status: "DRAFT",
  canWrite: true,
  sources: [{ id: "s1", filename: "public.pdf", status: "READY" }],
  onChanged: vi.fn(async () => {}),
};

it("keeps generation unavailable when no approved server profile is configured", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ profiles: [], batches: [] })),
  );
  render(<RagasProposals {...props} />);
  expect(
    await screen.findByText(/No proposal provider is configured/),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Generate proposals" }),
  ).not.toBeInTheDocument();
  expect(screen.getByText(/two necessary evidence steps/)).toBeInTheDocument();
});

it("pins selection in preflight and sends a new request only after readiness", async () => {
  const fetcher = vi.fn(async (input: string, init?: RequestInit) => {
    if (!init?.method)
      return Response.json({
        profiles: [{ profile_id: "fixture", model: "offline" }],
        batches: [],
      });
    if (input.includes("preflight"))
      return Response.json({
        status: "READY",
        expected_revision: 2,
        input_digest: "a".repeat(64),
        reasons: [],
      });
    return Response.json({ status: "INDETERMINATE", id: "b" });
  });
  vi.stubGlobal("fetch", fetcher);
  render(<RagasProposals {...props} />);
  await userEvent.click(
    await screen.findByRole("checkbox", { name: "public.pdf" }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Check proposal readiness" }),
  );
  expect(await screen.findByText("READY")).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Generate proposals" }),
  );
  await waitFor(() =>
    expect(
      fetcher.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(2),
  );
  const bodies = fetcher.mock.calls
    .filter(([, init]) => init?.method === "POST")
    .map(([, init]) => JSON.parse(init!.body as string));
  expect(bodies[0]).toEqual({
    source_ids: ["s1"],
    profile_id: "fixture",
    language: "vi",
    count: 1,
  });
  expect(bodies[1]).toMatchObject({
    ...bodies[0],
    expected_revision: 2,
    input_digest: "a".repeat(64),
    request_id: expect.any(String),
  });
});

it("allows editing question/reference before importing an unreviewed draft", async () => {
  const changed = vi.fn(async () => {});
  const fetcher = vi.fn(async (input: string, init?: RequestInit) =>
    Response.json(
      init?.method
        ? {}
        : {
            profiles: [],
            batches: [
              {
                id: "batch",
                status: "COMPLETED",
                result: {
                  generator: { model: "offline" },
                  diagnostics: [],
                  source: {
                    pdf_sources: [
                      { source_id: "s1", document_version_id: "v1" },
                    ],
                  },
                  drafts: [
                    {
                      draft_id: "draft-01",
                      status: "READY_FOR_REVIEW",
                      case: {
                        case_id: "generated",
                        question: "Original?",
                        reference_answer: "Old answer",
                        required_facts: ["first", "second"],
                        evidence_groups: [
                          {
                            alternatives: [
                              {
                                document_version_id: "v1",
                                physical_page: 1,
                                quote: "Evidence one",
                              },
                            ],
                          },
                        ],
                      },
                    },
                  ],
                },
              },
            ],
          },
    ),
  );
  vi.stubGlobal("fetch", fetcher);
  render(<RagasProposals {...props} onChanged={changed} />);
  const question = await screen.findByRole("textbox", {
    name: "Proposal question",
  });
  await userEvent.clear(question);
  await userEvent.type(question, "Edited question?");
  await userEvent.click(
    screen.getByRole("button", { name: "Import as unreviewed case" }),
  );
  await waitFor(() => expect(changed).toHaveBeenCalledOnce());
  const [url, init] = fetcher.mock.calls.find(
    ([, init]) => init?.method === "POST",
  )!;
  expect(url).toContain(
    "/proposals/batch/drafts/draft-01/import?workspaceId=w1",
  );
  expect(JSON.parse(init!.body as string)).toEqual({
    expected_revision: 2,
    question: "Edited question?",
    reference_answer: "Old answer",
  });
  expect(screen.getByRole("link", { name: /PDF page 1/ })).toHaveAttribute(
    "href",
    "/api/operator/evaluation/datasets/d1/sources/s1/original?workspaceId=w1#page=1",
  );
  expect(
    fetcher.mock.calls.some(
      ([url]) => url.includes("/review") || url.includes("/freeze"),
    ),
  ).toBe(false);
});

it("shows saved proposals to read-only users without mutation controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ profiles: [], batches: [] })),
  );
  render(<RagasProposals {...props} canWrite={false} />);
  await screen.findByText(/No proposal provider is configured/);
  expect(
    screen.queryByRole("button", { name: "Check proposal readiness" }),
  ).not.toBeInTheDocument();
});
