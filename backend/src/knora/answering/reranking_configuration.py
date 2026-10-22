"""Deployment-wide cross-encoder reranking configuration and resolver.

System administrators select an immutable, versioned configuration. Client requests
and HTTP callers are forbidden from choosing model, overriding thresholds or altering scope.
Refs #153.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RerankingConfiguration:
    """Deployment-wide cross-encoder reranking and MMR evidence selection configuration."""

    id: str
    provider: str
    model: str
    revision: str | None = None
    max_candidates: int = 100
    timeout_seconds: float = 30.0
    fallback_policy: str = "fallback_dbsf_sdm"
    normalization: str = "min_max"
    weight_reranker: float = 0.50
    weight_retrieval: float = 0.50
    mmr_enabled: bool = True
    mmr_lambda: float = 0.70
    max_evidence_chunks: int = 5
    max_evidence_tokens: int = 3000

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id must not be empty")
        if not self.provider:
            raise ValueError("provider must not be empty")
        if not self.model:
            raise ValueError("model must not be empty")
        if self.max_candidates <= 0:
            raise ValueError("max_candidates must be positive")
        if self.timeout_seconds <= 0.0:
            raise ValueError("timeout_seconds must be positive")
        if self.fallback_policy not in {"fallback_dbsf_sdm", "fail_closed"}:
            raise ValueError(f"unsupported fallback_policy: {self.fallback_policy}")
        if self.normalization not in {"min_max", "sigmoid", "none"}:
            raise ValueError(f"unsupported normalization: {self.normalization}")
        if not (math.isfinite(self.weight_reranker) and math.isfinite(self.weight_retrieval)):
            raise ValueError("weights must be finite numbers")
        if self.weight_reranker < 0.0 or self.weight_retrieval < 0.0:
            raise ValueError("weights must be non-negative")
        if self.weight_reranker + self.weight_retrieval <= 0.0:
            raise ValueError("sum of weights must be positive")
        if not (0.0 <= self.mmr_lambda <= 1.0):
            raise ValueError("mmr_lambda must be between 0.0 and 1.0")
        if self.max_evidence_chunks <= 0:
            raise ValueError("max_evidence_chunks must be positive")
        if self.max_evidence_tokens <= 0:
            raise ValueError("max_evidence_tokens must be positive")

    def digest(self) -> str:
        data = asdict(self)
        payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def cloudflare_bge_reranker_v1(cls) -> RerankingConfiguration:
        return cls(
            id="reranking-cloudflare-bge-base-v1",
            provider="cloudflare-workers-ai",
            model="@cf/baai/bge-reranker-base",
            revision="cf-v1",
            max_candidates=100,
            timeout_seconds=30.0,
            fallback_policy="fallback_dbsf_sdm",
            normalization="min_max",
            weight_reranker=0.50,
            weight_retrieval=0.50,
            mmr_enabled=True,
            mmr_lambda=0.70,
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
        )

    @classmethod
    def deterministic_v1(cls) -> RerankingConfiguration:
        return cls(
            id="reranking-deterministic-v1",
            provider="deterministic-local",
            model="deterministic-reranker-v1",
            revision="v1",
            max_candidates=100,
            timeout_seconds=10.0,
            fallback_policy="fallback_dbsf_sdm",
            normalization="min_max",
            weight_reranker=0.50,
            weight_retrieval=0.50,
            mmr_enabled=True,
            mmr_lambda=0.70,
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
        )


class RerankingConfigurationResolver(Protocol):
    """Protocol for resolving deployment reranking configuration."""

    def resolve(self) -> RerankingConfiguration | None: ...


@dataclass(frozen=True, slots=True)
class DeploymentRerankingConfigurationResolver:
    """Deployment-wide immutable resolver managed by System Administrator."""

    configuration: RerankingConfiguration | None

    def resolve(self) -> RerankingConfiguration | None:
        return self.configuration


def resolve_reranking_configuration(
    configuration_id: str | None,
) -> RerankingConfiguration | None:
    """Resolve the immutable deployment reranking configuration by ID."""
    if not configuration_id:
        return None
    cf_config = RerankingConfiguration.cloudflare_bge_reranker_v1()
    configurations = {
        "reranking-cloudflare-bge-base-v1": cf_config,
        "cross-encoder-bge-reranker-base-v1": cf_config,
        "reranking-deterministic-v1": RerankingConfiguration.deterministic_v1(),
    }
    try:
        return configurations[configuration_id]
    except KeyError as error:
        raise ValueError(f"unsupported reranking configuration: {configuration_id}") from error
