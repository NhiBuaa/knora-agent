from pathlib import Path

from knora.infrastructure.settings import Settings


def test_shared_dotenv_ignores_non_backend_entries(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "KNORA_DATABASE_URL=postgresql+psycopg://knora:knora@localhost:5432/local",
                "KNORA_CANONICAL_MINIO_ACCESS_KEY=local-access",
                "KEYCLOAK_ISSUER=http://127.0.0.1:8180/realms/knora",
                "SESSION_SECRET=local-session-secret",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.database_url.endswith("/local")


def test_process_environment_overrides_dotenv(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KNORA_DATABASE_URL=postgresql+psycopg://knora:knora@localhost:5432/from-file\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "KNORA_DATABASE_URL",
        "postgresql+psycopg://knora:knora@localhost:5432/from-process",
    )

    settings = Settings(_env_file=env_file)

    assert settings.database_url.endswith("/from-process")
