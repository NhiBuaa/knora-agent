from dataclasses import dataclass

import pytest

from knora.application.answer_question import AnswerQuestion
from knora.domain.models import GeneratedAnswer, RetrievedChunk


@dataclass
class StubRetriever:
    chunks: list[RetrievedChunk]

    async def retrieve(self, *, question: str, workspace_id: str) -> list[RetrievedChunk]:
        return self.chunks


class StubGenerator:
    async def generate(
        self, *, question: str, evidence: list[RetrievedChunk]
    ) -> GeneratedAnswer:
        return GeneratedAnswer(text="Khách hàng có thể yêu cầu hoàn tiền trong 30 ngày.")


@pytest.mark.asyncio
async def test_answer_uses_retrieved_evidence_as_citations() -> None:
    evidence = [
        RetrievedChunk(
            document_id="refund-policy",
            chunk_id="refund-policy:0",
            source="refund-policy.md",
            content="Yêu cầu hoàn tiền được chấp nhận trong vòng 30 ngày.",
            score=0.91,
        )
    ]
    service = AnswerQuestion(retriever=StubRetriever(evidence), generator=StubGenerator())

    result = await service.execute(
        question="Chính sách hoàn tiền là gì?", workspace_id="demo"
    )

    assert result.answer == "Khách hàng có thể yêu cầu hoàn tiền trong 30 ngày."
    assert result.refused is False
    assert [citation.source for citation in result.citations] == ["refund-policy.md"]


@pytest.mark.asyncio
async def test_answer_refuses_when_no_evidence_is_available() -> None:
    service = AnswerQuestion(retriever=StubRetriever([]), generator=StubGenerator())

    result = await service.execute(question="Ai vô địch World Cup?", workspace_id="demo")

    assert result.refused is True
    assert result.citations == []
    assert result.answer == (
        "Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này."
    )

