import unicodedata

import httpx

from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


class GeminiEmbeddingProvider:
    """Gemini API adapter for the immutable M3 asymmetric QA embedding space."""

    def __init__(
        self,
        *,
        api_key: str,
        client: httpx.Client | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None
        self._url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            "models/gemini-embedding-2:embedContent"
        )

    def embed_documents(
        self, texts: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        return self._embed(texts, configuration, role="document")

    def embed_queries(
        self, texts: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        return self._embed(texts, configuration, role="query")

    def embed(
        self, texts: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        raise KnoraError("EMBEDDING_INPUT_ROLE_REQUIRED")

    def _embed(
        self,
        texts: list[str],
        configuration: EmbeddingConfiguration,
        *,
        role: str,
    ) -> EmbeddingBatch:
        if configuration != EmbeddingConfiguration.gemini_m3():
            raise KnoraError("EMBEDDING_CONFIGURATION_MISMATCH")
        vectors: list[tuple[float, ...]] = []
        request_id: str | None = None
        try:
            for raw_text in texts:
                content = unicodedata.normalize("NFKC", raw_text)
                provider_text = (
                    f"title: none | text: {content}"
                    if role == "document"
                    else f"task: question answering | query: {content}"
                )
                response = self._client.post(
                    self._url,
                    headers={"x-goog-api-key": self._api_key},
                    json={
                        "content": {"parts": [{"text": provider_text}]},
                        # REST serialization of non-deprecated EmbedContentConfig.
                        "output_dimensionality": configuration.output_dimensionality,
                    },
                )
                response.raise_for_status()
                values = response.json()["embedding"]["values"]
                vector = tuple(float(value) for value in values)
                if len(vector) != configuration.dimensions:
                    raise KnoraError("EMBEDDING_DIMENSION_MISMATCH")
                vectors.append(vector)
                request_id = response.headers.get("x-request-id", request_id)
        except KnoraError:
            raise
        except httpx.HTTPError:
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None
        except (KeyError, TypeError, ValueError):
            raise KnoraError("PROVIDER_RESPONSE_INVALID") from None
        return EmbeddingBatch(
            vectors=tuple(vectors),
            provider=configuration.provider,
            model=configuration.model,
            provider_request_id=request_id,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
