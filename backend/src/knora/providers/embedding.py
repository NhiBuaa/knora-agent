from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmbeddingConfiguration:
    id: str
    provider: str
    model: str
    dimensions: int
    distance_metric: str
    deployment_identity: str | None = None
    api_contract_version: str | None = None
    input_normalization: str | None = None
    input_policy_id: str | None = None
    output_dimensionality: int | None = None
    vector_normalization: str | None = None

    @classmethod
    def milestone_one_local(cls) -> "EmbeddingConfiguration":
        return cls(
            id="embedding-local-m1-v2",
            provider="deterministic-local",
            model="text-embedding-3-small",
            dimensions=1536,
            distance_metric="cosine",
        )

    @classmethod
    def openai_compatible(
        cls,
        *,
        configuration_id: str,
        model: str,
    ) -> "EmbeddingConfiguration":
        return cls(
            id=configuration_id,
            provider="openai-compatible",
            model=model,
            dimensions=1536,
            distance_metric="cosine",
        )

    @classmethod
    def gemini_m3(cls) -> "EmbeddingConfiguration":
        return cls(
            id="embedding-gemini-m1-v1",
            provider="google-gemini-api",
            model="gemini-embedding-2",
            dimensions=1536,
            distance_metric="cosine",
            deployment_identity="gemini-api-generativelanguage-googleapis-com-v1beta",
            api_contract_version="gemini-api-v1beta-models.embedContent-v1",
            input_normalization="utf8-nfkc-v1",
            input_policy_id="gemini-m3-qa-asymmetric-v1",
            output_dimensionality=1536,
            vector_normalization=(
                "gemini-embedding-2-provider-auto-normalized-truncated-output-v1"
            ),
        )


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    vectors: tuple[tuple[float, ...], ...]
    provider: str
    model: str
    provider_request_id: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    cost: dict[str, str] = field(default_factory=dict)


class EmbeddingProvider(Protocol):
    def embed(
        self,
        texts: list[str],
        configuration: EmbeddingConfiguration,
    ) -> EmbeddingBatch: ...

    def embed_documents(
        self,
        texts: list[str],
        configuration: EmbeddingConfiguration,
    ) -> EmbeddingBatch: ...

    def embed_queries(
        self,
        texts: list[str],
        configuration: EmbeddingConfiguration,
    ) -> EmbeddingBatch: ...
