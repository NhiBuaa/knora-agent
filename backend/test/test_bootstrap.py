from decimal import Decimal

import pytest

from knora.bootstrap import build_provider_selection
from knora.infrastructure.settings import ObjectStoreSettings, Settings
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.deterministic.generation import DeterministicGenerationProvider
from knora.providers.embedding import EmbeddingConfiguration
from knora.providers.gemini.embedding import GeminiEmbeddingProvider
from knora.providers.openai_compatible.embedding import OpenAICompatibleEmbeddingProvider
from knora.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider


def compatible_settings(**overrides) -> Settings:
    values = {
        "provider_mode": "openai-compatible",
        "openai_base_url": "https://provider.example/v1",
        "openai_api_key": "runtime-secret",
        "openai_generation_model": "compatible-chat-model",
        "openai_pricing_version": "pricing-2026-07",
        "openai_embedding_input_cost_per_million_tokens": Decimal("0.02"),
        "openai_generation_input_cost_per_million_tokens": Decimal("1"),
        "openai_generation_output_cost_per_million_tokens": Decimal("2"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_bootstrap_selects_one_complete_provider_mode() -> None:
    local = build_provider_selection(Settings(_env_file=None))

    assert isinstance(local.embedding_provider, DeterministicEmbeddingProvider)
    assert isinstance(local.generation_provider, DeterministicGenerationProvider)
    assert local.embedding_configuration.provider == "deterministic-local"

    compatible = build_provider_selection(compatible_settings())

    assert isinstance(compatible.embedding_provider, OpenAICompatibleEmbeddingProvider)
    assert isinstance(compatible.generation_provider, OpenAICompatibleGenerationProvider)
    assert compatible.embedding_configuration.provider == "openai-compatible"
    assert compatible.embedding_configuration.model == "text-embedding-3-small"
    assert compatible.embedding_configuration.dimensions == 1536


def test_bootstrap_selects_embedding_and_generation_independently() -> None:
    selected = build_provider_selection(
        compatible_settings(
            embedding_provider="openai-compatible",
            generation_provider="deterministic-local",
            openai_generation_model=None,
            openai_generation_input_cost_per_million_tokens=None,
            openai_generation_output_cost_per_million_tokens=None,
        )
    )

    assert isinstance(selected.embedding_provider, OpenAICompatibleEmbeddingProvider)
    assert isinstance(selected.generation_provider, DeterministicGenerationProvider)
    assert selected.embedding_configuration.provider == "openai-compatible"


def test_bootstrap_selects_local_embedding_with_openai_generation() -> None:
    selected = build_provider_selection(
        compatible_settings(
            provider_mode="unused-legacy-mode",
            embedding_provider="deterministic-local",
            generation_provider="openai-compatible",
            openai_embedding_input_cost_per_million_tokens=None,
        )
    )

    assert isinstance(selected.embedding_provider, DeterministicEmbeddingProvider)
    assert isinstance(selected.generation_provider, OpenAICompatibleGenerationProvider)
    assert selected.embedding_configuration == EmbeddingConfiguration.milestone_one_local()


def test_bootstrap_requires_pricing_version_for_selected_openai_embedding() -> None:
    with pytest.raises(ValueError, match="openai_pricing_version"):
        build_provider_selection(
            compatible_settings(
                embedding_provider="openai-compatible",
                generation_provider="deterministic-local",
                openai_pricing_version=None,
            )
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"embedding_provider": "deterministic-local"},
        {"generation_provider": "deterministic-local"},
        {"embedding_provider": "ollama", "generation_provider": "deterministic-local"},
        {"embedding_provider": "deterministic-local", "generation_provider": "google-gemini-api"},
    ],
)
def test_bootstrap_rejects_partial_or_unknown_provider_selectors(overrides: dict) -> None:
    with pytest.raises(ValueError, match="provider configuration"):
        build_provider_selection(Settings(_env_file=None, **overrides))


def test_bootstrap_rejects_dimension_that_does_not_match_selected_profile() -> None:
    with pytest.raises(ValueError, match="embedding configuration.*1536 dimensions"):
        build_provider_selection(
            Settings(
                _env_file=None,
                embedding_provider="deterministic-local",
                generation_provider="deterministic-local",
                embedding_dimension=1024,
            )
        )


