"""Separate PDF raw identity from Milestone 1 normalized checksum identity."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_0007"
down_revision: str | None = "20260805_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "document_versions_document_id_normalized_content_checksum_key",
        "document_versions",
        type_="unique",
    )
    op.create_index(
        "uq_document_versions_document_normalized_checksum_m1",
        "document_versions",
        ["document_id", "normalized_content_checksum"],
        unique=True,
        postgresql_where=sa.text(
            "raw_sha256 IS NULL AND normalized_content_checksum IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_document_versions_document_normalized_checksum_m1",
        table_name="document_versions",
    )
    op.create_unique_constraint(
        "document_versions_document_id_normalized_content_checksum_key",
        "document_versions",
        ["document_id", "normalized_content_checksum"],
    )
