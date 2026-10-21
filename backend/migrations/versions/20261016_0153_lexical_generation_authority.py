"""Add lexical request/activation authority without changing legacy projections.

Revision ID: 20261016_0153
Revises: 4949b27855f4
"""

import sqlalchemy as sa
from alembic import op

revision = "20261016_0153"
down_revision = "4949b27855f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lexical_generations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(100),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            sa.String(36),
            sa.ForeignKey("document_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "chunk_set_id",
            sa.String(36),
            sa.ForeignKey("chunk_sets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("source_revision", sa.Integer, nullable=False),
        sa.Column("workspace_revision", sa.Integer, nullable=False),
        sa.Column("profile_digest", sa.String(64), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("expected_count", sa.Integer, nullable=False),
        sa.Column("acknowledged_count", sa.Integer, nullable=True),
        sa.Column("manifest", sa.JSON, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("revision > 0", name="ck_lexical_generations_revision"),
        sa.CheckConstraint("expected_count > 0", name="ck_lexical_generations_count"),
        sa.CheckConstraint(
            "status IN ('requested', 'active', 'revoked')", name="ck_lexical_generations_status"
        ),
        sa.UniqueConstraint(
            "document_id", "revision", name="uq_lexical_generations_document_revision"
        ),
    )
    op.create_index("ix_lexical_generations_document_id", "lexical_generations", ["document_id"])
    op.create_table(
        "lexical_heads",
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column(
            "desired_generation_id",
            sa.String(36),
            sa.ForeignKey("lexical_generations.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "active_generation_id",
            sa.String(36),
            sa.ForeignKey("lexical_generations.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.CheckConstraint("revision >= 0", name="ck_lexical_heads_revision"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM lexical_generations)")):
        raise RuntimeError("lexical downgrade requires an empty owned database")
    op.drop_table("lexical_heads")
    op.drop_index("ix_lexical_generations_document_id", table_name="lexical_generations")
    op.drop_table("lexical_generations")
