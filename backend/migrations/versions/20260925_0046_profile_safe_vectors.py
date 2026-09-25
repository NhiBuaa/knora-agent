"""Allow profile-sized chunk vectors while enforcing configuration dimensions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0046"
down_revision: str | None = "20260924_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    if connection.execute(
        sa.text(
            """
            SELECT 1
            FROM chunk_embeddings AS e
            JOIN embedding_sets AS s ON s.id = e.embedding_set_id
            JOIN embedding_configurations AS c ON c.id = s.embedding_configuration_id
            WHERE vector_dims(e.embedding) <> c.dimensions
            LIMIT 1
            """
        )
    ).first():
        raise RuntimeError("existing chunk vector dimensions differ from their configuration")

    op.execute(
        "ALTER TABLE chunk_embeddings ALTER COLUMN embedding TYPE vector USING embedding::vector"
    )
    op.execute(
        """
        CREATE FUNCTION enforce_chunk_embedding_dimensions()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE expected_dimensions integer;
        BEGIN
            SELECT c.dimensions INTO expected_dimensions
            FROM embedding_sets AS s
            JOIN embedding_configurations AS c
              ON c.id = s.embedding_configuration_id
            WHERE s.id = NEW.embedding_set_id;

            IF expected_dimensions IS NULL
               OR vector_dims(NEW.embedding) <> expected_dimensions THEN
                RAISE EXCEPTION 'embedding dimension does not match configuration'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER chunk_embedding_dimensions
        BEFORE INSERT OR UPDATE OF embedding, embedding_set_id ON chunk_embeddings
        FOR EACH ROW EXECUTE FUNCTION enforce_chunk_embedding_dimensions()
        """
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(
        sa.text("SELECT 1 FROM chunk_embeddings WHERE vector_dims(embedding) <> 1536 LIMIT 1")
    ).first():
        raise RuntimeError("refusing downgrade: non-1536 chunk vectors would be lost")

    op.execute("DROP TRIGGER chunk_embedding_dimensions ON chunk_embeddings")
    op.execute("DROP FUNCTION enforce_chunk_embedding_dimensions()")
    op.execute(
        "ALTER TABLE chunk_embeddings "
        "ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)"
    )
