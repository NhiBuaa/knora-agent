import json

import httpx
import pytest

from knora.domain.errors import KnoraError
from knora.providers.ollama.embedding import (
    OllamaEmbeddingProvider,
    resolve_ollama_embedding_configuration,
)

MODEL = "qwen3-embedding:0.6b"
DIGEST = "sha256:" + "a" * 64


def _client(*, dimensions: int = 1024, digest: str = DIGEST, bad: str | None = None):
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": MODEL, "digest": digest}]})
        if request.url.path == "/api/show":
            return httpx.Response(
                200, json={"details": {"quantization_level": "Q8_0", "family": "qwen3"}}
            )
        payload = json.loads(request.content)
        if bad == "timeout":
            raise httpx.ReadTimeout("unavailable")
        if bad == "malformed":
            return httpx.Response(200, json={"model": MODEL, "embeddings": []})
        if bad == "wrong_model":
            return httpx.Response(200, json={"model": "other", "embeddings": [[0.0] * dimensions]})
        return httpx.Response(
            200,
            json={"model": MODEL, "embeddings": [[0.5] * dimensions for _ in payload["input"]]},
        )

    return httpx.Client(
        transport=httpx.MockTransport(handle), base_url="http://ollama.test"
    ), requests


def test_profile_pins_digest_and_role_specific_batch_inputs() -> None:
    client, requests = _client()
    profile = resolve_ollama_embedding_configuration(client, MODEL)
    provider = OllamaEmbeddingProvider(client=client)

    documents = provider.embed_documents(["ba\u0301o ca\u0301o", "chương 2"], profile)
    query = provider.embed_queries(["cần bao nhiêu chương?"], profile)

    assert profile.provider == "ollama"
    assert profile.dimensions == 1024
    assert profile.deployment_identity is not None
    assert profile.deployment_identity.endswith(DIGEST)
    assert profile.input_policy_id == "qwen3-qa-asymmetric-v1"
    assert len(documents.vectors) == 2
    assert len(documents.vectors[0]) == 1024
    assert len(query.vectors[0]) == 1024
    embed_requests = [request for request in requests if request.url.path == "/api/embed"]
    assert json.loads(embed_requests[0].content) == {
        "model": MODEL,
        "input": ["báo cáo", "chương 2"],
        "truncate": False,
    }
    assert json.loads(embed_requests[1].content)["input"] == [
        "Instruct: Retrieve passages that answer this Vietnamese question.\n"
        "Query: cần bao nhiêu chương?"
    ]


def test_changed_digest_changes_immutable_profile_identity() -> None:
    first, _ = _client()
    second, _ = _client(digest="sha256:" + "b" * 64)
    assert (
        resolve_ollama_embedding_configuration(first, MODEL).id
        != resolve_ollama_embedding_configuration(second, MODEL).id
    )


def test_model_drift_after_startup_fails_before_embedding() -> None:
    digest = DIGEST

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal digest
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": MODEL, "digest": digest}]})
        if request.url.path == "/api/show":
            return httpx.Response(
                200, json={"details": {"quantization_level": "Q8_0", "family": "qwen3"}}
            )
        raise AssertionError("model drift should prevent embedding")

    client = httpx.Client(transport=httpx.MockTransport(handle), base_url="http://ollama.test")
    profile = resolve_ollama_embedding_configuration(client, MODEL)
    digest = "sha256:" + "b" * 64

    with pytest.raises(KnoraError, match="EMBEDDING_CONFIGURATION_MISMATCH"):
        OllamaEmbeddingProvider(client=client).embed_documents(["document"], profile)


@pytest.mark.parametrize(
    ("bad", "dimensions", "error"),
    [
        (None, 1023, "EMBEDDING_DIMENSION_MISMATCH"),
        ("malformed", 1024, "PROVIDER_RESPONSE_INVALID"),
        ("wrong_model", 1024, "EMBEDDING_CONFIGURATION_MISMATCH"),
        ("timeout", 1024, "PROVIDER_REQUEST_FAILED"),
    ],
)
def test_embedding_rejects_unsafe_provider_result(
    bad: str | None, dimensions: int, error: str
) -> None:
    client, _ = _client(dimensions=dimensions, bad=bad)
    profile = resolve_ollama_embedding_configuration(client, MODEL)
    with pytest.raises(KnoraError, match=error):
        OllamaEmbeddingProvider(client=client).embed_documents(["báo cáo"], profile)
