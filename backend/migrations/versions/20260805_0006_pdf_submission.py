"""Add durable PDF source submission and queued ingestion jobs."""

# Migration expressions are intentionally kept close to the approved schema contract.
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_0006"
down_revision: str | None = "20260731_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("document_versions", "normalized_content", nullable=True)
    op.alter_column("document_versions", "normalized_content_checksum", nullable=True)
    op.add_column("document_versions", sa.Column("raw_sha256", sa.String(64), nullable=True))
    op.add_column("document_versions", sa.Column("media_type", sa.String(100), nullable=True))
    op.add_column("document_versions", sa.Column("version_number", sa.Integer(), nullable=True))
    op.execute(
        """
        WITH numbered AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY document_id ORDER BY created_at, id
                   ) AS version_number
              FROM document_versions
        )
        UPDATE document_versions
           SET version_number = numbered.version_number
          FROM numbered
         WHERE document_versions.id = numbered.id
        """
    )
    op.alter_column("document_versions", "version_number", nullable=False)
    op.create_unique_constraint(
        "uq_document_versions_document_raw_sha256",
        "document_versions",
        ["document_id", "raw_sha256"],
    )
    op.create_unique_constraint(
        "uq_document_versions_document_version_number",
        "document_versions",
        ["document_id", "version_number"],
    )

    op.add_column(
        "documents",
        sa.Column("current_document_version_id", sa.String(36), nullable=True),
    )
    op.execute(
        """
        UPDATE documents
           SET current_document_version_id = document_versions.id
          FROM embedding_sets
          JOIN chunk_sets ON chunk_sets.id = embedding_sets.chunk_set_id
          JOIN document_versions
            ON document_versions.id = chunk_sets.document_version_id
         WHERE embedding_sets.id = documents.active_embedding_set_id
        """
    )
    op.execute(
        """
        UPDATE documents AS target
           SET current_document_version_id = (
              SELECT candidate.id
                FROM document_versions AS candidate
               WHERE candidate.document_id = target.id
               ORDER BY candidate.version_number DESC
               LIMIT 1
          )
         WHERE target.current_document_version_id IS NULL
           AND EXISTS (
              SELECT 1
                FROM document_versions
               WHERE document_versions.document_id = target.id
          )
        """
    )
    op.create_foreign_key(
        "fk_documents_current_document_version",
        "documents",
        "document_versions",
        ["current_document_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        CREATE FUNCTION validate_document_current_version()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            owner_document_id varchar(36);
        BEGIN
            IF NEW.current_document_version_id IS NULL THEN
                RETURN NEW;
            END IF;
            SELECT document_id INTO owner_document_id
              FROM document_versions
             WHERE id = NEW.current_document_version_id
             FOR SHARE;
            IF owner_document_id IS DISTINCT FROM NEW.id THEN
                RAISE EXCEPTION 'invalid current Document Version'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$;

        CREATE TRIGGER validate_document_current_version
        BEFORE INSERT OR UPDATE OF current_document_version_id ON documents
        FOR EACH ROW
        EXECUTE FUNCTION validate_document_current_version();
        """
    )

    op.create_table(
        "original_source_objects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_version_id", sa.String(36), sa.ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("object_key", sa.String(255), nullable=False),
        sa.Column("raw_sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("document_version_id", name="uq_original_source_objects_document_version"),
        sa.UniqueConstraint("object_key", name="uq_original_source_objects_object_key"),
    )
    op.create_index("ix_original_source_objects_workspace_id", "original_source_objects", ["workspace_id"])
    op.create_index("ix_original_source_objects_document_version_id", "original_source_objects", ["document_version_id"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_document_version_id", sa.String(36), sa.ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_object_id", sa.String(36), sa.ForeignKey("original_source_objects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("content_fingerprint", sa.Text(), nullable=False),
        sa.Column("parser_configuration_id", sa.String(100), nullable=False),
        sa.Column("normalizer_configuration_id", sa.String(100), nullable=False),
        sa.Column("chunking_configuration_id", sa.String(100), sa.ForeignKey("chunking_configurations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("embedding_configuration_id", sa.String(100), sa.ForeignKey("embedding_configurations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'retry_scheduled', 'succeeded', 'superseded', 'failed')",
            name="ck_ingestion_jobs_public_status",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "operation",
            "content_fingerprint",
            name="uq_ingestion_jobs_content_fingerprint",
        ),
    )
    for column in (
        "workspace_id",
        "document_id",
        "target_document_version_id",
        "source_object_id",
        "chunking_configuration_id",
        "embedding_configuration_id",
    ):
        op.create_index(f"ix_ingestion_jobs_{column}", "ingestion_jobs", [column])

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("request_fingerprint", sa.Text(), nullable=False),
        sa.Column("ingestion_job_id", sa.String(36), sa.ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "workspace_id", "operation", "key", name="uq_idempotency_records_scope"
        ),
    )
    op.create_index("ix_idempotency_records_workspace_id", "idempotency_records", ["workspace_id"])
    op.create_index("ix_idempotency_records_ingestion_job_id", "idempotency_records", ["ingestion_job_id"])


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("ingestion_jobs")
    op.drop_table("original_source_objects")
    op.execute("DROP TRIGGER validate_document_current_version ON documents")
    op.execute("DROP FUNCTION validate_document_current_version()")
    op.drop_constraint(
        "fk_documents_current_document_version", "documents", type_="foreignkey"
    )
    op.drop_column("documents", "current_document_version_id")
    op.drop_constraint(
        "uq_document_versions_document_version_number",
        "document_versions",
        type_="unique",
    )
    op.drop_constraint(
        "uq_document_versions_document_raw_sha256",
        "document_versions",
        type_="unique",
    )
    op.drop_column("document_versions", "version_number")
    op.drop_column("document_versions", "media_type")
    op.drop_column("document_versions", "raw_sha256")
    op.alter_column("document_versions", "normalized_content_checksum", nullable=False)
    op.alter_column("document_versions", "normalized_content", nullable=False)
