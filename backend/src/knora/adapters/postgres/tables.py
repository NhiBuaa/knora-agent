from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from knora.adapters.postgres.database import Base


class WorkspaceTable(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentTable(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("workspace_id", "source_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    source_key: Mapped[str] = mapped_column(String(500), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    active_embedding_set_id: Mapped[str | None] = mapped_column(
        ForeignKey("embedding_sets.id", ondelete="RESTRICT"), nullable=True
    )
    active_embedding_configuration_id: Mapped[str | None] = mapped_column(
        ForeignKey("embedding_configurations.id", ondelete="RESTRICT"), nullable=True
    )
    current_document_version_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "document_versions.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_documents_current_document_version",
        ),
        nullable=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentVersionTable(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "raw_sha256"),
        UniqueConstraint("document_id", "version_number"),
        Index(
            "uq_document_versions_document_normalized_checksum_m1",
            "document_id",
            "normalized_content_checksum",
            unique=True,
            postgresql_where=text(
                "raw_sha256 IS NULL AND normalized_content_checksum IS NOT NULL"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), index=True
    )
    normalized_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_content_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OriginalSourceObjectTable(Base):
    __tablename__ = "original_source_objects"
    __table_args__ = (UniqueConstraint("document_version_id"), UniqueConstraint("object_key"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"), index=True
    )
    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestionJobTable(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "operation", "content_fingerprint"),
        CheckConstraint(
            "status IN ('queued', 'processing', 'retry_scheduled', "
            "'succeeded', 'superseded', 'failed')",
            name="ck_ingestion_jobs_public_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), index=True
    )
    target_document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"), index=True
    )
    source_object_id: Mapped[str] = mapped_column(
        ForeignKey("original_source_objects.id", ondelete="RESTRICT"), index=True
    )
    content_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    parser_configuration_id: Mapped[str] = mapped_column(String(100), nullable=False)
    normalizer_configuration_id: Mapped[str] = mapped_column(String(100), nullable=False)
    chunking_configuration_id: Mapped[str] = mapped_column(
        ForeignKey("chunking_configurations.id", ondelete="RESTRICT"), index=True
    )
    embedding_configuration_id: Mapped[str] = mapped_column(
        ForeignKey("embedding_configurations.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_attempt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_attempt_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_attempt_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    safe_failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    terminal_outcome_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    replacement_document_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=True
    )
    replacement_ingestion_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"), nullable=True
    )
    reprocess_of_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    last_heartbeat_operation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_heartbeat_request_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_heartbeat_resulting_lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IngestionJobAttemptTable(Base):
    __tablename__ = "ingestion_job_attempts"
    __table_args__ = (
        Index(
            "uq_ingestion_job_attempts_one_open",
            "ingestion_job_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
        UniqueConstraint("claim_operation_id", name="uq_ingestion_job_attempts_claim_operation"),
        UniqueConstraint(
            "transition_operation_kind",
            "transition_operation_id",
            name="uq_ingestion_job_attempts_transition_operation_kind",
        ),
    )

    ingestion_job_id: Mapped[str] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"), primary_key=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[str] = mapped_column(String(100), nullable=False)
    lease_version: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    initial_lease_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    claim_operation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    claim_request_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    closure_cause: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_cause: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_cause_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cause_mapping_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    safe_failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    terminal_outcome_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transition_operation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    transition_operation_kind: Mapped[str | None] = mapped_column(String(30), nullable=True)
    transition_request_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_policy_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retry_policy_result: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retry_jitter_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retry_window_upper_bound_microseconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    retry_delay_microseconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    replacement_document_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=True
    )
    replacement_ingestion_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"), nullable=True
    )


class IdempotencyRecordTable(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("workspace_id", "operation", "key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    ingestion_job_id: Mapped[str] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReprocessAuditTable(Base):
    __tablename__ = "reprocess_audit_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    actor_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"), index=True
    )
    requested_config_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    resolved_config_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    config_source_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"), nullable=True
    )
    ingestion_job_id: Mapped[str] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"), index=True
    )
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChunkingConfigurationTable(Base):
    __tablename__ = "chunking_configurations"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    chunker_version: Mapped[str] = mapped_column(String(100), nullable=False)
    tokenizer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tokenizer_version: Mapped[str] = mapped_column(String(100), nullable=False)
    target_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    overlap_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False)


class ChunkSetTable(Base):
    __tablename__ = "chunk_sets"
    __table_args__ = (
        Index(
            "uq_chunk_sets_legacy_identity",
            "document_version_id",
            "chunking_configuration_id",
            unique=True,
            postgresql_where=text(
                "parser_configuration_id IS NULL AND normalizer_configuration_id IS NULL"
            ),
        ),
        Index(
            "uq_chunk_sets_pdf_derivation_identity",
            "document_version_id",
            "parser_configuration_id",
            "normalizer_configuration_id",
            "chunking_configuration_id",
            unique=True,
            postgresql_where=text(
                "parser_configuration_id IS NOT NULL AND "
                "normalizer_configuration_id IS NOT NULL"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"), index=True
    )
    chunking_configuration_id: Mapped[str] = mapped_column(
        ForeignKey("chunking_configurations.id", ondelete="RESTRICT"), index=True
    )
    parser_configuration_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    normalizer_configuration_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class ChunkTable(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("chunk_set_id", "ordinal"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    chunk_set_id: Mapped[str] = mapped_column(
        ForeignKey("chunk_sets.id", ondelete="RESTRICT"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[list] = mapped_column(JSON, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)


class EmbeddingConfigurationTable(Base):
    __tablename__ = "embedding_configurations"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_metric: Mapped[str] = mapped_column(String(30), nullable=False)


class EmbeddingSetTable(Base):
    __tablename__ = "embedding_sets"
    __table_args__ = (UniqueConstraint("chunk_set_id", "embedding_configuration_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    chunk_set_id: Mapped[str] = mapped_column(
        ForeignKey("chunk_sets.id", ondelete="RESTRICT"), index=True
    )
    embedding_configuration_id: Mapped[str] = mapped_column(
        ForeignKey("embedding_configurations.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class ChunkEmbeddingTable(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (UniqueConstraint("embedding_set_id", "chunk_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    embedding_set_id: Mapped[str] = mapped_column(
        ForeignKey("embedding_sets.id", ondelete="RESTRICT"), index=True
    )
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="RESTRICT"), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)


class QuestionTraceTable(Base):
    __tablename__ = "question_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    trace_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retrieval_configuration_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_configuration_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_set_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    chunk_set_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    retrieved_chunk_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    candidate_decisions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    refused: Mapped[bool] = mapped_column(Boolean, nullable=False)
    refusal_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_status: Mapped[str] = mapped_column(String(30), nullable=False)
    alias_mapping: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    parsed_markers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    validation_outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
