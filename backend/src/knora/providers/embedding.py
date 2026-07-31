from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmbeddingConfiguration:
    id: str
    provider: str
    model: str
    dimensions: int
    distance_metric: str

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
