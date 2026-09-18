import type { QuestionEvent } from "@/lib/ui-states";

export class QuestionStreamError extends Error {
  code: "STREAM_INTERRUPTED" | "STREAM_UNAVAILABLE" | "STREAM_HTTP_ERROR";
  status?: number;
  constructor(code: QuestionStreamError["code"], status?: number) { super(code); this.name = "QuestionStreamError"; this.code = code; this.status = status; }
}

export function streamUnavailable(response: Response): boolean {
  return response.status === 404 || response.status === 405 || response.status === 501;
}

export async function consumeQuestionStream(response: Response, onEvent: (event: QuestionEvent) => void, signal?: AbortSignal): Promise<void> {
  if (!response.ok) throw new QuestionStreamError("STREAM_HTTP_ERROR", response.status);
  if (streamUnavailable(response)) throw new QuestionStreamError("STREAM_UNAVAILABLE", response.status);
  if (!response.body) throw new QuestionStreamError("STREAM_INTERRUPTED");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminalCount = 0;
  try {
    while (true) {
      if (signal?.aborted) throw new QuestionStreamError("STREAM_INTERRUPTED");
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      const records = buffer.split(/\r?\n\r?\n/);
      buffer = records.pop() ?? "";
      for (const record of records) {
        const event = parseRecord(record);
        if (!event) continue;
        if (event.terminal) {
          terminalCount += 1;
          if (terminalCount > 1) continue;
        }
        onEvent(event);
      }
      if (done) break;
    }
  } finally { reader.releaseLock(); }
  if (terminalCount !== 1) throw new QuestionStreamError("STREAM_INTERRUPTED");
}

function parseRecord(record: string): QuestionEvent | null {
  const lines = record.split(/\r?\n/);
  const name = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
  const data = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n");
  if (!name || !data) return null;
  try {
    const payload = JSON.parse(data) as Record<string, unknown>;
    const terminal = name === "final_validated" || name === "refusal" || name === "failure";
    return { stage: name as QuestionEvent["stage"], payload, terminal };
  } catch { return null; }
}
