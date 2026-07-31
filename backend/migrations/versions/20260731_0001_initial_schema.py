"""Create the Milestone 1 storage schema."""

# Alembic's declarative column expressions are intentionally kept readable on one line.
# ruff: noqa: E501

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260731_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=100), sa.ForeignKey("workspaces.id", ondelete="RESTRICT")),
        sa.Column("source_key", sa.String(length=500), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "source_key"),
    )
    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"])
    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="RESTRICT")),
        sa.Column("normalized_content", sa.Text(), nullable=False),
        sa.Column("normalized_content_checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "normalized_content_checksum"),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_table(
        "chunking_configurations",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("parser_version", sa.String(length=100), nullable=False),
        sa.Column("chunker_version", sa.String(length=100), nullable=False),
        sa.Column("tokenizer_name", sa.String(length=100), nullable=False),
        sa.Column("tokenizer_version", sa.String(length=100), nullable=False),
        sa.Column("target_tokens", sa.Integer(), nullable=False),
        sa.Column("overlap_tokens", sa.Integer(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
    )
    op.create_table(
        "chunk_sets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_version_id", sa.String(length=36), sa.ForeignKey("document_versions.id", ondelete="RESTRICT")),
        sa.Column("chunking_configuration_id", sa.String(length=100), sa.ForeignKey("chunking_configurations.id", ondelete="RESTRICT")),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.UniqueConstraint("document_version_id", "chunking_configuration_id"),
    )
    op.create_index("ix_chunk_sets_document_version_id", "chunk_sets", ["document_version_id"])
    op.create_index("ix_chunk_sets_chunking_configuration_id", "chunk_sets", ["chunking_configuration_id"])
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("chunk_set_id", sa.String(length=36), sa.ForeignKey("chunk_sets.id", ondelete="RESTRICT")),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading_path", postgresql.JSONB(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_checksum", sa.String(length=64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("chunk_set_id", "ordinal"),
    )
    op.create_index("ix_chunks_chunk_set_id", "chunks", ["chunk_set_id"])
    op.create_table(
        "embedding_configurations",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("distance_metric", sa.String(length=30), nullable=False),
    )
    op.create_table(
        "embedding_sets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("chunk_set_id", sa.String(length=36), sa.ForeignKey("chunk_sets.id", ondelete="RESTRICT")),
        sa.Column("embedding_configuration_id", sa.String(length=100), sa.ForeignKey("embedding_configurations.id", ondelete="RESTRICT")),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.UniqueConstraint("chunk_set_id", "embedding_configuration_id"),
    )
    op.create_index("ix_embedding_sets_chunk_set_id", "embedding_sets", ["chunk_set_id"])
    op.create_index("ix_embedding_sets_embedding_configuration_id", "embedding_sets", ["embedding_configuration_id"])
    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("embedding_set_id", sa.String(length=36), sa.ForeignKey("embedding_sets.id", ondelete="RESTRICT")),
        sa.Column("chunk_id", sa.String(length=36), sa.ForeignKey("chunks.id", ondelete="RESTRICT")),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=False),
        sa.UniqueConstraint("embedding_set_id", "chunk_id"),
    )
    op.create_index("ix_chunk_embeddings_embedding_set_id", "chunk_embeddings", ["embedding_set_id"])
    op.create_index("ix_chunk_embeddings_chunk_id", "chunk_embeddings", ["chunk_id"])
    op.add_column("documents", sa.Column("active_embedding_set_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_documents_active_embedding_set",
        "documents",
        "embedding_sets",
        ["active_embedding_set_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "question_traces",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=100), sa.ForeignKey("workspaces.id", ondelete="RESTRICT")),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("retrieved_chunk_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("refused", sa.Boolean(), nullable=False),
        sa.Column("provider_metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_question_traces_workspace_id", "question_traces", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("question_traces")
    op.drop_constraint("fk_documents_active_embedding_set", "documents", type_="foreignkey")
    op.drop_column("documents", "active_embedding_set_id")
    op.drop_table("chunk_embeddings")
    op.drop_table("embedding_sets")
    op.drop_table("embedding_configurations")
    op.drop_table("chunks")
    op.drop_table("chunk_sets")
    op.drop_table("chunking_configurations")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("workspaces")
