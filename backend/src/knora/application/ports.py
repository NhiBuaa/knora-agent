from typing import Protocol

from knora.domain.models import GeneratedAnswer, RetrievedChunk


class Retriever(Protocol):
    async def retrieve(self, *, question: str, workspace_id: str) -> list[RetrievedChunk]: ...


class AnswerGenerator(Protocol):
    async def generate(
        self, *, question: str, evidence: list[RetrievedChunk]
    ) -> GeneratedAnswer: ...


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
