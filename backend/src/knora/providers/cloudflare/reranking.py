"""Cloudflare Workers AI cross-encoder reranking provider.

Invokes @cf/baai/bge-reranker-base (or configured cross-encoder model)
on Cloudflare Workers AI with zero local weights and strict error boundaries.
Refs #153.
"""

from __future__ import annotations

import math
import re
import time
import unicodedata
from collections.abc import Sequence

import httpx

from knora.domain.errors import KnoraError
from knora.providers.reranking import (
    RerankingCandidate,
    RerankingResult,
    ScoredRerankingCandidate,
)

DEFAULT_CLOUDFLARE_RERANKER_MODEL = "@cf/baai/bge-reranker-base"


class CloudflareRerankingProvider:
    """Reranking provider targeting Cloudflare Workers AI cross-encoder endpoints."""

    def __init__(
        self,
        *,
        account_id: str,
        api_token: str,
        client: httpx.Client | None = None,
        model: str = DEFAULT_CLOUDFLARE_RERANKER_MODEL,
        timeout_seconds: float = 30.0,
        batch_size: int = 32,
    ) -> None:
        if re.fullmatch(r"[0-9a-fA-F]{32}", account_id) is None:
            raise ValueError("invalid provider configuration: invalid cloudflare_account_id")
        if not api_token or not api_token.strip():
            raise ValueError("invalid provider configuration: empty api_token")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        self._account_id = account_id
        self._api_token = api_token
        self._model = model
        self._url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None
        self._batch_size = batch_size

    @property
    def endpoint_url(self) -> str:
        return self._url

    @property
    def model(self) -> str:
        return self._model

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> CloudflareRerankingProvider:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankingCandidate],
    ) -> RerankingResult:
        """Score and rerank candidates against query via Cloudflare cross-encoder."""
        if not candidates:
            return RerankingResult(
                model=self._model,
                scored_candidates=(),
                request_id=None,
                duration_ms=0.0,
            )

        # Basic security and endpoint allowlist guard
        if not self._url.startswith("https://api.cloudflare.com/client/v4/accounts/"):
            raise KnoraError("CLOUDFLARE_RERANKING_ENDPOINT_FORBIDDEN")

        normalized_query = unicodedata.normalize("NFKC", query).strip()
        t0 = time.perf_counter()

        scored_pairs: list[tuple[float, RerankingCandidate]] = []
        last_request_id: str | None = None

        # Process candidates in batches
        for offset in range(0, len(candidates), self._batch_size):
            batch = candidates[offset : offset + self._batch_size]
            contexts = [{"text": unicodedata.normalize("NFKC", c.content)} for c in batch]
            payload = {
                "query": normalized_query,
                "contexts": contexts,
            }

            try:
                response = self._client.post(
                    self._url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_token}",
                        "Content-Type": "application/json",
                    },
                )
            except httpx.TimeoutException as exc:
                raise KnoraError("CLOUDFLARE_RERANKING_TIMEOUT") from exc
            except httpx.NetworkError as exc:
                raise KnoraError("CLOUDFLARE_RERANKING_UNAVAILABLE") from exc

            if response.status_code == 429:
                raise KnoraError("CLOUDFLARE_RERANKING_QUOTA_EXCEEDED")
            if response.status_code in (401, 403):
                raise KnoraError("CLOUDFLARE_RERANKING_AUTH_FAILED")
            if response.status_code >= 400:
                raise KnoraError("CLOUDFLARE_RERANKING_UNAVAILABLE")

            last_request_id = response.headers.get("cf-ray")

            try:
                data = response.json()
            except Exception as exc:
                raise KnoraError("CLOUDFLARE_RERANKING_MALFORMED_OUTPUT") from exc

            # Parse Cloudflare result structure
            raw_results = data.get("result") if isinstance(data, dict) else data
            if not isinstance(raw_results, list) or len(raw_results) != len(batch):
                raise KnoraError("CLOUDFLARE_RERANKING_MALFORMED_OUTPUT")

            # Collect scores matching candidate indices
            batch_scores: list[float | None] = [None] * len(batch)
            for item_idx, item in enumerate(raw_results):
                if not isinstance(item, dict):
                    raise KnoraError("CLOUDFLARE_RERANKING_MALFORMED_OUTPUT")

                score = item.get("score")
                if not isinstance(score, (int, float)) or not math.isfinite(score):
                    raise KnoraError("CLOUDFLARE_RERANKING_MALFORMED_OUTPUT")

                # Cloudflare item may have explicit 'index' mapping back to request context
                target_idx = item.get("index", item_idx)
                if not isinstance(target_idx, int) or target_idx < 0 or target_idx >= len(batch):
                    raise KnoraError("CLOUDFLARE_RERANKING_MALFORMED_OUTPUT")

                batch_scores[target_idx] = float(score)

            if any(s is None for s in batch_scores):
                raise KnoraError("CLOUDFLARE_RERANKING_MALFORMED_OUTPUT")

            for score, cand in zip(batch_scores, batch, strict=True):
                assert score is not None
                scored_pairs.append((score, cand))

        duration_ms = (time.perf_counter() - t0) * 1000.0

        # Sort descending by score, deterministic tie-breaking by chunk_id ascending
        scored_pairs.sort(key=lambda item: (-item[0], item[1].chunk_id))

        ranked = [
            ScoredRerankingCandidate(
                candidate=cand,
                rerank_score=score,
                rerank_rank=rank,
            )
            for rank, (score, cand) in enumerate(scored_pairs, start=1)
        ]

        return RerankingResult(
            model=self._model,
            scored_candidates=tuple(ranked),
            request_id=last_request_id,
            duration_ms=duration_ms,
        )
