from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["knora-agent"]


class IngestionResponse(BaseModel):
    outcome: Literal["created", "reused"]
    activation_changed: bool
    document_id: str
    document_version_id: str
    chunk_set_id: str
    embedding_set_id: str
    chunking_configuration_id: str
    embedding_configuration_id: str
    chunk_count: int


class PdfSubmissionResponse(BaseModel):
    ingestion_job_id: str
    submission_outcome: Literal["created", "idempotency_replay", "deduplicated"]
    status: Literal["queued", "processing", "retry_scheduled", "succeeded", "superseded", "failed"]
    document_id: str
    document_version_id: str
