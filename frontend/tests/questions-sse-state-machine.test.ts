import { describe, expect, it } from "vitest";
import { consumeQuestionStream } from "@/lib/questions/sse";

function streamOf(...chunks: string[]) {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({ start(controller) { chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk))); controller.close(); } });
}

describe("question SSE consumer", () => {
  it("parses ordered stages and one terminal event", async () => {
    const stages: string[] = [];
    await consumeQuestionStream(new Response(streamOf('event: started\ndata: {}\n\n', 'event: final_validated\ndata: {"answer":"ok","citations":[]}\n\n'), { headers: { "content-type": "text/event-stream" } }), (event) => stages.push(event.stage));
    expect(stages).toEqual(["started", "final_validated"]);
  });

  it("marks a disconnected stream interrupted instead of successful", async () => {
    await expect(consumeQuestionStream(new Response(streamOf('event: started\ndata: {}\n\n'), { headers: { "content-type": "text/event-stream" } }), () => undefined)).rejects.toMatchObject({ code: "STREAM_INTERRUPTED" });
  });
});
