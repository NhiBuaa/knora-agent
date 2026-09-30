"""Check local Conversation traces without printing document text or credentials."""

import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import create_engine, text

POSITIVE = "cần trình bày báo cáo bao nhiêu chương?"
NEGATIVE = "Hạn cuối nộp báo cáo chính xác là ngày nào?"
EXPECTED_CHUNK = "f3081d1e2e6d069f574162a260070f5bc844ac906fac9dd51ebe8868882c0b2c"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", type=datetime.fromisoformat, required=True)
    args = parser.parse_args()
    database_url = os.environ.get("KNORA_DATABASE_URL")
    if not database_url:
        print("CONVERSATION_TRACE_DATABASE_REQUIRED", file=sys.stderr)
        return 2

    try:
        engine = create_engine(database_url)
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT qt.question, qt.decision, qt.generation_status, "
                    "qt.provider_metadata, ct.result "
                    "FROM question_traces qt JOIN conversation_turns ct "
                    "ON ct.id = qt.conversation_turn_id "
                    "WHERE qt.created_at >= :since AND qt.question IN (:positive, :negative) "
                    "ORDER BY qt.created_at DESC"
                ),
                {"since": args.since, "positive": POSITIVE, "negative": NEGATIVE},
            ).mappings()
            by_question = {row["question"]: row for row in rows}
    except Exception:
        print("CONVERSATION_TRACE_UNAVAILABLE", file=sys.stderr)
        return 2

    positive = by_question.get(POSITIVE)
    negative = by_question.get(NEGATIVE)
    if positive is None or negative is None:
        print("CONVERSATION_TRACE_MISSING", file=sys.stderr)
        return 1

    positive_metadata = positive["provider_metadata"] or {}
    negative_metadata = negative["provider_metadata"] or {}
    positive_result = positive["result"] or {}
    negative_result = negative["result"] or {}
    positive_generation = positive_metadata.get("generation", {})
    negative_generation = negative_metadata.get("generation", {})
    positive_citations = positive_result.get("citations", [])
    expected_model = os.environ.get("KNORA_OLLAMA_GENERATION_MODEL", "qwen3:8b")
    if not (
        positive["decision"] == "ANSWER"
        and positive["generation_status"] == "completed"
        and positive_generation.get("provider") == "ollama"
        and positive_generation.get("model") == expected_model
        and any(item.get("content_checksum") == EXPECTED_CHUNK for item in positive_citations)
    ):
        print("OLLAMA_POSITIVE_TRACE_FAILED", file=sys.stderr)
        return 1
    if not (
        negative["decision"] == "REFUSAL"
        and negative["generation_status"] == "completed"
        and negative_generation.get("provider") == "ollama"
        and negative_generation.get("model") == expected_model
        and not negative_result.get("citations")
    ):
        print("OLLAMA_NEGATIVE_TRACE_FAILED", file=sys.stderr)
        return 1
    print("OLLAMA_CONVERSATION_TRACE_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
