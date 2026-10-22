"""merge_evaluation_workbench_heads

Revision ID: 20261022_0157
Revises: 20261016_0051, 20261018_0156
Create Date: 2026-10-22 14:52:30.688014
"""

from collections.abc import Sequence

revision: str = "20261022_0157"
down_revision: str | None = ("20261016_0051", "20261018_0156")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
