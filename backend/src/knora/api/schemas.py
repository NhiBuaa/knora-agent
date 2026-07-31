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
    document_id: str
    chunk_id: str
    source: str


class QuestionResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    refused: bool


class HealthResponse(BaseModel):
    status: str
    service: str
