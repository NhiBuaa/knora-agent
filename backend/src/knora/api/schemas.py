from pydantic import BaseModel, Field, field_validator


class QuestionRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=4000)

    @field_validator("workspace_id", "question")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class CitationResponse(BaseModel):
    evidence_id: str
    document_id: str
    document_version_id: str
    source_key: str
    source_name: str
    heading_path: list[str]
    start_line: int
    end_line: int
    excerpt: str
    content_checksum: str


class QuestionResponse(BaseModel):
    decision: str
    answer: str
    citations: list[CitationResponse]
    refusal_reason: str | None
    trace_id: str


class HealthResponse(BaseModel):
    status: str
    service: str
