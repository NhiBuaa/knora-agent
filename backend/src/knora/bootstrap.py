from dataclasses import dataclass

import httpx

from knora.infrastructure.settings import Settings
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.deterministic.generation import DeterministicGenerationProvider
from knora.providers.embedding import EmbeddingConfiguration, EmbeddingProvider
from knora.providers.gemini.embedding import GeminiEmbeddingProvider
from knora.providers.generation import GenerationProvider
from knora.providers.ollama.embedding import (
    OllamaEmbeddingProvider,
    resolve_ollama_embedding_configuration,
)
from knora.providers.openai_compatible.embedding import OpenAICompatibleEmbeddingProvider
from knora.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    embedding_provider: EmbeddingProvider
    generation_provider: GenerationProvider
    embedding_configuration: EmbeddingConfiguration


def build_provider_selection(runtime_settings: Settings) -> ProviderSelection:
    embedding_choice = runtime_settings.embedding_provider
    generation_choice = runtime_settings.generation_provider
    if (embedding_choice is None) != (generation_choice is None):
        raise ValueError("invalid provider configuration: both selectors are required")
    if embedding_choice is not None and generation_choice is not None:
        embedding, configuration = _build_selected_embedding(runtime_settings, embedding_choice)
        try:
            _validate_embedding_dimension(runtime_settings, configuration)
            _require_expected_profile(runtime_settings, configuration)
            generation = _build_selected_generation(runtime_settings, generation_choice)
        except Exception:
            close_embedding = getattr(embedding, "close", None)
            if close_embedding is not None:
                close_embedding()
            raise
        return ProviderSelection(embedding, generation, configuration)

    return _build_legacy_provider_selection(runtime_settings)


def _validate_embedding_dimension(
    runtime_settings: Settings, configuration: EmbeddingConfiguration
) -> None:
    if runtime_settings.embedding_dimension != configuration.dimensions:
        raise ValueError(
            "invalid provider configuration: Milestone 1 embedding configuration expected "
            f"{configuration.dimensions} dimensions"
        )


def _require_expected_profile(
    runtime_settings: Settings, configuration: EmbeddingConfiguration
) -> None:
    expected = runtime_settings.expected_embedding_configuration_id
    if expected is not None and configuration.id != expected:
        raise ValueError("invalid provider configuration: embedding profile mismatch")


def _build_selected_embedding(
    runtime_settings: Settings, choice: str
) -> tuple[EmbeddingProvider, EmbeddingConfiguration]:
    if choice == "ollama":
        if runtime_settings.ollama_timeout_seconds <= 0:
            raise ValueError("invalid provider configuration: timeout must be positive")
        if runtime_settings.ollama_embedding_model != "qwen3-embedding:0.6b":
            raise ValueError("invalid provider configuration: unsupported Ollama embedding model")
        provider = OllamaEmbeddingProvider(
            base_url=runtime_settings.ollama_base_url,
            timeout_seconds=runtime_settings.ollama_timeout_seconds,
        )
        try:
            with httpx.Client(
                base_url=runtime_settings.ollama_base_url,
                timeout=runtime_settings.ollama_timeout_seconds,
            ) as client:
                configuration = resolve_ollama_embedding_configuration(
                    client, runtime_settings.ollama_embedding_model
                )
        except Exception:
            provider.close()
            raise
        return provider, configuration
    if choice == "deterministic-local":
        if runtime_settings.openai_embedding_model != "text-embedding-3-small":
            raise ValueError(
                "invalid provider configuration: Milestone 1 embedding configuration for "
                "deterministic-local expected text-embedding-3-small"
            )
        return DeterministicEmbeddingProvider(), EmbeddingConfiguration.milestone_one_local()
    if choice == "google-gemini-api":
        api_key = runtime_settings.gemini_api_key
        if api_key is None or not api_key.get_secret_value():
            raise ValueError("invalid provider configuration: missing gemini_api_key")
        if runtime_settings.gemini_timeout_seconds <= 0:
            raise ValueError("invalid provider configuration: timeout must be positive")
        return (
            GeminiEmbeddingProvider(
                api_key=api_key.get_secret_value(),
                timeout_seconds=runtime_settings.gemini_timeout_seconds,
            ),
            EmbeddingConfiguration.gemini_m3(),
        )
    if choice == "openai-compatible":
        required = {
            "openai_base_url": runtime_settings.openai_base_url,
            "openai_embedding_model": runtime_settings.openai_embedding_model,
            "openai_embedding_configuration_id": runtime_settings.openai_embedding_configuration_id,
            "openai_pricing_version": runtime_settings.openai_pricing_version,
            "openai_embedding_input_cost_per_million_tokens": (
                runtime_settings.openai_embedding_input_cost_per_million_tokens
            ),
        }
        api_key = runtime_settings.openai_api_key
        missing = [name for name, value in required.items() if value is None or value == ""]
        if api_key is None or not api_key.get_secret_value():
            missing.append("openai_api_key")
        if missing:
            raise ValueError(
                "invalid provider configuration: missing " + ", ".join(sorted(missing))
            )
        cost = runtime_settings.openai_embedding_input_cost_per_million_tokens
        assert cost is not None
        assert api_key is not None
        if cost < 0:
            raise ValueError("invalid provider configuration: costs must be non-negative")
        if runtime_settings.openai_timeout_seconds <= 0:
            raise ValueError("invalid provider configuration: timeout must be positive")
        return (
            OpenAICompatibleEmbeddingProvider(
                base_url=str(runtime_settings.openai_base_url),
                api_key=api_key.get_secret_value(),
                input_cost_per_million_tokens=cost,
                pricing_version=str(runtime_settings.openai_pricing_version),
                timeout_seconds=runtime_settings.openai_timeout_seconds,
            ),
            EmbeddingConfiguration.openai_compatible(
                configuration_id=runtime_settings.openai_embedding_configuration_id,
                model=runtime_settings.openai_embedding_model,
            ),
        )
    raise ValueError("invalid provider configuration: unsupported embedding_provider")


