"""Create Milestone 1 storage schema."""

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
        sa.Column("id", sa.String(length=200), primary_key=True),
        sa.Column("workspace_id", sa.String(length=100), sa.ForeignKey("workspaces.id")),
        sa.Column("source", sa.String(length=500), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"])
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(length=220), primary_key=True),
        sa.Column("document_id", sa.String(length=200), sa.ForeignKey("documents.id")),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_table(
        "question_traces",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=100), sa.ForeignKey("workspaces.id")),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("retrieved_chunk_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("refused", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("provider_metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_question_traces_workspace_id", "question_traces", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("question_traces")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("workspaces")

