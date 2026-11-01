import math
import re
import unicodedata

import httpx

from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration

QUERY_INSTRUCTION = "Retrieve passages that answer this Vietnamese question."


class CloudflareEmbeddingProvider:
    def __init__(
        self,
        *,
        account_id: str,
        api_token: str,
        client: httpx.Client | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        if re.fullmatch(r"[0-9a-fA-F]{32}", account_id) is None:
            raise ValueError("invalid provider configuration: invalid cloudflare_account_id")
        self._account_id = account_id
        self._url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{account_id}/ai/run/@cf/qwen/qwen3-embedding-0.6b"
        )
        self._api_token = api_token
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None

    def embed_documents(
        self, texts: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        return self._embed(texts, configuration, role="documents")

    def embed_queries(
        self, texts: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        return self._embed(texts, configuration, role="queries")

    def embed(self, texts: list[str], configuration: EmbeddingConfiguration) -> EmbeddingBatch:
        raise KnoraError("EMBEDDING_INPUT_ROLE_REQUIRED")

    def _embed(
        self,
        texts: list[str],
        configuration: EmbeddingConfiguration,
        *,
        role: str,
    ) -> EmbeddingBatch:
        if configuration not in {
            EmbeddingConfiguration.cloudflare_qwen3_06b(),
            EmbeddingConfiguration.cloudflare_bge_base_en(),
        }:
            raise KnoraError("EMBEDDING_CONFIGURATION_MISMATCH")
        target_url = (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{self._account_id}/ai/run/{configuration.model}"
        )
        expected_dim = configuration.dimensions
        vectors: list[tuple[float, ...]] = []
        request_id: str | None = None
        try:
            for offset in range(0, len(texts), 32):
                batch = [
                    unicodedata.normalize("NFKC", text) for text in texts[offset : offset + 32]
                ]
                if (
                    "bge" in configuration.model.lower()
                    or configuration == EmbeddingConfiguration.cloudflare_bge_base_en()
                ):
                    body: dict[str, object] = {"text": batch}
                else:
                    body: dict[str, object] = {role: batch}
                    if (
                        role == "queries"
                        and configuration == EmbeddingConfiguration.cloudflare_qwen3_06b()
                    ):
                        body["instruction"] = QUERY_INSTRUCTION
                response = self._client.post(
                    target_url,
                    headers={"Authorization": f"Bearer {self._api_token}"},
                    json=body,
                )
                response.raise_for_status()
                result = response.json()["result"]
                data = result["data"]
                shape = result["shape"]
                if (
                    not isinstance(data, list)
                    or not isinstance(shape, list)
                    or len(shape) != 2
                    or any(type(dimension) is not int for dimension in shape)
                ):
                    raise KnoraError("PROVIDER_RESPONSE_INVALID")
                if len(data) != len(batch) or shape != [len(batch), expected_dim]:
                    if isinstance(shape, list) and len(shape) == 2 and shape[1] != expected_dim:
                        raise KnoraError("EMBEDDING_DIMENSION_MISMATCH")
                    raise KnoraError("PROVIDER_RESPONSE_INVALID")
                for row in data:
                    if not isinstance(row, list):
                        raise KnoraError("PROVIDER_RESPONSE_INVALID")
                    if len(row) != expected_dim:
                        raise KnoraError("EMBEDDING_DIMENSION_MISMATCH")
                    if any(
                        isinstance(value, bool)
                        or not isinstance(value, int | float)
                        or not math.isfinite(value)
                        for value in row
                    ):
                        raise KnoraError("PROVIDER_RESPONSE_INVALID")
                    vectors.append(tuple(float(value) for value in row))
                request_id = response.headers.get("cf-ray") or response.headers.get(
                    "x-request-id", request_id
                )
        except KnoraError:
            raise
        except httpx.HTTPError:
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None
        except (KeyError, TypeError, ValueError, OverflowError):
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
