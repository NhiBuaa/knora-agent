"""Prevent mutation of an active Embedding Set into invalid state."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260731_0004"
down_revision: str | None = "20260731_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION protect_active_embedding_set()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF EXISTS (
                SELECT 1
                  FROM documents
                 WHERE documents.active_embedding_set_id = OLD.id
            ) AND (
                NEW.status IS DISTINCT FROM 'completed'
                OR NEW.chunk_set_id IS DISTINCT FROM OLD.chunk_set_id
                OR NEW.embedding_configuration_id
                   IS DISTINCT FROM OLD.embedding_configuration_id
            ) THEN
                RAISE EXCEPTION 'cannot invalidate an active Embedding Set'
                    USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER protect_active_embedding_set
        BEFORE UPDATE OF status, chunk_set_id, embedding_configuration_id
        ON embedding_sets
        FOR EACH ROW
        EXECUTE FUNCTION protect_active_embedding_set()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER protect_active_embedding_set ON embedding_sets")
    op.execute("DROP FUNCTION protect_active_embedding_set()")
