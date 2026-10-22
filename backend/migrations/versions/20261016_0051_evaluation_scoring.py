"""Keep supplementary scoring separate from saved Q&A and deterministic reports.

Revision ID: 20261016_0051
Revises: 20261015_0050
"""

import sqlalchemy as sa
from alembic import op

revision = "20261016_0051"
down_revision = "20261015_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evaluation_runs",
        sa.Column("scoring_batches", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("evaluation_runs", "scoring_batches")
