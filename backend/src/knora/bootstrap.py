from dataclasses import dataclass

from knora.infrastructure.settings import Settings
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.deterministic.generation import DeterministicGenerationProvider
from knora.providers.embedding import EmbeddingConfiguration, EmbeddingProvider
from knora.providers.generation import GenerationProvider
from knora.providers.openai_compatible.embedding import OpenAICompatibleEmbeddingProvider
from knora.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    embedding_provider: EmbeddingProvider
    generation_provider: GenerationProvider
    embedding_configuration: EmbeddingConfiguration


def build_provider_selection(runtime_settings: Settings) -> ProviderSelection:
    if runtime_settings.embedding_dimension != 1536:
        raise ValueError(
            "invalid provider configuration: Milestone 1 embedding configuration expected "
            "1536 dimensions"
        )
    if (
        runtime_settings.provider_mode == "deterministic-local"
        and runtime_settings.openai_embedding_model != "text-embedding-3-small"
    ):
        raise ValueError(
            "invalid provider configuration: Milestone 1 embedding configuration for "
            "deterministic-local expected text-embedding-3-small"
        )
    if runtime_settings.provider_mode == "deterministic-local":
        return ProviderSelection(
            embedding_provider=DeterministicEmbeddingProvider(),
            generation_provider=DeterministicGenerationProvider(),
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        )
    if runtime_settings.provider_mode != "openai-compatible":
        raise ValueError("invalid provider configuration: unsupported provider_mode")

    required_text = {
        "openai_base_url": runtime_settings.openai_base_url,
        "openai_embedding_model": runtime_settings.openai_embedding_model,
        "openai_embedding_configuration_id": (
            runtime_settings.openai_embedding_configuration_id
        ),
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
        raise ValueError(
            "invalid provider configuration: missing " + ", ".join(sorted(missing))
        )
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
