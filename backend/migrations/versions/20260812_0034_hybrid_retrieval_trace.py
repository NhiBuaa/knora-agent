"""Add explicit-simple FTS indexing and hybrid retrieval trace provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0034"
down_revision: str | None = "20260810_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', content)", persisted=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_chunks_search_vector_fts_v1",
        "chunks",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.add_column(
        "question_traces", sa.Column("fusion_policy_version", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("question_traces", "fusion_policy_version")
    op.drop_index("ix_chunks_search_vector_fts_v1", table_name="chunks")
    op.drop_column("chunks", "search_vector")
