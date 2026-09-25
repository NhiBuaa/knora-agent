import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToolLifecycleDisplay } from "@/components/tools/ToolLifecycle";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ToolLifecycleDisplay", () => {
  it("renders the server-projected proposal, approval, execution, and reconciliation values", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        availability: "available",
        items: [
          {
            proposal: {
              proposal_id: "proposal-1",
              state: "approved",
              revision: 3,
            },
            approval: {
              decision: "approved",
              decided_at: "2026-09-18T10:00:00Z",
              actor_kind: "operator",
            },
            execution: {
              lifecycle: "succeeded",
              revision: 4,
              generation: 1,
              observations: [
                {
                  sequence: 1,
                  observation_type: "execution_succeeded",
                  failure_code: null,
                  observed_at: "2026-09-18T10:01:00Z",
                },
              ],
              failure_code: null,
              finalized_at: "2026-09-18T10:01:01Z",
            },
            reconciliation: {
              status: "observed",
              observation_type: "execution_succeeded",
              failure_code: null,
              observed_at: "2026-09-18T10:01:00Z",
            },
          },
        ],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(React.createElement(ToolLifecycleDisplay, { workspaceId: "ws-1" }));

    expect(
      await screen.findByRole("heading", { name: /proposal-1/ }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("approved", { selector: "dd" })).toHaveLength(2);
    expect(
      screen.getByText("succeeded", { selector: "dd" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("observed", { selector: "dd" }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/workspaces/ws-1/operator/tool-lifecycle",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders an explicit unavailable state without fabricating lifecycle values", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ availability: "unavailable", items: [], code: null }),
        ),
    );

    render(React.createElement(ToolLifecycleDisplay, { workspaceId: "ws-1" }));

    expect(await screen.findByText(/unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText("not recorded")).not.toBeInTheDocument();
  });

  it("renders an explicit observation failure state and server code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          availability: "observation_failure",
          items: [],
          code: "TOOL_LIFECYCLE_OBSERVATION_FAILED",
        }),
      ),
    );

    render(React.createElement(ToolLifecycleDisplay, { workspaceId: "ws-1" }));

    expect(await screen.findByText(/observation failure/i)).toBeInTheDocument();
    expect(
      screen.getByText(/TOOL_LIFECYCLE_OBSERVATION_FAILED/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
