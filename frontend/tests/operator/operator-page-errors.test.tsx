import { describe, expect, it, vi } from "vitest";
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { readOperatorBff } from "../../lib/operator/bff";
import { OperationsContent } from "../../app/operator/operations/content";
import TraceDetailPage from "../../app/operator/traces/[traceId]/page";
import EvaluationDetailPage from "../../app/operator/evaluations/[reportId]/page";

vi.mock("../../lib/operator/bff", () => ({ readOperatorBff: vi.fn() }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/operator/traces/trace-1",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

describe("operator page transport failures", () => {
  it("renders unavailable when operations JSON is malformed", async () => {
    vi.mocked(readOperatorBff).mockResolvedValueOnce(
      new Response("not-json", { status: 200 }),
    );
    const page = await OperationsContent();
    expect(page.props.role).toBe("status");
    expect(page.props.children).toBe("Operational observation unavailable.");
  });
  it.each([
    ["trace", TraceDetailPage, { traceId: "trace-1" }],
    ["evaluation", EvaluationDetailPage, { reportId: "report-1" }],
  ] as const)(
    "keeps %s lookup available after malformed observation JSON",
    async (kind, page, params) => {
      vi.mocked(readOperatorBff).mockResolvedValueOnce(
        new Response("not-json", { status: 200 }),
      );
      render(await page({ params: Promise.resolve(params) } as never));
      expect(screen.getByRole("status")).toHaveTextContent(
        /observation unavailable/i,
      );
      expect(
        screen.getByRole("button", {
          name: kind === "trace" ? "Open trace" : "Open report",
        }),
      ).toBeEnabled();
      cleanup();
    },
  );
  it("forwards exact trace and report IDs with an explicit archived Workspace target", async () => {
    vi.mocked(readOperatorBff).mockResolvedValue(
      new Response("{}", { status: 404 }),
    );
    await TraceDetailPage({
      params: Promise.resolve({ traceId: "trace 1" }),
      searchParams: Promise.resolve({ workspaceId: "archived-ws" }),
    });
    await EvaluationDetailPage({
      params: Promise.resolve({ reportId: "report 1" }),
      searchParams: Promise.resolve({ workspaceId: "archived-ws" }),
    });
    expect(readOperatorBff).toHaveBeenCalledWith(
      "/api/operator/traces/trace%201?workspaceId=archived-ws",
    );
    expect(readOperatorBff).toHaveBeenCalledWith(
      "/api/operator/evaluations/report%201?workspaceId=archived-ws",
    );
  });
  it("renders unavailable when the operations BFF request rejects", async () => {
    vi.mocked(readOperatorBff).mockRejectedValueOnce(
      new Error("BFF unavailable"),
    );

    const page = await OperationsContent();

    expect(page.props.role).toBe("status");
    expect(page.props.children).toBe("Operational observation unavailable.");
  });
});
