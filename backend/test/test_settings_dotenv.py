from pathlib import Path

import pytest

from knora.bootstrap import build_provider_selection
from knora.infrastructure.settings import Settings


def test_shared_dotenv_ignores_non_backend_entries(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KNORA_DATABASE_URL", raising=False)
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

    selection = build_provider_selection(settings)
    assert selection.embedding_configuration.provider == "deterministic-local"
    assert selection.embedding_configuration.dimensions == 1536


@pytest.mark.parametrize("source", ["dotenv", "environment"])
def test_backend_does_not_validate_evaluation_only_configuration(monkeypatch, tmp_path, source):
    values = {
        "KNORA_SEMANTIC_SCORER_TIMEOUT_SECONDS": "not-a-backend-timeout",
        "KNORA_SEMANTIC_SCORER_INPUT_COST_PER_MILLION_TOKENS": "not-a-backend-price",
        "KNORA_SEMANTIC_SCORER_OUTPUT_COST_PER_MILLION_TOKENS": "not-a-backend-price",
    }
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    for name, value in values.items():
        monkeypatch.delenv(name, raising=False)
        if source == "environment":
            monkeypatch.setenv(name, value)
    if source == "dotenv":
        env_file.write_text("\n".join(f"{name}={value}" for name, value in values.items()))

    selection = build_provider_selection(Settings(_env_file=env_file))

    assert selection.embedding_configuration.id == "embedding-local-m1-v2"
