from datetime import datetime
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


class SuccessfulJobResultResponse(BaseModel):
    document_version_id: str


class IngestionJobStatusResponse(BaseModel):
    ingestion_job_id: str
    status: Literal[
        "queued", "processing", "retry_scheduled", "succeeded", "superseded", "failed"
    ]
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime | None = None
    created_at: datetime
    started_at: datetime | None = None
    updated_at: datetime
    terminal_at: datetime | None = None
    target_document_version_id: str
    current_document_version_id: str | None
    served_document_version_id: str | None
    serving_state: Literal["unavailable", "current", "previous"]
    failure_reason: Literal[
        "retry_exhausted", "terminal_input", "terminal_config", "resource_limit"
    ] | None = None
    error_code: str | None = None
    result: SuccessfulJobResultResponse | None = None
    replacement_document_version_id: str | None = None
    replacement_ingestion_job_id: str | None = None
    reprocess_of_job_id: str | None = None
    poll_after_seconds: int


class ReprocessRequest(BaseModel):
    config_mode: Literal["same_as_job", "current"]
    config_source_job_id: str | None = None


class ReprocessResponse(BaseModel):
    ingestion_job_id: str
    document_version_id: str
    outcome: Literal["created", "reused", "idempotency_replay"]
    status: Literal[
        "queued", "processing", "retry_scheduled", "succeeded", "superseded", "failed"
    ]
