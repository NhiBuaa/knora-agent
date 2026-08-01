"""Enforce active Embedding Set ownership and completion invariants."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260731_0003"
down_revision: str | None = "20260731_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION validate_document_active_embedding_set()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            owner_document_id varchar(36);
            embedding_set_status varchar(30);
        BEGIN
            IF NEW.active_embedding_set_id IS NULL THEN
                RETURN NEW;
            END IF;

            SELECT document_versions.document_id, embedding_sets.status
              INTO owner_document_id, embedding_set_status
              FROM embedding_sets
              JOIN chunk_sets
                ON chunk_sets.id = embedding_sets.chunk_set_id
             JOIN document_versions
                ON document_versions.id = chunk_sets.document_version_id
             WHERE embedding_sets.id = NEW.active_embedding_set_id
             FOR SHARE OF embedding_sets;

            IF owner_document_id IS DISTINCT FROM NEW.id
               OR embedding_set_status IS DISTINCT FROM 'completed' THEN
                RAISE EXCEPTION 'invalid active Embedding Set'
                    USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER validate_document_active_embedding_set
        BEFORE INSERT OR UPDATE OF active_embedding_set_id ON documents
        FOR EACH ROW
        EXECUTE FUNCTION validate_document_active_embedding_set()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER validate_document_active_embedding_set ON documents"
    )
    op.execute("DROP FUNCTION validate_document_active_embedding_set()")