@pytest.mark.parametrize(
    "provider_mode",
    ["google-gemini-api", "openai-compatible", "unknown"],
)
def test_legacy_dimension_error_precedes_provider_configuration_errors(
    provider_mode: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="^invalid provider configuration: Milestone 1 embedding configuration expected "
        "1536 dimensions$",
    ):
        build_provider_selection(
            Settings(_env_file=None, provider_mode=provider_mode, embedding_dimension=1024)
        )


@pytest.mark.parametrize(
    "runtime_settings",
    [
        Settings(_env_file=None, embedding_dimension=1535),
        Settings(
            _env_file=None,
            provider_mode="deterministic-local",
            openai_embedding_model="gemini-embedding-001",
        ),
    ],
)
def test_bootstrap_rejects_an_unapproved_embedding_space(
    runtime_settings: Settings,
) -> None:
    with pytest.raises(ValueError, match="Milestone 1 embedding configuration"):
        build_provider_selection(runtime_settings)


def test_bootstrap_accepts_a_compatible_embedding_model_with_fixed_dimension() -> None:
    compatible = build_provider_selection(
        compatible_settings(openai_embedding_model="gemini-embedding-001")
    )

    assert compatible.embedding_configuration.provider == "openai-compatible"
    assert compatible.embedding_configuration.model == "gemini-embedding-001"
    assert compatible.embedding_configuration.dimensions == 1536


@pytest.mark.parametrize("provider_mode", ["unknown", "openai-compatible"])
def test_bootstrap_rejects_invalid_configuration_without_fallback(provider_mode: str) -> None:
    with pytest.raises(ValueError, match="provider configuration"):
        build_provider_selection(Settings(_env_file=None, provider_mode=provider_mode))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("openai_api_key", ""),
        ("openai_embedding_model", ""),
        ("openai_embedding_configuration_id", ""),
        ("openai_generation_model", ""),
        ("openai_pricing_version", ""),
        ("openai_embedding_input_cost_per_million_tokens", Decimal("-0.01")),
        ("openai_generation_input_cost_per_million_tokens", Decimal("-1")),
        ("openai_generation_output_cost_per_million_tokens", Decimal("-2")),
        ("openai_timeout_seconds", 0),
    ],
)
def test_bootstrap_rejects_unsafe_compatible_settings(field: str, value: object) -> None:
    with pytest.raises(ValueError, match="provider configuration"):
        build_provider_selection(compatible_settings(**{field: value}))


def test_settings_repr_redacts_provider_api_key() -> None:
    runtime_settings = compatible_settings(openai_api_key="unique-runtime-canary")

    assert "unique-runtime-canary" not in repr(runtime_settings)


def test_bootstrap_selects_exact_gemini_m3_embedding_contract() -> None:
    selected = build_provider_selection(
        compatible_settings(
            provider_mode="google-gemini-api",
            gemini_api_key="runtime-gemini-secret",
        )
    )

    assert isinstance(selected.embedding_provider, GeminiEmbeddingProvider)
    assert selected.embedding_configuration == EmbeddingConfiguration.gemini_m3()
    assert "runtime-gemini-secret" not in repr(
        Settings(_env_file=None, gemini_api_key="runtime-gemini-secret")
    )


def test_object_store_settings_are_typed_and_validate_backend() -> None:
    runtime = Settings(_env_file=None, object_store_backend="filesystem")
    selected = runtime.object_store_settings
    assert isinstance(selected, ObjectStoreSettings)
    assert selected.backend == "filesystem"

    with pytest.raises(ValueError, match="unsupported object_store_backend"):
        assert Settings(_env_file=None, object_store_backend="other").object_store_settings

    with pytest.raises(ValueError, match="access credentials"):
        runtime = Settings(
            _env_file=None,
            object_store_backend="s3_compatible",
            object_store_s3_bucket="knora",
        )
        _ = runtime.object_store_settings


@pytest.mark.parametrize("field", ["object_store_s3_access_key", "object_store_s3_secret_key"])
def test_object_store_settings_reject_empty_s3_credentials(field: str) -> None:
    values = {
        "_env_file": None,
        "object_store_backend": "s3_compatible",
        "object_store_s3_bucket": "knora",
        "object_store_s3_access_key": "access",
        "object_store_s3_secret_key": "secret",
        field: "",
    }
    runtime = Settings(**values)

    with pytest.raises(ValueError, match="access credentials"):
        _ = runtime.object_store_settings
