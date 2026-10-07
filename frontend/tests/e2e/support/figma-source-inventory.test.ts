import { describe, expect, it } from "vitest";
import { fixtureResponse } from "./figma-state-fixtures";

describe("Figma fixture boundary", () => {
  it("provides a complete deterministic Document projection at the approved fixture path", () => {
    expect(
      fixtureResponse(
        "128:122",
        "/api/v1/workspaces/fixture-workspace/documents/fixture-document",
        "GET",
      ),
    ).toMatchObject({
      document_id: "fixture-document",
      workspace_id: "fixture-workspace",
      source_name: "Teacher Manh – Guidelines 2024.pdf",
      serving_state: "current",
      answer_availability: "available",
      revision: 7,
    });
  });
  it.each([
    ["unknown", "/api/v1/workspaces/fixture-workspace", "GET"],
    ["128:122", "/api/v1/workspaces/another-workspace/documents", "GET"],
    ["128:122", "/api/auth/logout", "POST"],
    [
      "128:122",
      "/api/v1/workspaces/fixture-workspace/documents/fixture-document",
      "DELETE",
    ],
  ])(
    "rejects unsupported state, scope, credential and method requests",
    (state, path, method) => {
      expect(() => fixtureResponse(state, path, method)).toThrow(
        "Unrecognized fixture request",
      );
    },
  );
});
