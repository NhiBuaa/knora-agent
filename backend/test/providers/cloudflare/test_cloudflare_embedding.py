import json
import math
import unicodedata

import httpx
import pytest

from knora.domain.errors import KnoraError
from knora.providers.cloudflare.embedding import CloudflareEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration

PROFILE = EmbeddingConfiguration.cloudflare_qwen3_06b()
ACCOUNT = "0123456789abcdef0123456789abcdef"


def _provider(endpoint):
    return CloudflareEmbeddingProvider(
        account_id=ACCOUNT,
        api_token="secret-canary",
        client=httpx.Client(transport=httpx.MockTransport(endpoint)),
    )


def test_cloudflare_embedding_uses_role_specific_normalized_inputs() -> None:
    observed = []

    def endpoint(request: httpx.Request) -> httpx.Response:
        observed.append(
            (str(request.url), request.headers["Authorization"], json.loads(request.content))
        )
        return httpx.Response(
            200,
            headers={"cf-ray": "request-1"},
            json={"result": {"data": [[0.25] * 1024], "shape": [1, 1024]}},
        )

    provider = _provider(endpoint)
    raw = "Ａ refund\u0301"
    document = provider.embed_documents([raw], PROFILE)
    query = provider.embed_queries([raw], PROFILE)

    normalized = unicodedata.normalize("NFKC", raw)
    assert observed[0][0] == (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{ACCOUNT}/ai/run/@cf/qwen/qwen3-embedding-0.6b"
    )
    assert [item[1] for item in observed] == ["Bearer secret-canary"] * 2
    assert observed[0][2] == {"documents": [normalized]}
    assert observed[1][2] == {
        "queries": [normalized],
        "instruction": "Retrieve passages that answer this Vietnamese question.",
    }
    assert document.vectors == query.vectors == ((0.25,) * 1024,)
    assert document.provider == query.provider == "cloudflare-workers-ai"
    assert document.model == query.model == "@cf/qwen/qwen3-embedding-0.6b"
    assert document.provider_request_id == "request-1"


@pytest.mark.parametrize("count", [32, 33, 100])
def test_cloudflare_embedding_batches_at_32_and_preserves_order(count: int) -> None:
    requests: list[list[str]] = []

    def endpoint(request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["documents"]
        requests.append(texts)
        data = [[float(text)] * 1024 for text in texts]
        return httpx.Response(200, json={"result": {"data": data, "shape": [len(texts), 1024]}})

    result = _provider(endpoint).embed_documents([str(i) for i in range(count)], PROFILE)
    assert [len(batch) for batch in requests] == [
        min(32, count - offset) for offset in range(0, count, 32)
    ]
    assert [vector[0] for vector in result.vectors] == list(map(float, range(count)))


@pytest.mark.parametrize(
    ("result", "error"),
    [
        ({"data": [], "shape": [1, 1024]}, "PROVIDER_RESPONSE_INVALID"),
        ({"data": [[0.0] * 1024], "shape": [2, 1024]}, "PROVIDER_RESPONSE_INVALID"),
        ({"data": [[0.0] * 1024], "shape": [True, 1024]}, "PROVIDER_RESPONSE_INVALID"),
        ({"data": [[0.0] * 1023], "shape": [1, 1023]}, "EMBEDDING_DIMENSION_MISMATCH"),
        ({"data": [[math.inf] * 1024], "shape": [1, 1024]}, "PROVIDER_RESPONSE_INVALID"),
        ({"data": [[True] * 1024], "shape": [1, 1024]}, "PROVIDER_RESPONSE_INVALID"),
    ],
)
def test_cloudflare_embedding_rejects_invalid_result(result: dict, error: str) -> None:
    provider = _provider(lambda request: httpx.Response(200, json={"result": result}))
    with pytest.raises(KnoraError, match=error):
        provider.embed_queries(["hello"], PROFILE)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_cloudflare_embedding_safely_normalizes_http_errors(status: int) -> None:
    calls = 0

    def endpoint(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, text="secret-canary-body")

    with pytest.raises(KnoraError, match="PROVIDER_REQUEST_FAILED") as captured:
        _provider(endpoint).embed_documents(["hello"], PROFILE)
    assert "secret-canary" not in str(captured.value)
    assert calls == 1


def test_cloudflare_embedding_rejects_malformed_json() -> None:
    provider = _provider(lambda request: httpx.Response(200, text="secret-canary-not-json"))
    with pytest.raises(KnoraError, match="PROVIDER_RESPONSE_INVALID") as captured:
        provider.embed_documents(["hello"], PROFILE)
    assert "secret-canary" not in str(captured.value)


def test_cloudflare_embedding_does_not_return_partial_batch_after_timeout() -> None:
    calls = 0

    def endpoint(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise httpx.ReadTimeout("secret-canary-timeout", request=request)
        return httpx.Response(
            200, json={"result": {"data": [[0.0] * 1024] * 32, "shape": [32, 1024]}}
        )

    with pytest.raises(KnoraError, match="PROVIDER_REQUEST_FAILED"):
        _provider(endpoint).embed_documents([str(i) for i in range(33)], PROFILE)
    assert calls == 2


def test_cloudflare_embedding_requires_exact_configuration_and_role() -> None:
    provider = _provider(lambda request: pytest.fail("must not call transport"))
    with pytest.raises(KnoraError, match="EMBEDDING_CONFIGURATION_MISMATCH"):
        provider.embed_documents(["hello"], EmbeddingConfiguration.gemini_m3())
    with pytest.raises(KnoraError, match="EMBEDDING_INPUT_ROLE_REQUIRED"):
        provider.embed(["hello"], PROFILE)


def test_cloudflare_embedding_bge_uses_text_field() -> None:
    observed_bodies = []
    bge_profile = EmbeddingConfiguration.cloudflare_bge_base_en()

    def endpoint(request: httpx.Request) -> httpx.Response:
        observed_bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"result": {"data": [[0.1] * 768], "shape": [1, 768]}},
        )

    provider = _provider(endpoint)
    provider.embed_documents(["document text"], bge_profile)
    provider.embed_queries(["query text"], bge_profile)

    assert observed_bodies[0] == {"text": ["document text"]}
    assert observed_bodies[1] == {"text": ["query text"]}
