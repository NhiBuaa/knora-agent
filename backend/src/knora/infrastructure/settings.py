from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://knora:knora@localhost:5432/knora"
    embedding_dimension: int = 1536

    model_config = SettingsConfigDict(env_file=".env", env_prefix="KNORA_")


settings = Settings()
