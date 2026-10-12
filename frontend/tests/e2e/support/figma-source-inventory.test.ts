import { describe, expect, it } from "vitest";
import { fixtureResponse } from "./figma-state-fixtures";

describe("Figma fixture boundary", () => {
  it("admits one synthetic suggestion Turn only in the empty Conversation state", () => {
    const path =
      "/api/v1/workspaces/fixture-workspace/conversations/fixture-conversation/turns";
    expect(
      fixtureResponse("128:109", path, "POST", {
        question: "Summarize this workspace",
      }),
    ).toMatchObject({
      question: "Summarize this workspace",
      status: "answered",
    });
    expect(() =>
      fixtureResponse("128:119", path, "POST", {
        question: "Summarize this workspace",
      }),
    ).toThrow("Unrecognized fixture request");
    expect(() =>
      fixtureResponse("128:109", path, "POST", { question: "Other" }),
    ).toThrow("Unrecognized fixture request");
  });
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
    "rejects unsupported state, scope, credential and method requests (%s, %s, %s)",
    (state, path, method) => {
      expect(() => fixtureResponse(state, path, method)).toThrow(
        "Unrecognized fixture request",
      );
    },
  );
});
