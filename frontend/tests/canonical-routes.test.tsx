import { describe, expect, it } from "vitest";
import { routes, destinationForResolution } from "@/lib/navigation/routes";

describe("canonical Workspace routes", () => {
  it("encodes each identity without creating a Conversation on navigation", () => {
    expect(routes.workspace("w /1")).toBe("/workspaces/w%20%2F1/conversations");
    expect(routes.documents("w")).toBe("/workspaces/w/documents");
    expect(routes.conversations("w")).toBe("/workspaces/w/conversations");
    expect(routes.conversation("w", "c")).toBe("/workspaces/w/conversations/c");
    expect(routes.document("w", "d")).toBe("/workspaces/w/documents/d");
  });

  it("routes all-archived owners to the collection surface", () => {
    expect(
      destinationForResolution({
        state: "NO_ACTIVE_WORKSPACE",
        workspace: null,
      }),
    ).toBe("/workspaces");
  });
});
