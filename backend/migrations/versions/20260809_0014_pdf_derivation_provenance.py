"""Add PDF derivation identity and page-bounded chunk provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0014"
down_revision: str | None = "20260809_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chunk_sets",
        sa.Column("parser_configuration_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "chunk_sets",
        sa.Column("normalizer_configuration_id", sa.String(100), nullable=True),
    )
    op.add_column("chunks", sa.Column("page_start", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("page_end", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("start_offset", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("end_offset", sa.Integer(), nullable=True))
    op.create_index(
        "ix_chunk_sets_parser_configuration_id",
        "chunk_sets",
        ["parser_configuration_id"],
    )
    op.create_index(
        "ix_chunk_sets_normalizer_configuration_id",
        "chunk_sets",
        ["normalizer_configuration_id"],
    )

    op.drop_constraint(
        "chunk_sets_document_version_id_chunking_configuration_id_key",
        "chunk_sets",
        type_="unique",
    )
    op.create_index(
        "uq_chunk_sets_legacy_identity",
        "chunk_sets",
        ["document_version_id", "chunking_configuration_id"],
        unique=True,
        postgresql_where=sa.text(
            "parser_configuration_id IS NULL AND normalizer_configuration_id IS NULL"
        ),
    )
    op.create_index(
        "uq_chunk_sets_pdf_derivation_identity",
        "chunk_sets",
        [
            "document_version_id",
            "parser_configuration_id",
            "normalizer_configuration_id",
            "chunking_configuration_id",
        ],
        unique=True,
        postgresql_where=sa.text(
            "parser_configuration_id IS NOT NULL AND "
            "normalizer_configuration_id IS NOT NULL"
        ),
    )
    op.create_check_constraint(
        "ck_chunk_sets_pdf_configuration_pair",
        "chunk_sets",
        "(parser_configuration_id IS NULL) = (normalizer_configuration_id IS NULL)",
    )
    op.create_check_constraint(
        "ck_chunks_pdf_provenance",
        "chunks",
        """
        (page_start IS NULL AND page_end IS NULL AND start_offset IS NULL AND end_offset IS NULL)
        OR
        (page_start IS NOT NULL AND page_start >= 1
         AND page_end IS NOT NULL AND page_end = page_start
         AND start_offset IS NOT NULL AND start_offset >= 0
         AND end_offset IS NOT NULL AND end_offset > start_offset)
        """,
    )


def downgrade() -> None:
    op.drop_constraint("ck_chunks_pdf_provenance", "chunks", type_="check")
    op.drop_constraint("ck_chunk_sets_pdf_configuration_pair", "chunk_sets", type_="check")
    op.drop_index("ix_chunk_sets_normalizer_configuration_id", table_name="chunk_sets")
    op.drop_index("ix_chunk_sets_parser_configuration_id", table_name="chunk_sets")
    op.drop_index("uq_chunk_sets_pdf_derivation_identity", table_name="chunk_sets")
    op.drop_index("uq_chunk_sets_legacy_identity", table_name="chunk_sets")
    op.create_unique_constraint(
        "chunk_sets_document_version_id_chunking_configuration_id_key",
        "chunk_sets",
        ["document_version_id", "chunking_configuration_id"],
    )
    op.drop_column("chunks", "end_offset")
    op.drop_column("chunks", "start_offset")
    op.drop_column("chunks", "page_end")
    op.drop_column("chunks", "page_start")
    op.drop_column("chunk_sets", "normalizer_configuration_id")
    op.drop_column("chunk_sets", "parser_configuration_id")
