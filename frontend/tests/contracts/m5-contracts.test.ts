import { describe, expect, it } from "vitest";
import { consumeQuestionStream } from "@/lib/questions/sse";
import type {
  KnoraApiPath,
  KnoraApiResponseFor,
  QuestionResponse,
  ToolLifecycleResponse,
} from "@/generated/knora-openapi";

const requiredPaths = [
  "/health",
  "/v1/questions",
  "/v1/questions/stream",
  "/v1/workspaces/{workspace_id}/documents",
  "/v1/workspaces/{workspace_id}/documents/{document_id}",
  "/v1/workspaces/{workspace_id}/ingestion-jobs/{ingestion_job_id}",
  "/v1/workspaces/{workspace_id}/operator/traces/{trace_id}",
  "/v1/workspaces/{workspace_id}/operator/evaluations/{report_id}",
  "/v1/workspaces/{workspace_id}/operator/operations",
  "/v1/workspaces/{workspace_id}/operator/tool-lifecycle",
] as const satisfies readonly KnoraApiPath[];

describe("M5 generated public contract", () => {
  it("keeps required REST paths and response mappings type-compatible", async () => {
    expect(requiredPaths).toHaveLength(10);
    const response: KnoraApiResponseFor<"/v1/questions"> = {
      answer: null,
      citations: [],
      decision: "REFUSAL",
      refusal_reason: "NO_EVIDENCE",
      trace_id: "trace-1",
      workspace_id: "ws-1",
    } satisfies QuestionResponse;
    expect(response.workspace_id).toBe("ws-1");
  });

  it("models sanitized lifecycle states without mutation authority", () => {
    const projection = {
      availability: "available",
      items: [
        {
          proposal: {
            proposal_id: "proposal-1",
            revision: 1,
            state: "approved",
          },
          approval: {},
        },
      ],
    } satisfies ToolLifecycleResponse;
    expect(projection).not.toHaveProperty("approve");
    expect(projection).not.toHaveProperty("execute");
    expect(JSON.stringify(projection)).not.toMatch(
      /api[_-]?key|secret|raw[_-]?token/i,
    );
  });

  it("accepts an ordered stream with exactly one terminal frame", async () => {
    const seen: string[] = [];
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode(
            'event: started\ndata: {}\n\nevent: final_validated\ndata: {"answer":"ok"}\n\n',
          ),
        );
        controller.close();
      },
    });
    await consumeQuestionStream(new Response(body), (event) =>
      seen.push(event.stage),
    );
    expect(seen).toEqual(["started", "final_validated"]);
  });
});
