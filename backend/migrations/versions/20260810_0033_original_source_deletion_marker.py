"""Retain an auditable Original Source Object record after approved hard deletion."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0033"
down_revision: str | None = "20260810_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("original_source_objects")
    }
    if "deleted_at" not in columns:
        op.add_column(
            "original_source_objects",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("original_source_objects")
    }
    if "deleted_at" in columns:
        op.drop_column("original_source_objects", "deleted_at")
