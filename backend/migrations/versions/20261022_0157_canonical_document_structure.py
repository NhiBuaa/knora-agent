"""add canonical document structure to chunk sets and chunks

Revision ID: 20261022_0157
Revises: 20261018_0156
"""

import sqlalchemy as sa
from alembic import op

revision = "20261022_0157"
down_revision = "20261018_0156"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chunk_sets", sa.Column("canonical_structure", sa.JSON(), nullable=True))
    op.add_column("chunks", sa.Column("block_ids", sa.JSON(), nullable=True))
    op.add_column("chunks", sa.Column("table_ids", sa.JSON(), nullable=True))
    op.add_column("chunks", sa.Column("search_context", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chunks", "search_context")
    op.drop_column("chunks", "table_ids")
    op.drop_column("chunks", "block_ids")
    op.drop_column("chunk_sets", "canonical_structure")