def _build_selected_generation(runtime_settings: Settings, choice: str) -> GenerationProvider:
    if choice == "deterministic-local":
        return DeterministicGenerationProvider()
    if choice == "openai-compatible":
        if any(
            cost is not None and cost < 0
            for cost in (
                runtime_settings.openai_generation_input_cost_per_million_tokens,
                runtime_settings.openai_generation_output_cost_per_million_tokens,
            )
        ):
            raise ValueError("invalid provider configuration: costs must be non-negative")
        return _build_openai_generation(runtime_settings)
    raise ValueError("invalid provider configuration: unsupported generation_provider")


def _build_legacy_provider_selection(runtime_settings: Settings) -> ProviderSelection:
    if runtime_settings.provider_mode == "google-gemini-api":
        legacy_configuration = EmbeddingConfiguration.gemini_m3()
    elif runtime_settings.provider_mode == "openai-compatible":
        legacy_configuration = EmbeddingConfiguration.openai_compatible(
            configuration_id=runtime_settings.openai_embedding_configuration_id,
            model=runtime_settings.openai_embedding_model,
        )
    else:
        legacy_configuration = EmbeddingConfiguration.milestone_one_local()
    _validate_embedding_dimension(runtime_settings, legacy_configuration)
    _require_expected_profile(runtime_settings, legacy_configuration)

    if (
        runtime_settings.provider_mode == "deterministic-local"
        and runtime_settings.openai_embedding_model != "text-embedding-3-small"
    ):
        raise ValueError(
            "invalid provider configuration: Milestone 1 embedding configuration for "
            "deterministic-local expected text-embedding-3-small"
        )
    if runtime_settings.provider_mode == "deterministic-local":
        configuration = EmbeddingConfiguration.milestone_one_local()
        return ProviderSelection(
            embedding_provider=DeterministicEmbeddingProvider(),
            generation_provider=DeterministicGenerationProvider(),
            embedding_configuration=configuration,
        )
    if runtime_settings.provider_mode == "google-gemini-api":
        api_key = runtime_settings.gemini_api_key
        if api_key is None or not api_key.get_secret_value():
            raise ValueError("invalid provider configuration: missing gemini_api_key")
        if runtime_settings.gemini_timeout_seconds <= 0:
            raise ValueError("invalid provider configuration: timeout must be positive")
        generation = _build_openai_generation(runtime_settings)
        configuration = EmbeddingConfiguration.gemini_m3()
        return ProviderSelection(
            embedding_provider=GeminiEmbeddingProvider(
                api_key=api_key.get_secret_value(),
                timeout_seconds=runtime_settings.gemini_timeout_seconds,
            ),
            generation_provider=generation,
            embedding_configuration=configuration,
        )
    if runtime_settings.provider_mode != "openai-compatible":
        raise ValueError("invalid provider configuration: unsupported provider_mode")

    required_text = {
        "openai_base_url": runtime_settings.openai_base_url,
        "openai_embedding_model": runtime_settings.openai_embedding_model,
        "openai_embedding_configuration_id": (runtime_settings.openai_embedding_configuration_id),
        "openai_generation_model": runtime_settings.openai_generation_model,
        "openai_pricing_version": runtime_settings.openai_pricing_version,
    }
    costs = {
        "openai_embedding_input_cost_per_million_tokens": (
            runtime_settings.openai_embedding_input_cost_per_million_tokens
        ),
        "openai_generation_input_cost_per_million_tokens": (
            runtime_settings.openai_generation_input_cost_per_million_tokens
        ),
        "openai_generation_output_cost_per_million_tokens": (
            runtime_settings.openai_generation_output_cost_per_million_tokens
        ),
    }
    api_key = runtime_settings.openai_api_key
    missing = [name for name, value in required_text.items() if not value]
    if api_key is None or not api_key.get_secret_value():
        missing.append("openai_api_key")
    missing.extend(name for name, value in costs.items() if value is None)
    if missing:
        raise ValueError("invalid provider configuration: missing " + ", ".join(sorted(missing)))
    if any(value is not None and value < 0 for value in costs.values()):
        raise ValueError("invalid provider configuration: costs must be non-negative")
    if runtime_settings.openai_timeout_seconds <= 0:
        raise ValueError("invalid provider configuration: timeout must be positive")

    assert api_key is not None
    base_url = runtime_settings.openai_base_url
    generation_model = runtime_settings.openai_generation_model
    pricing_version = runtime_settings.openai_pricing_version
    embedding_cost = runtime_settings.openai_embedding_input_cost_per_million_tokens
    generation_input_cost = runtime_settings.openai_generation_input_cost_per_million_tokens
    generation_output_cost = runtime_settings.openai_generation_output_cost_per_million_tokens
    assert base_url is not None
    assert generation_model is not None
    assert pricing_version is not None
    assert embedding_cost is not None
    assert generation_input_cost is not None
    assert generation_output_cost is not None

    configuration = EmbeddingConfiguration.openai_compatible(
        configuration_id=runtime_settings.openai_embedding_configuration_id,
        model=runtime_settings.openai_embedding_model,
    )
    return ProviderSelection(
        embedding_provider=OpenAICompatibleEmbeddingProvider(
            base_url=base_url,
            api_key=api_key.get_secret_value(),
            input_cost_per_million_tokens=embedding_cost,
            pricing_version=pricing_version,
            timeout_seconds=runtime_settings.openai_timeout_seconds,
        ),
        generation_provider=OpenAICompatibleGenerationProvider(
            base_url=base_url,
            api_key=api_key.get_secret_value(),
            model=generation_model,
            input_cost_per_million_tokens=generation_input_cost,
            output_cost_per_million_tokens=generation_output_cost,
            pricing_version=pricing_version,
            timeout_seconds=runtime_settings.openai_timeout_seconds,
        ),
        embedding_configuration=configuration,
    )


