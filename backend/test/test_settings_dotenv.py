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


def test_env_example_is_safe_to_copy_for_default_provider_mode(monkeypatch) -> None:
    for name in (
        "KNORA_EMBEDDING_PROVIDER",
        "KNORA_GENERATION_PROVIDER",
        "KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    env_example = Path(__file__).resolve().parents[2] / ".env.example"

    settings = Settings(_env_file=env_example)

    assert settings.provider_mode == "deterministic-local"
    assert settings.embedding_provider is None
    assert settings.generation_provider is None
    assert settings.expected_embedding_configuration_id is None
