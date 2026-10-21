"""Unit tests for Cloudflare cross-encoder reranking provider."""

from __future__ import annotations

import json
import unicodedata

import httpx
import pytest

from knora.domain.errors import KnoraError
from knora.providers.cloudflare.reranking import (
    DEFAULT_CLOUDFLARE_RERANKER_MODEL,
    CloudflareRerankingProvider,
)
from knora.providers.reranking import RerankingCandidate

ACCOUNT = "0123456789abcdef0123456789abcdef"


def _make_candidate(chunk_id: str, content: str) -> RerankingCandidate:
    return RerankingCandidate(
        chunk_id=chunk_id,
        document_version_id="ver-1",
        content=content,
        content_checksum=f"chk-{chunk_id}",
    )


def _provider(endpoint, batch_size: int = 32) -> CloudflareRerankingProvider:
    return CloudflareRerankingProvider(
        account_id=ACCOUNT,
        api_token="secret-canary",
        client=httpx.Client(transport=httpx.MockTransport(endpoint)),
        batch_size=batch_size,
    )


def test_cloudflare_reranking_request_payload_and_headers() -> None:
    observed: list[tuple[str, str, dict]] = []

    def endpoint(request: httpx.Request) -> httpx.Response:
        observed.append(
            (
                str(request.url),
                request.headers["Authorization"],
                json.loads(request.content),
            )
        )
        return httpx.Response(
            200,
            headers={"cf-ray": "ray-test-1"},
            json={
                "result": [
                    {"index": 0, "score": 0.95},
                    {"index": 1, "score": 0.20},
                ],
                "success": True,
            },
        )

    provider = _provider(endpoint)
    c1 = _make_candidate("c1", "quy định về thời giờ làm việc")
    c2 = _make_candidate("c2", "chính sách nghỉ dưỡng du lịch")

    res = provider.rerank("thời giờ làm việc", [c1, c2])

    assert len(observed) == 1
    url, auth, body = observed[0]
    expected_url = (
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run/"
        f"{DEFAULT_CLOUDFLARE_RERANKER_MODEL}"
    )
    assert url == expected_url
    assert auth == "Bearer secret-canary"
    assert body["query"] == "thời giờ làm việc"
    assert body["contexts"] == [
        {"text": unicodedata.normalize("NFKC", c1.content)},
        {"text": unicodedata.normalize("NFKC", c2.content)},
    ]

    assert len(res.scored_candidates) == 2
    assert res.scored_candidates[0].candidate.chunk_id == "c1"
    assert res.scored_candidates[0].rerank_score == 0.95
    assert res.scored_candidates[0].rerank_rank == 1
    assert res.scored_candidates[1].candidate.chunk_id == "c2"
    assert res.scored_candidates[1].rerank_score == 0.20
    assert res.scored_candidates[1].rerank_rank == 2
    assert res.request_id == "ray-test-1"


def test_cloudflare_reranking_handles_permuted_response_indices() -> None:
    """Cloudflare response items returned out of order are mapped correctly by index."""

    def endpoint(request: httpx.Request) -> httpx.Response:
        # Return index 1 first with higher score, then index 0
        return httpx.Response(
            200,
            json={
                "result": [
                    {"index": 1, "score": 0.99},
                    {"index": 0, "score": 0.15},
                ],
                "success": True,
            },
        )

    provider = _provider(endpoint)
    c0 = _make_candidate("c0", "low relevance content")
    c1 = _make_candidate("c1", "high relevance content")

    res = provider.rerank("query", [c0, c1])
    assert len(res.scored_candidates) == 2
    # c1 had score 0.99, so it must be rank 1
    assert res.scored_candidates[0].candidate.chunk_id == "c1"
    assert res.scored_candidates[0].rerank_score == 0.99
    assert res.scored_candidates[0].rerank_rank == 1
    # c0 had score 0.15, so it must be rank 2
    assert res.scored_candidates[1].candidate.chunk_id == "c0"
    assert res.scored_candidates[1].rerank_score == 0.15
    assert res.scored_candidates[1].rerank_rank == 2


@pytest.mark.parametrize("count", [5, 10])
def test_cloudflare_reranking_batches_candidates(count: int) -> None:
    batches_seen: list[int] = []

    def endpoint(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content)
        contexts = data["contexts"]
        batches_seen.append(len(contexts))
        results = [{"index": i, "score": float(10 - i)} for i in range(len(contexts))]
        return httpx.Response(200, json={"result": results, "success": True})

    # batch_size = 4
    provider = _provider(endpoint, batch_size=4)
    candidates = [_make_candidate(f"c{i}", f"content {i}") for i in range(count)]

    res = provider.rerank("query", candidates)
    assert len(res.scored_candidates) == count
    if count == 5:
        assert batches_seen == [4, 1]
    elif count == 10:
        assert batches_seen == [4, 4, 2]


def test_cloudflare_reranking_quota_exhausted_raises_error() -> None:
    def endpoint(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limit / quota exceeded"})

    provider = _provider(endpoint)
    candidates = [_make_candidate("c1", "content")]
    with pytest.raises(KnoraError) as exc_info:
        provider.rerank("query", candidates)
    assert exc_info.value.code == "CLOUDFLARE_RERANKING_QUOTA_EXCEEDED"


def test_cloudflare_reranking_auth_failure_raises_error() -> None:
    def endpoint(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    provider = _provider(endpoint)
    candidates = [_make_candidate("c1", "content")]
    with pytest.raises(KnoraError) as exc_info:
        provider.rerank("query", candidates)
    assert exc_info.value.code == "CLOUDFLARE_RERANKING_AUTH_FAILED"


def test_cloudflare_reranking_timeout_raises_error() -> None:
    def endpoint(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out")

    provider = _provider(endpoint)
    candidates = [_make_candidate("c1", "content")]
    with pytest.raises(KnoraError) as exc_info:
        provider.rerank("query", candidates)
    assert exc_info.value.code == "CLOUDFLARE_RERANKING_TIMEOUT"


def test_cloudflare_reranking_malformed_scores_rejected() -> None:
    def endpoint(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"result": [{"index": 0, "score": "not-a-number"}], "success": True},
        )

    provider = _provider(endpoint)
    candidates = [_make_candidate("c1", "content")]
    with pytest.raises(KnoraError) as exc_info:
        provider.rerank("query", candidates)
    assert exc_info.value.code == "CLOUDFLARE_RERANKING_MALFORMED_OUTPUT"


def test_cloudflare_reranking_rejects_invalid_account_id() -> None:
    with pytest.raises(ValueError, match="invalid cloudflare_account_id"):
        CloudflareRerankingProvider(
            account_id="not-a-hex-account-id",
            api_token="valid-token",
        )
