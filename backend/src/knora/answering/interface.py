from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QuestionCommand:
    workspace_id: str
    question: str


@dataclass(frozen=True, slots=True)
class CitationProjection:
    evidence_id: str
    document_id: str
    document_version_id: str
    source_key: str
    source_name: str
    heading_path: tuple[str, ...]
    start_line: int
    end_line: int
    excerpt: str
    content_checksum: str
    page_start: int | None = None
    page_end: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None


@dataclass(frozen=True, slots=True)
class QuestionResult:
    decision: str
    answer: str
    citations: tuple[CitationProjection, ...]
    refusal_reason: str | None
    trace_id: str
