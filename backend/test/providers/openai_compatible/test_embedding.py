from decimal import Decimal

import httpx
import pytest

from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingConfiguration
from knora.providers.openai_compatible.embedding import OpenAICompatibleEmbeddingProvider


def test_openai_compatible_embedding_returns_ordered_vectors_and_safe_metadata() -> None:
    observed: dict[str, object] = {}

    def endpoint(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["authorization"] = request.headers["Authorization"]
        observed["payload"] = __import__("json").loads(request.content)
        return httpx.Response(
            200,
            headers={"x-request-id": "embed-request-1"},
            json={
                "object": "list",
                "model": "text-embedding-3-small",
                "data": [
                    {"object": "embedding", "index": 1, "embedding": [0.0] * 1536},
                    {"object": "embedding", "index": 0, "embedding": [1.0] * 1536},
                ],
                "usage": {"prompt_tokens": 4, "total_tokens": 4},
            },
        )

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://provider.example/v1/",
        api_key="runtime-secret",
        client=httpx.Client(transport=httpx.MockTransport(endpoint)),
        input_cost_per_million_tokens=Decimal("0.02"),
        pricing_version="test-pricing-v1",
    )
    configuration = EmbeddingConfiguration.openai_compatible(
        configuration_id="embedding-openai-m1-v1",
        model="text-embedding-3-small",
    )

    result = provider.embed(["first", "second"], configuration)

    assert observed == {
        "url": "https://provider.example/v1/embeddings",
        "authorization": "Bearer runtime-secret",
        "payload": {
            "input": ["first", "second"],
            "model": "text-embedding-3-small",
            "dimensions": 1536,
        },
    }
    assert result.vectors[0] == tuple([1.0] * 1536)
    assert result.vectors[1] == tuple([0.0] * 1536)
    assert result.provider == "openai-compatible"
    assert result.model == "text-embedding-3-small"
    assert result.provider_request_id == "embed-request-1"
    assert result.usage == {"prompt_tokens": 4, "total_tokens": 4}
    assert result.cost == {
        "amount_usd": "0.00000008",
        "currency": "USD",
        "pricing_version": "test-pricing-v1",
    }


@pytest.mark.parametrize("failure", ["http", "timeout"])
def test_openai_compatible_embedding_sanitizes_transport_failures(failure: str) -> None:
    calls = 0

    def endpoint(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if failure == "timeout":
            raise httpx.ReadTimeout("secret-canary-timeout", request=request)
        return httpx.Response(500, text="secret-canary-body")

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://provider.example/v1",
        api_key="secret-canary-key",
        client=httpx.Client(transport=httpx.MockTransport(endpoint)),
        input_cost_per_million_tokens=Decimal("0.02"),
        pricing_version="test-pricing-v1",
    )

    with pytest.raises(KnoraError) as captured:
        provider.embed(
            ["refund policy"],
            EmbeddingConfiguration.openai_compatible(
                configuration_id="embedding-openai-m1-v1",
                model="text-embedding-3-small",
            ),
        )

    assert captured.value.code == "PROVIDER_REQUEST_FAILED"
    assert str(captured.value) == "PROVIDER_REQUEST_FAILED"
    assert "secret-canary" not in str(captured.value)
    assert calls == 1
