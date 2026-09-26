"""Ollama embedding adapter with an immutable, resolved model profile."""

import hashlib
import json
import math
import unicodedata

import httpx

from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration

INPUT_POLICY = "qwen3-qa-asymmetric-v1"
API_CONTRACT = "ollama-api-embed-v1"
QUERY_PREFIX = "Instruct: Retrieve passages that answer this Vietnamese question.\nQuery: "


def resolve_ollama_embedding_configuration(
    client: httpx.Client, model: str
) -> EmbeddingConfiguration:
    """Resolve a model tag to an immutable profile before accepting work."""
    try:
        tags_response = client.get("/api/tags")
        tags_response.raise_for_status()
        models = tags_response.json()["models"]
        matches = [item for item in models if item.get("name") == model]
        if len(matches) != 1:
            raise ValueError("model tag missing or ambiguous")
        digest = matches[0]["digest"]
        if not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) != 71:
            raise ValueError("invalid model digest")
        show_response = client.post("/api/show", json={"model": model})
        show_response.raise_for_status()
        details = show_response.json()["details"]
        family = details["family"]
        quantization = details["quantization_level"]
        if not all(isinstance(value, str) and value for value in (family, quantization)):
            raise ValueError("missing model metadata")
    except httpx.HTTPError:
        raise KnoraError("PROVIDER_REQUEST_FAILED") from None
    except (KeyError, TypeError, ValueError):
        raise KnoraError("PROVIDER_RESPONSE_INVALID") from None
    identity = {
        "digest": digest,
        "family": family,
        "quantization": quantization,
        "api_contract": API_CONTRACT,
        "input_policy": INPUT_POLICY,
        "dimensions": 1024,
        "distance_metric": "cosine",
    }
    fingerprint = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]
    return EmbeddingConfiguration(
        id=f"embedding-ollama-qwen3-{fingerprint}",
        provider="ollama",
        model=model,
        dimensions=1024,
        distance_metric="cosine",
        deployment_identity=f"ollama:{family}:{quantization}:{digest}",
        api_contract_version=API_CONTRACT,
        input_normalization="utf8-nfkc-v1",
        input_policy_id=INPUT_POLICY,
        output_dimensionality=1024,
        vector_normalization="ollama-native-v1",
    )


class OllamaEmbeddingProvider:
    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout_seconds)
        self._owns_client = client is None

    def embed(self, texts: list[str], configuration: EmbeddingConfiguration) -> EmbeddingBatch:
        raise KnoraError("EMBEDDING_INPUT_ROLE_REQUIRED")

    def embed_documents(
        self, texts: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        return self._embed(texts, configuration, query=False)

    def embed_queries(
        self, texts: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        return self._embed(texts, configuration, query=True)

    def _embed(
        self, texts: list[str], configuration: EmbeddingConfiguration, *, query: bool
    ) -> EmbeddingBatch:
        if (
            configuration.provider != "ollama"
            or configuration.input_policy_id != INPUT_POLICY
            or configuration.api_contract_version != API_CONTRACT
            or configuration.dimensions != 1024
        ):
            raise KnoraError("EMBEDDING_CONFIGURATION_MISMATCH")
        if not texts:
            return EmbeddingBatch(vectors=(), provider="ollama", model=configuration.model)
        self._require_current_digest(configuration)
        inputs = [unicodedata.normalize("NFKC", text) for text in texts]
        if query:
            inputs = [QUERY_PREFIX + text for text in inputs]
        try:
            response = self._client.post(
                "/api/embed",
                json={"model": configuration.model, "input": inputs, "truncate": False},
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("model") != configuration.model:
                raise KnoraError("EMBEDDING_CONFIGURATION_MISMATCH")
            raw_vectors = payload["embeddings"]
            if not isinstance(raw_vectors, list) or len(raw_vectors) != len(texts):
                raise ValueError("embedding count mismatch")
            vectors = []
            for raw_vector in raw_vectors:
                if not isinstance(raw_vector, list):
                    raise ValueError("invalid embedding")
                if len(raw_vector) != 1024:
                    raise KnoraError("EMBEDDING_DIMENSION_MISMATCH")
                if any(
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    for value in raw_vector
                ):
                    raise ValueError("invalid embedding value")
                vector = tuple(float(value) for value in raw_vector)
                if not all(math.isfinite(value) for value in vector):
                    raise ValueError("non-finite embedding value")
                vectors.append(vector)
        except KnoraError:
            raise
        except httpx.HTTPError:
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None
        except (KeyError, TypeError, ValueError):
            raise KnoraError("PROVIDER_RESPONSE_INVALID") from None
        return EmbeddingBatch(vectors=tuple(vectors), provider="ollama", model=configuration.model)

    def _require_current_digest(self, configuration: EmbeddingConfiguration) -> None:
        try:
            response = self._client.get("/api/tags")
            response.raise_for_status()
            models = response.json()["models"]
            matches = [item for item in models if item.get("name") == configuration.model]
            digest = matches[0]["digest"] if len(matches) == 1 else None
            if not isinstance(digest, str) or not configuration.deployment_identity:
                raise KnoraError("EMBEDDING_CONFIGURATION_MISMATCH")
            if not configuration.deployment_identity.endswith(digest):
                raise KnoraError("EMBEDDING_CONFIGURATION_MISMATCH")
        except KnoraError:
            raise
        except httpx.HTTPError:
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None
        except (KeyError, TypeError, ValueError):
            raise KnoraError("PROVIDER_RESPONSE_INVALID") from None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
