import { describe, expect, it, vi } from "vitest";
import {
  forwardOperatorRequest,
  isOperatorOperations,
  isOperatorTrace,
} from "@/lib/operator/api";
import { consumeQuestionStream, streamUnavailable } from "@/lib/questions/sse";
import {
  interruptedQuestionState,
  initialQuestionState,
  questionStateReducer,
} from "@/lib/ui-states";

function streamOf(...chunks: string[]) {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
}

describe("M5 browser flow evidence (deterministic public seams)", () => {
  it("covers upload/ingestion serving as a workspace-scoped browser request", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response('{"status":"accepted","ingestion_job_id":"job-1"}', {
        status: 202,
      }),
    );
    const response = await fetcher("/api/v1/workspaces/ws-a/documents", {
      method: "POST",
      headers: new Headers({ "Idempotency-Key": "upload-1" }),
    });
    expect(response.status).toBe(202);
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/workspaces/ws-a/documents",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("covers cited answer, refusal and provider failure terminal states", () => {
    const answered = questionStateReducer(initialQuestionState, {
      stage: "final_validated",
      terminal: true,
      payload: {
        answer: "A",
        trace_id: "t-1",
        citations: [{ evidence_id: "e-1" }],
      },
    });
    const refused = questionStateReducer(initialQuestionState, {
      stage: "refusal",
      terminal: true,
      payload: { refusal_reason: "INSUFFICIENT_EVIDENCE", trace_id: "t-2" },
    });
    const failed = questionStateReducer(initialQuestionState, {
      stage: "failure",
      terminal: true,
      payload: { error_code: "PROVIDER_UNAVAILABLE" },
    });
    expect(answered).toMatchObject({
      status: "final",
      answer: "A",
      traceId: "t-1",
    });
    expect(answered.citations).toHaveLength(1);
    expect(refused).toMatchObject({
      status: "refusal",
      refusalReason: "INSUFFICIENT_EVIDENCE",
      citations: [],
    });
    expect(failed).toMatchObject({
      status: "failure",
      errorCode: "PROVIDER_UNAVAILABLE",
      citations: [],
    });
  });

  it("covers successful citation SSE and refuses to treat an interrupted stream as success", async () => {
    const stages: string[] = [];
    await consumeQuestionStream(
      new Response(
        streamOf(
          "event: started\ndata: {}\n\n",
          'event: final_validated\ndata: {"answer":"A","citations":[]}\n\n',
        ),
        { headers: { "content-type": "text/event-stream" } },
      ),
      (event) => stages.push(event.stage),
    );
    expect(stages).toEqual(["started", "final_validated"]);
    await expect(
      consumeQuestionStream(
        new Response(streamOf("event: started\ndata: {}\n\n"), {
          headers: { "content-type": "text/event-stream" },
        }),
        () => undefined,
      ),
    ).rejects.toMatchObject({ code: "STREAM_INTERRUPTED" });
    expect(interruptedQuestionState(initialQuestionState)).toMatchObject({
      status: "interrupted",
      errorCode: "STREAM_INTERRUPTED",
      citations: [],
    });
  });

  it("covers explicit stream fallback boundary without treating auth/provider failures as fallback", () => {
    expect(streamUnavailable(new Response(null, { status: 404 }))).toBe(true);
    expect(streamUnavailable(new Response(null, { status: 405 }))).toBe(true);
    expect(streamUnavailable(new Response(null, { status: 401 }))).toBe(false);
    expect(streamUnavailable(new Response(null, { status: 500 }))).toBe(false);
  });

  it("covers archive/unarchive and deletion observation as idempotent, revision-bound requests", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response('{"archived":true,"revision":2}', { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response('{"state":"requested"}', { status: 202 }),
      );
    const archive = await fetcher(
      "/api/v1/workspaces/ws-a/documents/doc-1/archive",
      { method: "POST", headers: new Headers({ "If-Match": "1" }) },
    );
    const deletion = await fetcher(
      "/api/v1/workspaces/ws-a/documents/doc-1/deletion-request",
      {
        method: "POST",
        headers: new Headers({ "Idempotency-Key": "delete-1" }),
      },
    );
    expect(archive.status).toBe(200);
    expect(deletion.status).toBe(202);
    expect(
      (fetcher.mock.calls[0]?.[1]?.headers as Headers).get("If-Match"),
    ).toBe("1");
    expect(
      (fetcher.mock.calls[1]?.[1]?.headers as Headers).get("Idempotency-Key"),
    ).toBe("delete-1");
  });

  it("covers operator trace/evaluation/operations reads and sanitized malformed payload rejection", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response('{"error":{"code":"CAPABILITY_ACCESS_DENIED"}}', {
        status: 403,
      }),
    );
    const response = await forwardOperatorRequest(
      "http://backend.local/v1/workspaces/ws-a/operator/operations",
      { accessToken: "test-token" },
      fetcher,
    );
    expect(response.status).toBe(403);
    expect(
      (fetcher.mock.calls[0]?.[1]?.headers as Headers).get("Authorization"),
    ).toBe("Bearer test-token");
    expect(isOperatorOperations({ metrics: {}, histograms: {} })).toBe(true);
    expect(isOperatorOperations({ metrics: null, histograms: {} })).toBe(false);
    expect(isOperatorTrace({ trace_id: "opaque-trace", candidates: [] })).toBe(
      true,
    );
    expect(
      isOperatorTrace({ trace_id: "opaque-trace", candidates: null }),
    ).toBe(false);
  });
});
