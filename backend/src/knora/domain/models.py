from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    document_id: str
    chunk_id: str
    source: str
    content: str
    score: float


@dataclass(frozen=True, slots=True)
class Citation:
    document_id: str
    chunk_id: str
    source: str


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    text: str


@dataclass(frozen=True, slots=True)
class QuestionAnswer:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    refused: bool = False
