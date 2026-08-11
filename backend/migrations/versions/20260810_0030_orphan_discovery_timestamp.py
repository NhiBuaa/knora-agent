"""Persist the first authoritative orphan-discovery timestamp."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0030"
down_revision: str | None = "20260810_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("object_lifecycle_work")
    }
    if "discovery_recorded_at" not in columns:
        op.add_column(
            "object_lifecycle_work",
            sa.Column("discovery_recorded_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("object_lifecycle_work")
    }
    if "discovery_recorded_at" in columns:
        op.drop_column("object_lifecycle_work", "discovery_recorded_at")
