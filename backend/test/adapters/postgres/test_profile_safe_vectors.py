"""Database contract for profile-sized chunk embeddings."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from knora.infrastructure.settings import settings


@contextmanager
def _disposable_database() -> Iterator[str]:
    database_name = f"knora_profile_vectors_{uuid4().hex}"
    database_url = make_url(settings.database_url).set(database=database_name)
    admin_engine = create_engine(
        database_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin_engine.connect() as connection:
        connection.execute(text(f"CREATE DATABASE {database_name}"))
    try:
        yield database_url.render_as_string(hide_password=False)
    finally:
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name"
                ),
                {"name": database_name},
            )
            connection.execute(text(f"DROP DATABASE {database_name}"))
        admin_engine.dispose()


def _alembic_config(database_url: str) -> Config:
    backend_root = Path(__file__).parents[3]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _insert_embedding(
    connection, *, embedding_id: str, set_id: str, chunk_id: str, size: int
) -> None:
    connection.execute(
        text(
            "INSERT INTO chunk_embeddings (id, embedding_set_id, chunk_id, embedding) "
            "VALUES (:id, :set_id, :chunk_id, CAST(:embedding AS vector))"
        ),
        {
            "id": embedding_id,
            "set_id": set_id,
            "chunk_id": chunk_id,
            "embedding": "[" + ",".join(["0.125"] + ["0"] * (size - 1)) + "]",
        },
    )


def test_migration_preserves_1536_and_enforces_profile_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _disposable_database() as database_url:
        monkeypatch.setenv("KNORA_DATABASE_URL", database_url)
        config = _alembic_config(database_url)
        command.upgrade(config, "20260924_0045")
        engine = create_engine(database_url)
        ids = {
            name: uuid4().hex
            for name in (
                "workspace",
                "document",
                "version",
                "chunk_set",
                "chunk",
                "old_set",
                "new_set",
                "old_embedding",
                "new_embedding",
            )
        }
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO workspaces (id, name) VALUES (:id, 'Vector test')"),
                {"id": ids["workspace"]},
            )
            connection.execute(
                text(
                    """INSERT INTO documents
                    (id, workspace_id, source_key, source_name, archived)
                    VALUES (:id, :workspace, 'vector-test', 'vector.txt', false)"""
                ),
                {"id": ids["document"], "workspace": ids["workspace"]},
            )
            connection.execute(
                text(
                    """INSERT INTO document_versions
                    (id, document_id, normalized_content, normalized_content_checksum,
                     version_number)
                    VALUES (:id, :document, 'vector text', :checksum, 1)"""
                ),
                {"id": ids["version"], "document": ids["document"], "checksum": "a" * 64},
            )
            connection.execute(
                text(
                    """INSERT INTO chunking_configurations
                    (id, parser_version, chunker_version, tokenizer_name,
                     tokenizer_version, target_tokens, overlap_tokens, max_tokens)
                    VALUES ('vector-test-chunking', 'v1', 'v1', 'test', 'v1', 500, 75, 650)"""
                )
            )
            connection.execute(
                text(
                    """INSERT INTO chunk_sets
                    (id, document_version_id, chunking_configuration_id, status)
                    VALUES (:id, :version, 'vector-test-chunking', 'completed')"""
                ),
                {"id": ids["chunk_set"], "version": ids["version"]},
            )
            connection.execute(
                text(
                    """INSERT INTO chunks
                    (id, chunk_set_id, ordinal, heading_path, start_line, end_line,
                     content, content_checksum, token_count)
                    VALUES (:id, :chunk_set, 0, '[]', 1, 1,
                            'vector text', :checksum, 2)"""
                ),
                {"id": ids["chunk"], "chunk_set": ids["chunk_set"], "checksum": "b" * 64},
            )
            connection.execute(
                text(
                    """INSERT INTO embedding_configurations
                    (id, provider, model, dimensions, distance_metric)
                    VALUES ('embedding-local-m1-v2', 'deterministic-local',
                            'text-embedding-3-small', 1536, 'cosine'),
                           ('vector-test-1024', 'deterministic', 'other', 1024, 'cosine')"""
                )
            )
            connection.execute(
                text(
                    """INSERT INTO embedding_sets
                    (id, chunk_set_id, embedding_configuration_id, status)
                    VALUES (:old_set, :chunk_set, 'embedding-local-m1-v2', 'completed'),
                           (:new_set, :chunk_set, 'vector-test-1024', 'completed')"""
                ),
                {
                    "old_set": ids["old_set"],
                    "new_set": ids["new_set"],
                    "chunk_set": ids["chunk_set"],
                },
            )
            _insert_embedding(
                connection,
                embedding_id=ids["old_embedding"],
                set_id=ids["old_set"],
                chunk_id=ids["chunk"],
                size=1536,
            )
            old_value = connection.scalar(
                text("SELECT encode(vector_send(embedding), 'hex') "
                     "FROM chunk_embeddings WHERE id = :id"),
                {"id": ids["old_embedding"]},
            )

        command.upgrade(config, "head")
        with engine.begin() as connection:
            assert (
                connection.scalar(
                    text("SELECT vector_dims(embedding) FROM chunk_embeddings WHERE id = :id"),
                    {"id": ids["old_embedding"]},
                )
                == 1536
            )
            assert (
                connection.scalar(
                    text("SELECT encode(vector_send(embedding), 'hex') "
                         "FROM chunk_embeddings WHERE id = :id"),
                    {"id": ids["old_embedding"]},
                )
                == old_value
            )
            _insert_embedding(
                connection,
                embedding_id=ids["new_embedding"],
                set_id=ids["new_set"],
                chunk_id=ids["chunk"],
                size=1024,
            )
            assert (
                connection.scalar(
                    text("SELECT vector_dims(embedding) FROM chunk_embeddings WHERE id = :id"),
                    {"id": ids["new_embedding"]},
                )
                == 1024
            )
            with (
                pytest.raises(
                    IntegrityError, match="embedding dimension does not match configuration"
                ),
                connection.begin_nested(),
            ):
                _insert_embedding(
                    connection,
                    embedding_id=uuid4().hex,
                    set_id=ids["new_set"],
                    chunk_id=ids["chunk"],
                    size=1023,
                )
            with (
                pytest.raises(
                    IntegrityError, match="embedding dimension does not match configuration"
                ),
                connection.begin_nested(),
            ):
                connection.execute(
                    text("UPDATE chunk_embeddings SET embedding_set_id = :set_id WHERE id = :id"),
                    {"set_id": ids["new_set"], "id": ids["old_embedding"]},
                )

        with pytest.raises(RuntimeError, match="refusing downgrade"):
            command.downgrade(config, "20260924_0045")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20260925_0046"
            )
            assert (
                connection.scalar(
                    text("SELECT vector_dims(embedding) FROM chunk_embeddings WHERE id = :id"),
                    {"id": ids["new_embedding"]},
                )
                == 1024
            )
        engine.dispose()
