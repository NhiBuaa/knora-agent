import { describe, expect, it, vi } from "vitest";
import { readOperatorBff } from "../../lib/operator/bff";
import { OperationsContent } from "../../app/operator/operations/content";
import TraceDetailPage from "../../app/operator/traces/[traceId]/page";
import EvaluationDetailPage from "../../app/operator/evaluations/[reportId]/page";

vi.mock("../../lib/operator/bff", () => ({ readOperatorBff: vi.fn() }));

describe("operator page transport failures", () => {
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
