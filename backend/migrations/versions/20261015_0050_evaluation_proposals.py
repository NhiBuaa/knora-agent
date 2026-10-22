"""Retain Ragas proposal provenance separately from immutable gold.

Revision ID: 20261015_0050
Revises: 20261015_0049
"""

import sqlalchemy as sa
from alembic import op

revision = "20261015_0050"
down_revision = "20261015_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evaluation_dataset_drafts",
        sa.Column("proposal_batches", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("evaluation_dataset_drafts", "proposal_batches")
