from decimal import Decimal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://knora:knora@localhost:5432/knora"
    object_store_root: str = ".knora-objects"
    embedding_dimension: int = 1536
    api_credentials_json: str = "[]"
    provider_mode: str = "deterministic-local"
    openai_base_url: str | None = None
    openai_api_key: SecretStr | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_configuration_id: str = "embedding-openai-m1-v1"
    openai_generation_model: str | None = None
    openai_pricing_version: str | None = None
    openai_embedding_input_cost_per_million_tokens: Decimal | None = None
    openai_generation_input_cost_per_million_tokens: Decimal | None = None
    openai_generation_output_cost_per_million_tokens: Decimal | None = None
    openai_timeout_seconds: float = 60.0
    semantic_scorer_base_url: str | None = None
    semantic_scorer_api_key: SecretStr | None = None
    semantic_scorer_model: str | None = None
    semantic_scorer_timeout_seconds: float = 60.0
    semantic_scorer_pricing_version: str | None = None
    semantic_scorer_input_cost_per_million_tokens: Decimal | None = None
    semantic_scorer_output_cost_per_million_tokens: Decimal | None = None

    model_config = SettingsConfigDict(env_file=".env", env_prefix="KNORA_")


settings = Settings()
