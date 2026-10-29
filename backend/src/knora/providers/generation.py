from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AnswerStatement:
    id: str
    text: str
    start: int
    end: int
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnswerProjection:
    answer_digest: str
    statements: tuple[AnswerStatement, ...]


@dataclass(frozen=True, slots=True)
class GenerationEvidence:
    evidence_id: str
    content: str


@dataclass(frozen=True, slots=True)
class GenerationResult:
    decision: str
    answer: str | None
    cited_evidence_ids: tuple[str, ...]
    refusal_reason: str | None
    provider: str = "unknown"
    model: str = "unknown"
    prompt_version: str = "unknown"
    finish_reason: str | None = None
    provider_request_id: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    cost: dict[str, str] = field(default_factory=dict)
    answer_projection: AnswerProjection | None = None


class GenerationProvider(Protocol):
    async def generate(
        self,
        *,
        question: str,
        evidence: tuple[GenerationEvidence, ...],
    ) -> GenerationResult: ...
