"""Pin each active Embedding Set to its required configuration."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_0005"
down_revision: str | None = "20260731_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("active_embedding_configuration_id", sa.String(length=100), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_active_embedding_configuration",
        "documents",
        "embedding_configurations",
        ["active_embedding_configuration_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        UPDATE documents
           SET active_embedding_configuration_id = embedding_sets.embedding_configuration_id
          FROM embedding_sets
         WHERE embedding_sets.id = documents.active_embedding_set_id
        """
    )
    op.create_check_constraint(
        "ck_documents_active_embedding_pair",
        "documents",
        "(active_embedding_set_id IS NULL) = "
        "(active_embedding_configuration_id IS NULL)",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_document_active_embedding_set()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            owner_document_id varchar(36);
            embedding_set_status varchar(30);
            embedding_configuration_id varchar(100);
        BEGIN
            IF NEW.active_embedding_set_id IS NULL THEN
                RETURN NEW;
            END IF;

            SELECT document_versions.document_id,
                   embedding_sets.status,
                   embedding_sets.embedding_configuration_id
              INTO owner_document_id,
                   embedding_set_status,
                   embedding_configuration_id
              FROM embedding_sets
              JOIN chunk_sets
                ON chunk_sets.id = embedding_sets.chunk_set_id
              JOIN document_versions
                ON document_versions.id = chunk_sets.document_version_id
             WHERE embedding_sets.id = NEW.active_embedding_set_id
             FOR SHARE OF embedding_sets;

            IF owner_document_id IS DISTINCT FROM NEW.id
               OR embedding_set_status IS DISTINCT FROM 'completed'
               OR embedding_configuration_id
                  IS DISTINCT FROM NEW.active_embedding_configuration_id THEN
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
        DROP TRIGGER validate_document_active_embedding_set ON documents;
        CREATE TRIGGER validate_document_active_embedding_set
        BEFORE INSERT OR UPDATE OF active_embedding_set_id,
                                   active_embedding_configuration_id
        ON documents
        FOR EACH ROW
        EXECUTE FUNCTION validate_document_active_embedding_set()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER validate_document_active_embedding_set ON documents;
        CREATE TRIGGER validate_document_active_embedding_set
        BEFORE INSERT OR UPDATE OF active_embedding_set_id ON documents
        FOR EACH ROW
        EXECUTE FUNCTION validate_document_active_embedding_set()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_document_active_embedding_set()
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
              JOIN chunk_sets ON chunk_sets.id = embedding_sets.chunk_set_id
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
    op.drop_constraint("ck_documents_active_embedding_pair", "documents", type_="check")
    op.drop_constraint(
        "fk_documents_active_embedding_configuration", "documents", type_="foreignkey"
    )
    op.drop_column("documents", "active_embedding_configuration_id")
