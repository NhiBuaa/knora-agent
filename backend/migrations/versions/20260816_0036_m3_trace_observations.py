"""Persist versioned M3 branch observations in question traces."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0036"
down_revision: str | None = "20260813_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "question_traces",
        sa.Column(
            "branch_observation_schema_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "question_traces",
        sa.Column(
            "branch_observations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("question_traces", "trace_schema_version", server_default="2")


def downgrade() -> None:
    op.drop_column("question_traces", "branch_observations")
    op.drop_column("question_traces", "branch_observation_schema_version")
    op.alter_column("question_traces", "trace_schema_version", server_default="1")
