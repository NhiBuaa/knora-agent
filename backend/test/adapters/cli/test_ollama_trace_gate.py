import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


def test_trace_lookup_requires_exact_workspace_conversation_turn_and_trace():
    path = Path(__file__).resolve().parents[4] / "scripts/verify_ollama_conversation.py"
    spec = importlib.util.spec_from_file_location("trace_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE question_traces (id TEXT, workspace_id TEXT, "
                "conversation_turn_id TEXT, question TEXT, decision TEXT, "
                "generation_status TEXT, provider_metadata TEXT)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE conversation_turns (id TEXT, workspace_id TEXT, "
                "conversation_id TEXT, result TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO question_traces VALUES "
                "('trace', 'workspace', 'turn', 'question', 'ANSWER', 'completed', '{}')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO conversation_turns VALUES ('turn', 'workspace', 'conversation', '{}')"
            )
        )
        binding = dict(
            workspace_id="workspace",
            conversation_id="conversation",
            turn_id="turn",
            trace_id="trace",
        )
        assert module.load_exact_trace(connection, binding)["decision"] == "ANSWER"
        for key in binding:
            with pytest.raises(ValueError, match="correlation"):
                module.load_exact_trace(connection, {**binding, key: "different"})
