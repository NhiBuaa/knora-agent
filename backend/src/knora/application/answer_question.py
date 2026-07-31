from knora.application.ports import AnswerGenerator, Retriever
from knora.domain.models import Citation, QuestionAnswer

REFUSAL_MESSAGE = "Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này."


class AnswerQuestion:
    def __init__(self, *, retriever: Retriever, generator: AnswerGenerator) -> None:
        self._retriever = retriever
        self._generator = generator

    async def execute(self, *, question: str, workspace_id: str) -> QuestionAnswer:
        evidence = await self._retriever.retrieve(
            question=question,
            workspace_id=workspace_id,
        )
        if not evidence:
            return QuestionAnswer(answer=REFUSAL_MESSAGE, refused=True)

        generated = await self._generator.generate(question=question, evidence=evidence)
        citations = [
            Citation(
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                source=chunk.source,
            )
            for chunk in evidence
        ]
        return QuestionAnswer(answer=generated.text, citations=citations)
