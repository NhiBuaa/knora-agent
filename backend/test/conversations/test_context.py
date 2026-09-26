from __future__ import annotations

from importlib import import_module

import pytest
import tiktoken

from knora.answering.interface import QuestionResult
from knora.conversations.types import TurnView


def turn(
    turn_id: str,
    conversation_id: str,
    sequence: int,
    question: str,
    *,
    status: str = "answered",
    answer: str | None = "A validated answer.",
) -> TurnView:
    result = None
    if status == "answered":
        result = QuestionResult(
            decision="ANSWER",
            answer=answer,
            citations=(),
            refusal_reason=None,
            trace_id=f"trace-{turn_id}",
            workspace_id="workspace-1",
        )
    elif status == "refused":
        result = QuestionResult(
            decision="REFUSAL",
            answer=None,
            citations=(),
            refusal_reason="INSUFFICIENT_EVIDENCE",
            trace_id=f"trace-{turn_id}",
            workspace_id="workspace-1",
        )
    return TurnView(
        id=turn_id,
        conversation_id=conversation_id,
        sequence=sequence,
        question=question,
        status=status,
        stage=None,
        result=result,
        error_code=None,
    )


def build_context(*args, **kwargs):
    try:
        context_module = import_module("knora.conversations.context")
    except ModuleNotFoundError as error:
        if error.name != "knora.conversations.context":
            raise
        pytest.fail("The bounded Conversation context policy has not been implemented.")
    return context_module.build_context(*args, **kwargs)


def test_context_keeps_only_recent_valid_turns_from_the_current_conversation() -> None:
    history = (
        turn("turn-1", "conversation-1", 1, "Old question."),
        turn("turn-2", "conversation-1", 2, "A refused question.", status="refused"),
        turn("turn-3", "conversation-1", 3, "A failed question.", status="failed"),
        turn("turn-4", "another-conversation", 4, "Private other conversation."),
        turn("turn-5", "conversation-1", 5, "No validated result.", answer=None),
        turn("turn-6", "conversation-1", 6, "Recent question six."),
        turn("turn-7", "conversation-1", 7, "Recent question seven."),
        turn("turn-8", "conversation-1", 8, "Recent question eight."),
        turn("turn-9", "conversation-1", 9, "Recent question nine."),
        turn(
            "turn-current",
            "conversation-1",
            10,
            "Current question.",
            status="processing",
            answer=None,
        ),
    )

    context = build_context(
        history,
        workspace_id="workspace-1",
        conversation_id="conversation-1",
        current_turn_id="turn-current",
        question="Current question.",
    )

    assert context.policy_id == "conversation-context-v1"
    assert context.selected_turn_ids == ("turn-6", "turn-7", "turn-8", "turn-9")
    assert "turn-6" not in context.transcript
    assert "Recent question six." in context.transcript
    assert "Recent question nine." in context.transcript
    assert "A validated answer." in context.transcript
    assert "Private other conversation." not in context.transcript
    assert "Current question." not in context.transcript
    assert "Recent question six." in context.retrieval_query
    assert "Current question." in context.retrieval_query
    assert "A validated answer." not in context.retrieval_query


def test_context_can_reference_a_validated_refusal_but_never_treats_it_as_evidence() -> None:
    history = (
        turn("turn-answer", "conversation-1", 1, "What is documented?"),
        turn("turn-refusal", "conversation-1", 2, "What is not documented?", status="refused"),
        turn(
            "turn-current",
            "conversation-1",
            3,
            "Can you answer that now?",
            status="processing",
            answer=None,
        ),
    )

    context = build_context(
        history,
        workspace_id="workspace-1",
        conversation_id="conversation-1",
        current_turn_id="turn-current",
        question="Can you answer that now?",
    )

    assert context.selected_turn_ids == ("turn-answer", "turn-refusal")
    assert "What is not documented?" in context.transcript
    assert "INSUFFICIENT_EVIDENCE" in context.transcript
    assert "What is not documented?" in context.retrieval_query
    assert "INSUFFICIENT_EVIDENCE" not in context.retrieval_query


def test_context_obeys_token_budget_without_splitting_turns() -> None:
    answers = {sequence: f"Policy{sequence} " * 600 for sequence in range(1, 5)}
    history = tuple(
        turn(
            f"turn-{sequence}",
            "conversation-1",
            sequence,
            f"Question {sequence}.",
            answer=answers[sequence],
        )
        for sequence in range(1, 5)
    )

    context = build_context(
        history,
        workspace_id="workspace-1",
        conversation_id="conversation-1",
        current_turn_id="turn-current",
        question="What does that mean?",
    )

    encoding = tiktoken.get_encoding("cl100k_base")
    assert len(encoding.encode(context.transcript)) <= 2048
    assert 0 < len(context.selected_turn_ids) < 4
    for sequence in range(1, 5):
        selected = f"turn-{sequence}" in context.selected_turn_ids
        assert (f"Question {sequence}." in context.transcript) is selected
        assert (answers[sequence] in context.transcript) is selected
