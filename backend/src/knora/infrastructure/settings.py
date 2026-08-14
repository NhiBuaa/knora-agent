from dataclasses import dataclass
from decimal import Decimal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True, slots=True)
class ObjectStoreSettings:
    """Typed runtime selection for the application-facing ObjectStore backend."""

    backend: str
    root: str
    s3_endpoint: str | None
    s3_bucket: str | None
    s3_region: str | None
    s3_access_key: SecretStr | None
    s3_secret_key: SecretStr | None

    @classmethod
    def from_runtime(cls, runtime: "Settings") -> "ObjectStoreSettings":
        if runtime.object_store_backend not in {"filesystem", "s3_compatible"}:
            raise ValueError("unsupported object_store_backend")
        if runtime.object_store_backend == "s3_compatible":
            if not runtime.object_store_s3_bucket:
                raise ValueError("S3-compatible ObjectStore requires a bucket")
            if (
                runtime.object_store_s3_access_key is None
                or runtime.object_store_s3_secret_key is None
                or not runtime.object_store_s3_access_key.get_secret_value()
                or not runtime.object_store_s3_secret_key.get_secret_value()
            ):
                raise ValueError("S3-compatible ObjectStore requires access credentials")
        return cls(
            backend=runtime.object_store_backend,
            root=runtime.object_store_root,
            s3_endpoint=runtime.object_store_s3_endpoint,
            s3_bucket=runtime.object_store_s3_bucket,
            s3_region=runtime.object_store_s3_region,
            s3_access_key=runtime.object_store_s3_access_key,
            s3_secret_key=runtime.object_store_s3_secret_key,
        )


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://knora:knora@localhost:5432/knora"
    object_store_root: str = ".knora-objects"
    object_store_backend: str = "filesystem"
    object_store_s3_endpoint: str | None = None
    object_store_s3_bucket: str | None = None
    object_store_s3_region: str | None = None
    object_store_s3_access_key: SecretStr | None = None
    object_store_s3_secret_key: SecretStr | None = None
    object_inventory_manifest: str | None = None
    object_inventory_minimum_age_seconds: int = 86_400
    operational_alert_configuration_json: str | None = None
    operational_metrics_retry_window_seconds: int = 300
    embedding_dimension: int = 1536
    retrieval_configuration_id: str = "retrieval-m1-v1"
    vector_min_similarity: float | None = None
    api_credentials_json: str = "[]"
    retrieval_configuration_id: str = "retrieval-m1-v1"
    provider_mode: str = "deterministic-local"
    gemini_api_key: SecretStr | None = None
    gemini_timeout_seconds: float = 60.0
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

    @property
    def object_store_settings(self) -> ObjectStoreSettings:
        return ObjectStoreSettings.from_runtime(self)


settings = Settings()
