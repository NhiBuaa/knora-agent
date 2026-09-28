import { describe, expect, it, vi } from "vitest";
import { buildOperatorBffUrl } from "../../lib/operator/bff";
import { OperationsContent } from "../../app/operator/operations/content";
import { readOperatorBff } from "../../lib/operator/bff";
import { renderToStaticMarkup } from "react-dom/server";

vi.mock("../../lib/operator/bff", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/operator/bff")>()),
  readOperatorBff: vi.fn(),
}));

describe("operator page BFF boundary", () => {
  it("builds same-origin BFF URLs instead of backend URLs", () => {
    expect(
      buildOperatorBffUrl("http://localhost:3000", "/api/operator/operations"),
    ).toBe("http://localhost:3000/api/operator/operations");
    expect(() =>
      buildOperatorBffUrl(
        "http://localhost:3000",
        "/v1/workspaces/ws/operator/operations",
      ),
    ).toThrow("Operator pages must use the operator BFF");
  });

  it("passes an explicit Workspace target to the read-only operations BFF", async () => {
    vi.mocked(readOperatorBff).mockResolvedValue(
      new Response(
        '{"configuration_version":"v1","histograms":{},"metrics":{},"workspace_id":"archived-ws"}',
      ),
    );
    const content = await OperationsContent({ workspaceId: "archived-ws" });
    expect(readOperatorBff).toHaveBeenCalledWith(
      "/api/operator/operations?workspaceId=archived-ws",
    );
    expect(renderToStaticMarkup(content)).toContain(
      "Observed Workspace: <code>archived-ws</code>",
    );
  });
});
