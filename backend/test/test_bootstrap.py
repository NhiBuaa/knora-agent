from decimal import Decimal

import pytest

from knora.bootstrap import build_provider_selection
from knora.infrastructure.settings import Settings
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.deterministic.generation import DeterministicGenerationProvider
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
