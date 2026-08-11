"""Add typed orphan reconciliation disposition."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0026"
down_revision: str | None = "20260810_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("object_lifecycle_work")
    }
    if "reconciliation_disposition" not in columns:
        op.add_column(
            "object_lifecycle_work",
            sa.Column("reconciliation_disposition", sa.String(40), nullable=True),
        )


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("object_lifecycle_work")
    }
    if "reconciliation_disposition" in columns:
        op.drop_column("object_lifecycle_work", "reconciliation_disposition")
