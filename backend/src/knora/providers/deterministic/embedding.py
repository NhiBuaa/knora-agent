import hashlib
import math

from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


class DeterministicEmbeddingProvider:
    def embed(
        self,
        texts: list[str],
        configuration: EmbeddingConfiguration,
    ) -> EmbeddingBatch:
        vectors = tuple(self._vector(text, configuration.dimensions) for text in texts)
        return EmbeddingBatch(
            vectors=vectors,
            provider=configuration.provider,
            model=configuration.model,
        )

    @staticmethod
    def _vector(text: str, dimensions: int) -> tuple[float, ...]:
        raw = hashlib.shake_256(text.encode("utf-8")).digest(dimensions * 2)
        values = [
            (int.from_bytes(raw[offset : offset + 2], "big") / 32767.5) - 1.0
            for offset in range(0, len(raw), 2)
        ]
        magnitude = math.sqrt(sum(value * value for value in values)) or 1.0
        return tuple(value / magnitude for value in values)