def _build_openai_generation(runtime_settings: Settings) -> GenerationProvider:
    required = {
        "openai_base_url": runtime_settings.openai_base_url,
        "openai_generation_model": runtime_settings.openai_generation_model,
        "openai_pricing_version": runtime_settings.openai_pricing_version,
        "openai_generation_input_cost_per_million_tokens": (
            runtime_settings.openai_generation_input_cost_per_million_tokens
        ),
        "openai_generation_output_cost_per_million_tokens": (
            runtime_settings.openai_generation_output_cost_per_million_tokens
        ),
    }
    api_key = runtime_settings.openai_api_key
    missing = [name for name, value in required.items() if value is None or value == ""]
    if api_key is None or not api_key.get_secret_value():
        missing.append("openai_api_key")
    if missing:
        raise ValueError("invalid provider configuration: missing " + ", ".join(sorted(missing)))
    if runtime_settings.openai_timeout_seconds <= 0:
        raise ValueError("invalid provider configuration: timeout must be positive")
    assert api_key is not None
    return OpenAICompatibleGenerationProvider(
        base_url=str(runtime_settings.openai_base_url),
        api_key=api_key.get_secret_value(),
        model=str(runtime_settings.openai_generation_model),
        input_cost_per_million_tokens=runtime_settings.openai_generation_input_cost_per_million_tokens,  # type: ignore[arg-type]
        output_cost_per_million_tokens=runtime_settings.openai_generation_output_cost_per_million_tokens,  # type: ignore[arg-type]
        pricing_version=str(runtime_settings.openai_pricing_version),
        timeout_seconds=runtime_settings.openai_timeout_seconds,
    )
