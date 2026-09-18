from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


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
    status: Literal["queued", "processing", "retry_scheduled", "succeeded", "superseded", "failed"]
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
    failure_reason: (
        Literal["retry_exhausted", "terminal_input", "terminal_config", "resource_limit"] | None
    ) = None
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
    status: Literal["queued", "processing", "retry_scheduled", "succeeded", "superseded", "failed"]


class DocumentResponse(BaseModel):
    document_id: str
    workspace_id: str
    source_key: str
    source_name: str
    archived: bool
    revision: int
    current_document_version_id: str | None = None
    serving_state: Literal["unavailable", "current", "previous"]
    ingestion_job_id: str | None = None
    ingestion_status: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


class DocumentDeletionRequestResponse(BaseModel):
    request_id: str
    document_id: str
    state: Literal["requested", "blocked", "processing", "succeeded", "failed"]
    failure_reason: str | None = None


JsonValue = Any


class OperatorCandidateResponse(BaseModel):
    chunk_id: str
    document_version_id: str
    chunk_set_id: str
    source_key: str
    chunk_ordinal: int
    workspace_id: str
    content: str
    start_line: int
    end_line: int
    final_rank: int
    fusion_score: float
    final_decision: str
    decision_reason: str | None = None
    vector_contribution: dict[str, JsonValue] | None = None
    fts_contribution: dict[str, JsonValue] | None = None


class OperatorTraceResponse(BaseModel):
    trace_id: str
    workspace_id: str
    retrieval_configuration_id: str
    embedding_configuration_id: str
    candidates: list[OperatorCandidateResponse]
    alias_mapping: dict[str, str]
    provider_metadata: dict[str, JsonValue]
    retrieval_latency_ms: float
    trace_schema_version: int
    branch_observation_schema_version: int
    fusion_policy_version: str | None = None
    embedding_set_ids: list[str]
    chunk_set_ids: list[str]
    candidate_decisions: list[dict[str, JsonValue]]
    branch_observations: list[dict[str, JsonValue]]
    decision: str
    answer: str | None = None
    refusal_reason: str | None = None
    parsed_markers: list[str]
    validation_outcome: str


class OperatorEvaluationResponse(BaseModel):
    report_id: str
    workspace_id: str
    availability: Literal["unavailable"]
    observation_failure: Literal["EVALUATION_REPORT_UNAVAILABLE"]


class OperatorHistogramResponse(BaseModel):
    count: int
    sum: float
    buckets: list[tuple[float, int]]


class OperatorOperationsResponse(BaseModel):
    workspace_id: str
    metrics: dict[str, int | float]
    configuration_version: str
    histograms: dict[str, OperatorHistogramResponse]


class ToolLifecycleProposalResponse(BaseModel):
    proposal_id: str
    state: str
    revision: int


class ToolLifecycleApprovalResponse(BaseModel):
    decision: str | None = None
    decided_at: datetime | None = None
    actor_kind: str | None = None


class ToolLifecycleExecutionObservationResponse(BaseModel):
    sequence: int
    observation_type: str
    failure_code: str | None = None
    observed_at: datetime


class ToolLifecycleExecutionResponse(BaseModel):
    lifecycle: str
    revision: int
    generation: int
    observations: list[ToolLifecycleExecutionObservationResponse]
    failure_code: str | None = None
    finalized_at: datetime | None = None


class ToolLifecycleReconciliationResponse(BaseModel):
    status: str
    observation_type: str | None = None
    failure_code: str | None = None
    observed_at: datetime | None = None


class ToolLifecycleItemResponse(BaseModel):
    proposal: ToolLifecycleProposalResponse
    approval: ToolLifecycleApprovalResponse
    execution: ToolLifecycleExecutionResponse | None = None
    reconciliation: ToolLifecycleReconciliationResponse | None = None


class ToolLifecycleResponse(BaseModel):
    availability: Literal["available", "unavailable", "observation_failure"]
    items: list[ToolLifecycleItemResponse] = Field(default_factory=list)
    code: str | None = None
