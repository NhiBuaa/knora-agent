import { describe, expect, it } from "vitest";
import { buildOperatorBffUrl } from "../../lib/operator/bff";

describe("operator page BFF boundary", () => {
  it("builds same-origin BFF URLs instead of backend URLs", () => {
    expect(buildOperatorBffUrl("http://localhost:3000", "/api/operator/operations")).toBe(
      "http://localhost:3000/api/operator/operations",
    );
    expect(() => buildOperatorBffUrl("http://localhost:3000", "/v1/workspaces/ws/operator/operations")).toThrow(
      "Operator pages must use the operator BFF",
    );
  });
});
