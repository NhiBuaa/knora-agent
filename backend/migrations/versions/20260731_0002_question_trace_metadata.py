"""Expand Question Trace metadata for cited retrieval."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260731_0002"
down_revision: str | None = "20260731_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "question_traces",
        sa.Column(
            "trace_schema_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "question_traces",
        sa.Column(
            "retrieval_configuration_id",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "question_traces",
        sa.Column(
            "embedding_configuration_id",
            sa.String(length=100),
            nullable=True,
        ),
    )
    for name in ("embedding_set_ids", "chunk_set_ids", "candidate_decisions", "parsed_markers"):
        op.add_column(
            "question_traces",
            sa.Column(
                name,
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )
    op.add_column(
        "question_traces",
        sa.Column("decision", sa.String(length=20), nullable=True),
    )
    op.add_column("question_traces", sa.Column("refusal_reason", sa.String(length=100)))
    op.add_column(
        "question_traces",
        sa.Column(
            "generation_status",
            sa.String(length=30),
            nullable=False,
            server_default="legacy-unrecorded",
        ),
    )
    op.add_column(
        "question_traces",
        sa.Column(
            "alias_mapping",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "question_traces",
        sa.Column(
            "validation_outcome",
            sa.String(length=30),
            nullable=False,
            server_default="legacy-unrecorded",
        ),
    )
    op.add_column(
        "question_traces",
        sa.Column("latency_ms", sa.Float(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE question_traces "
            "SET decision = CASE WHEN refused THEN 'REFUSAL' ELSE 'ANSWER' END"
        )
    )
    op.alter_column("question_traces", "decision", nullable=False)
    op.alter_column(
        "question_traces", "trace_schema_version", server_default="1"
    )
    op.alter_column("question_traces", "generation_status", server_default=None)
    op.alter_column("question_traces", "validation_outcome", server_default=None)


def downgrade() -> None:
    for name in (
        "trace_schema_version",
        "latency_ms",
        "validation_outcome",
        "alias_mapping",
        "generation_status",
        "refusal_reason",
        "decision",
        "parsed_markers",
        "candidate_decisions",
        "chunk_set_ids",
        "embedding_set_ids",
        "embedding_configuration_id",
        "retrieval_configuration_id",
    ):
        op.drop_column("question_traces", name, if_exists=True)
