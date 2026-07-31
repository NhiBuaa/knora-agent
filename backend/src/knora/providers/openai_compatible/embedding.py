from decimal import Decimal

import httpx

from knora.domain.errors import KnoraError
from knora.providers.embedding import (
    EmbeddingBatch,
    EmbeddingConfiguration,
)


class OpenAICompatibleEmbeddingProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        input_cost_per_million_tokens: Decimal,
        pricing_version: str,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/embeddings"
        self._api_key = api_key
        self._input_cost_per_million_tokens = input_cost_per_million_tokens
        self._pricing_version = pricing_version
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None

    def embed(
        self,
        texts: list[str],
        configuration: EmbeddingConfiguration,
    ) -> EmbeddingBatch:
        try:
            response = self._client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "input": texts,
                    "model": configuration.model,
                    "dimensions": configuration.dimensions,
                },
            )
            response.raise_for_status()
            payload = response.json()
            items = sorted(payload["data"], key=lambda item: item["index"])
            if [item["index"] for item in items] != list(range(len(items))):
                raise ValueError
            vectors = tuple(tuple(float(value) for value in item["embedding"]) for item in items)
            usage = {
                key: int(value)
                for key, value in payload.get("usage", {}).items()
                if isinstance(value, int)
            }
            prompt_tokens = usage.get("prompt_tokens", 0)
            amount = (
                Decimal(prompt_tokens) * self._input_cost_per_million_tokens / Decimal(1_000_000)
            )
            return EmbeddingBatch(
                vectors=vectors,
                provider="openai-compatible",
                model=str(payload.get("model", configuration.model)),
                provider_request_id=response.headers.get("x-request-id"),
                usage=usage,
                cost={
                    "amount_usd": format(amount, "f"),
                    "currency": "USD",
                    "pricing_version": self._pricing_version,
                },
            )
        except httpx.HTTPError:
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None
        except (KeyError, TypeError, ValueError):
            raise KnoraError("PROVIDER_RESPONSE_INVALID") from None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
