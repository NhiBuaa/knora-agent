from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    vectors: tuple[tuple[float, ...], ...]
    provider: str
    model: str


class EmbeddingProvider(Protocol):
    def embed(
        self,
        texts: list[str],
        configuration: EmbeddingConfiguration,
    ) -> EmbeddingBatch: ...
