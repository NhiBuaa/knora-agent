import { describe, expect, it } from "vitest";
import { selectWorkspace } from "@/lib/auth/workspace";

describe("workspace selection", () => {
  it("accepts only a workspace present in authenticated claims", () => {
    expect(selectWorkspace(["ws-a", "ws-b"], "ws-b")).toBe("ws-b");
    expect(selectWorkspace(["ws-a", "ws-b"], "other")).toBe("ws-a");
    expect(selectWorkspace([], "ws-a")).toBeNull();
  });
});
