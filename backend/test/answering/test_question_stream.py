from dataclasses import dataclass

import pytest

from knora.answering.interface import CitationProjection, QuestionCommand, QuestionResult
from knora.answering.module import AnswerQuestion
from knora.domain.access import WorkspacePrincipal


@dataclass
class StreamService(AnswerQuestion):
    result: QuestionResult | None = None


@pytest.mark.asyncio
async def test_execute_stream_emits_ordered_stages_and_one_validated_terminal_event() -> None:
    service = AnswerQuestion.__new__(AnswerQuestion)
    result = QuestionResult(
        workspace_id="workspace-a",
        decision="ANSWER",
        answer="Refunds are available. [[E1]]",
        citations=(
            CitationProjection(
                evidence_id="E1",
                document_id="doc-1",
                document_version_id="version-1",
                source_key="refunds",
                source_name="refunds.md",
                heading_path=("Refunds",),
                start_line=1,
                end_line=2,
                excerpt="Refunds are available.",
                content_checksum="sha256:x",
            ),
        ),
        refusal_reason=None,
        trace_id="trace-1",
    )

    async def execute(command, principal):
        assert command == QuestionCommand("workspace-a", "What is the policy?")
        assert principal.workspace_id == "workspace-a"
        return result

    service.execute = execute
    events = [
        event
        async for event in service.execute_stream(
            QuestionCommand("workspace-a", "What is the policy?"),
            WorkspacePrincipal("workspace-a", "key-1"),
        )
    ]

    assert [event.stage for event in events] == [
        "started",
        "retrieving",
        "selecting_evidence",
        "generating",
        "final_validated",
    ]
    assert sum(event.terminal for event in events) == 1
    assert events[-1].payload["answer"] == result.answer
    assert events[-1].payload["citations"][0]["evidence_id"] == "E1"
    assert "delta" not in events[-1].payload


@pytest.mark.asyncio
async def test_execute_stream_emits_refusal_terminal_without_citations() -> None:
    service = AnswerQuestion.__new__(AnswerQuestion)

    async def execute(command, principal):
        return QuestionResult(
            workspace_id=command.workspace_id,
            decision="REFUSAL",
            answer=None,
            citations=(),
            refusal_reason="INSUFFICIENT_EVIDENCE",
            trace_id="trace-refusal",
        )

    service.execute = execute
    events = [
        event
        async for event in service.execute_stream(
            QuestionCommand("workspace-a", "Unknown"),
            WorkspacePrincipal("workspace-a", "key-1"),
        )
    ]

    assert events[-1].stage == "refusal"
    assert events[-1].terminal is True
    assert events[-1].payload == {
        "refusal_reason": "INSUFFICIENT_EVIDENCE",
        "trace_id": "trace-refusal",
    }
