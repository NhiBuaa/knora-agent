// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
vi.mock("@/lib/auth/session", () => ({ getSession: vi.fn() }));
import { getSession } from "@/lib/auth/session";
import { POST } from "@/app/api/[...path]/route";

afterEach(() => vi.resetAllMocks());

describe("Workbench authenticated route boundary", () => {
  it.each(["evaluation", "%65valuation"])(
    "does not expose %s through the generic proxy",
    async (section) => {
      const response = await POST(
        new Request(
          "https://app.example/api/v1/workspaces/workspace-a/evaluation/runs",
          { method: "POST" },
        ),
        {
          params: Promise.resolve({
            path: ["v1", "workspaces", "workspace-a", section, "runs"],
          }),
        },
      );
      expect(response.status).toBe(404);
      expect(getSession).not.toHaveBeenCalled();
    },
  );
});
