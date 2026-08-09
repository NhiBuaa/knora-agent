from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from knora.infrastructure.settings import settings


@contextmanager
def disposable_database() -> Iterator[str]:
    database_name = f"knora_coordination_migration_{uuid4().hex}"
    database_url = make_url(settings.database_url).set(database=database_name)
    admin_url = database_url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.execute(text(f"CREATE DATABASE {database_name}"))
    try:
        yield database_url.render_as_string(hide_password=False)
    finally:
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.execute(text(f"DROP DATABASE IF EXISTS {database_name}"))
        admin_engine.dispose()


def alembic_config(database_url: str) -> Config:
    backend_root = Path(__file__).parents[3]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def seed_legacy_job(database_url: str, *, status: str, attempt_count: int) -> str:
    engine = create_engine(database_url)
    ids = {
        "workspace": uuid4().hex,
        "document": uuid4().hex,
        "version": uuid4().hex,
        "source": uuid4().hex,
        "job": uuid4().hex,
    }
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO workspaces (id, name) VALUES (:id, 'Migration workspace')"),
            {"id": ids["workspace"]},
        )
        connection.execute(
            text(
                """
                INSERT INTO documents (id, workspace_id, source_key, source_name, revision)
                VALUES (:id, :workspace_id, 'migration/source', 'migration.pdf', 0)
                """
            ),
            {"id": ids["document"], "workspace_id": ids["workspace"]},
        )
        connection.execute(
            text(
                """
                INSERT INTO document_versions
                    (id, document_id, raw_sha256, media_type, version_number)
                VALUES (:id, :document_id, :raw_sha256, 'application/pdf', 1)
                """
            ),
            {
                "id": ids["version"],
                "document_id": ids["document"],
                "raw_sha256": "a" * 64,
            },
        )
        connection.execute(
            text("UPDATE documents SET current_document_version_id = :version_id WHERE id = :id"),
            {"version_id": ids["version"], "id": ids["document"]},
        )
        connection.execute(
            text(
                """
                INSERT INTO original_source_objects
                    (id, workspace_id, document_version_id, object_key, raw_sha256, byte_size,
                     media_type)
                VALUES (:id, :workspace_id, :version_id, 'migration/object', :raw_sha256, 1,
                        'application/pdf')
                """
            ),
            {
                "id": ids["source"],
                "workspace_id": ids["workspace"],
                "version_id": ids["version"],
                "raw_sha256": "a" * 64,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO chunking_configurations
                    (id, parser_version, chunker_version, tokenizer_name, tokenizer_version,
                     target_tokens, overlap_tokens, max_tokens)
                VALUES ('migration-chunking', 'parser-v1', 'chunker-v1', 'cl100k_base', '0.12.0',
                        500, 75, 650)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO embedding_configurations
                    (id, provider, model, dimensions, distance_metric)
                VALUES ('migration-embedding', 'deterministic', 'local-v1', 1536, 'cosine')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO ingestion_jobs
                    (id, workspace_id, operation, document_id, target_document_version_id,
                     source_object_id, content_fingerprint, parser_configuration_id,
                     normalizer_configuration_id, chunking_configuration_id,
                     embedding_configuration_id, status, attempt_count, max_attempts)
                VALUES
                    (:id, :workspace_id, 'submit_pdf', :document_id, :version_id, :source_id,
                     :fingerprint, 'parser-v1', 'normalizer-v1', 'migration-chunking',
                     'migration-embedding', :status, :attempt_count, 4)
                """
            ),
            {
                "id": ids["job"],
                "workspace_id": ids["workspace"],
                "document_id": ids["document"],
                "version_id": ids["version"],
                "source_id": ids["source"],
                "fingerprint": f"migration-{ids['job']}",
                "status": status,
                "attempt_count": attempt_count,
            },
        )
    engine.dispose()
    return ids["job"]


def test_migration_preserves_known_queued_legacy_job_without_attempt_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with disposable_database() as database_url:
        monkeypatch.setenv("KNORA_DATABASE_URL", database_url)
        config = alembic_config(database_url)
        command.upgrade(config, "20260805_0008")
        job_id = seed_legacy_job(database_url, status="queued", attempt_count=0)

        command.upgrade(config, "head")

        engine = create_engine(database_url)
        with engine.connect() as connection:
            job = connection.execute(
                text(
                    """
                    SELECT status, attempt_count, lease_version, worker_id, current_attempt_number
                      FROM ingestion_jobs
                     WHERE id = :job_id
                    """
                ),
                {"job_id": job_id},
            ).one()
            attempt_count = connection.execute(
                text(
                    "SELECT count(*) FROM ingestion_job_attempts "
                    "WHERE ingestion_job_id = :job_id"
                ),
                {"job_id": job_id},
            ).scalar_one()
        engine.dispose()

    assert job == ("queued", 0, 0, None, None)
    assert attempt_count == 0


@pytest.mark.parametrize(("status", "attempt_count"), [("processing", 0), ("queued", 1)])
def test_migration_rejects_unknown_legacy_attempt_history(
    status: str,
    attempt_count: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with disposable_database() as database_url:
        monkeypatch.setenv("KNORA_DATABASE_URL", database_url)
        config = alembic_config(database_url)
        command.upgrade(config, "20260805_0008")
        seed_legacy_job(database_url, status=status, attempt_count=attempt_count)

        with pytest.raises(Exception, match="queued zero-attempt legacy jobs"):
            command.upgrade(config, "head")
