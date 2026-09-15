import json

from knora.answering.interface import QuestionEvent


def format_sse_event(event: QuestionEvent) -> str:
    """Serialize a question event as one standards-compatible SSE record."""
    payload = json.dumps(event.payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event.stage}\ndata: {payload}\n\n"
