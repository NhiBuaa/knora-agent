import { describe, expect, it, vi } from "vitest";
import { readOperatorBff } from "../../lib/operator/bff";
import { OperationsContent } from "../../app/operator/operations/content";

vi.mock("../../lib/operator/bff", () => ({ readOperatorBff: vi.fn() }));

describe("operator page transport failures", () => {
  it("renders unavailable when the operations BFF request rejects", async () => {
    vi.mocked(readOperatorBff).mockRejectedValueOnce(new Error("BFF unavailable"));

    const page = await OperationsContent();

    expect(page.props.role).toBe("status");
    expect(page.props.children).toBe("Operational observation unavailable.");
  });
});
