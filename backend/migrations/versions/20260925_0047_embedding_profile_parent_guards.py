"""Keep persisted chunk vectors bound to their embedding profile."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260925_0047"
down_revision: str | None = "20260925_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION protect_referenced_embedding_dimensions()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.dimensions IS DISTINCT FROM OLD.dimensions
               AND EXISTS (
                   SELECT 1 FROM embedding_sets
                   WHERE embedding_configuration_id = OLD.id
               ) THEN
                RAISE EXCEPTION
                    'cannot change dimensions of a referenced embedding configuration'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER protect_referenced_embedding_dimensions
        BEFORE UPDATE OF dimensions ON embedding_configurations
        FOR EACH ROW EXECUTE FUNCTION protect_referenced_embedding_dimensions()
        """
    )
    op.execute(
        """
        CREATE FUNCTION protect_populated_embedding_set_profile()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.embedding_configuration_id
               IS DISTINCT FROM OLD.embedding_configuration_id
               AND EXISTS (
                   SELECT 1 FROM chunk_embeddings WHERE embedding_set_id = OLD.id
               ) THEN
                RAISE EXCEPTION
                    'cannot change embedding configuration of a populated Embedding Set'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER protect_populated_embedding_set_profile
        BEFORE UPDATE OF embedding_configuration_id ON embedding_sets
        FOR EACH ROW EXECUTE FUNCTION protect_populated_embedding_set_profile()
        """
    )
    # Parent UPDATEs must wait for an in-flight vector INSERT/UPDATE before
    # their guards inspect persisted rows. Share locks serialize the two paths.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_chunk_embedding_dimensions()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE expected_dimensions integer;
        BEGIN
            SELECT c.dimensions INTO expected_dimensions
            FROM embedding_sets AS s
            JOIN embedding_configurations AS c
              ON c.id = s.embedding_configuration_id
            WHERE s.id = NEW.embedding_set_id
            FOR SHARE OF s, c;

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


def downgrade() -> None:
    op.execute("DROP TRIGGER protect_populated_embedding_set_profile ON embedding_sets")
    op.execute("DROP FUNCTION protect_populated_embedding_set_profile()")
    op.execute(
        "DROP TRIGGER protect_referenced_embedding_dimensions ON embedding_configurations"
    )
    op.execute("DROP FUNCTION protect_referenced_embedding_dimensions()")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_chunk_embedding_dimensions()
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
