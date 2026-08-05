"""Keep repository tests isolated from a developer's runtime provider .env."""

import os

os.environ["KNORA_PROVIDER_MODE"] = "deterministic-local"
os.environ["KNORA_OPENAI_EMBEDDING_MODEL"] = "text-embedding-3-small"
os.environ["KNORA_EMBEDDING_DIMENSION"] = "1536"
