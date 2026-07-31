from knora.domain.models import GeneratedAnswer, RetrievedChunk


class DemoRetriever:
    """Deterministic adapter that keeps the scaffold runnable without API keys."""

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks

    async def retrieve(self, *, question: str, workspace_id: str) -> list[RetrievedChunk]:
        if workspace_id != "demo":
            return []
        terms = {term.casefold().strip("?,.!:") for term in question.split() if len(term) > 3}
        matches = [
            chunk
            for chunk in self._chunks
            if terms.intersection(chunk.content.casefold().split())
        ]
        return matches[:3]


class DemoAnswerGenerator:
    async def generate(
        self, *, question: str, evidence: list[RetrievedChunk]
    ) -> GeneratedAnswer:
        del question
        return GeneratedAnswer(text=evidence[0].content)

