"""Add Evaluation Workbench dataset source and run persistence.

Revision ID: 20261015_0049
Revises: 4949b27855f4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261015_0049"
down_revision: str | None = "4949b27855f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_dataset_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cases", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("reviews", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("reference", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evaluation_dataset_drafts_workspace_id", "evaluation_dataset_drafts", ["workspace_id"]
    )
    op.create_table(
        "evaluation_dataset_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("document_version_id", sa.String(length=36), nullable=False),
        sa.Column("original_source_object_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("snapshot_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["evaluation_dataset_drafts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["document_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["original_source_object_id"], ["original_source_objects.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint("dataset_id", "idempotency_key"),
    )
    op.create_index(
        "ix_evaluation_dataset_sources_workspace_id", "evaluation_dataset_sources", ["workspace_id"]
    )
    op.create_index(
        "ix_evaluation_dataset_sources_dataset_id", "evaluation_dataset_sources", ["dataset_id"]
    )
    op.create_index(
        "ix_evaluation_dataset_sources_document_version_id",
        "evaluation_dataset_sources",
        ["document_version_id"],
    )
    op.create_index(
        "ix_evaluation_dataset_sources_original_source_object_id",
        "evaluation_dataset_sources",
        ["original_source_object_id"],
    )
    op.create_table(
        "evaluation_extraction_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("configuration_sha256", sa.String(length=64), nullable=False),
        sa.Column("extraction_sha256", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=100), nullable=False),
        sa.Column("extraction_options_version", sa.String(length=100), nullable=False),
        sa.Column("normalizer_version", sa.String(length=100), nullable=False),
        sa.Column("pages", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["evaluation_dataset_sources.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "configuration_sha256", "extraction_sha256"),
    )
    op.create_index(
        "ix_evaluation_extraction_snapshots_workspace_id",
        "evaluation_extraction_snapshots",
        ["workspace_id"],
    )
    op.create_index(
        "ix_evaluation_extraction_snapshots_source_id",
        "evaluation_extraction_snapshots",
        ["source_id"],
    )
    op.create_table(
        "evaluation_gold_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("frozen_json", sa.String(), nullable=False),
        sa.Column("reviews", sa.JSON(), nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["evaluation_dataset_drafts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "version"),
        sa.UniqueConstraint("dataset_id", "digest"),
    )
    op.create_index(
        "ix_evaluation_gold_versions_workspace_id", "evaluation_gold_versions", ["workspace_id"]
    )
    op.create_index(
        "ix_evaluation_gold_versions_dataset_id", "evaluation_gold_versions", ["dataset_id"]
    )
    op.create_table(
        "evaluation_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("selection_digest", sa.String(length=64), nullable=False),
        sa.Column("selection", sa.JSON(), nullable=False),
        sa.Column("profile_id", sa.String(length=100), nullable=False),
        sa.Column("binding", sa.JSON(), nullable=False),
        sa.Column("execution_status", sa.String(length=32), nullable=False),
        sa.Column("quality_status", sa.String(length=32), nullable=False),
        sa.Column("observations", sa.JSON(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=True),
        sa.Column("attempt_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("run_id"),
        sa.UniqueConstraint("workspace_id", "idempotency_key"),
    )
    op.create_index("ix_evaluation_runs_workspace_id", "evaluation_runs", ["workspace_id"])
    op.create_table(
        "evaluation_run_preflights",
        sa.Column("preflight_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("preflight_id"),
    )
    op.create_index(
        "ix_evaluation_run_preflights_workspace_id", "evaluation_run_preflights", ["workspace_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evaluation_run_preflights_workspace_id", table_name="evaluation_run_preflights"
    )
    op.drop_table("evaluation_run_preflights")
    op.drop_index("ix_evaluation_runs_workspace_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_index("ix_evaluation_gold_versions_dataset_id", table_name="evaluation_gold_versions")
    op.drop_index("ix_evaluation_gold_versions_workspace_id", table_name="evaluation_gold_versions")
    op.drop_table("evaluation_gold_versions")
    op.drop_index(
        "ix_evaluation_extraction_snapshots_source_id", table_name="evaluation_extraction_snapshots"
    )
    op.drop_index(
        "ix_evaluation_extraction_snapshots_workspace_id",
        table_name="evaluation_extraction_snapshots",
    )
    op.drop_table("evaluation_extraction_snapshots")
    op.drop_index(
        "ix_evaluation_dataset_sources_original_source_object_id",
        table_name="evaluation_dataset_sources",
    )
    op.drop_index(
        "ix_evaluation_dataset_sources_document_version_id", table_name="evaluation_dataset_sources"
    )
    op.drop_index(
        "ix_evaluation_dataset_sources_dataset_id", table_name="evaluation_dataset_sources"
    )
    op.drop_index(
        "ix_evaluation_dataset_sources_workspace_id", table_name="evaluation_dataset_sources"
    )
    op.drop_table("evaluation_dataset_sources")
    op.drop_index(
        "ix_evaluation_dataset_drafts_workspace_id", table_name="evaluation_dataset_drafts"
    )
    op.drop_table("evaluation_dataset_drafts")
