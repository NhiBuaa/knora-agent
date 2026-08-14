from dataclasses import dataclass

from knora.answering.reembedding_v2 import (
    CorpusChunk,
    CorpusChunkSet,
    ReembedProductionCorpus,
)
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


class RecordingProvider:
    def __init__(self) -> None:
        self.inputs: list[list[str]] = []

    def embed_documents(self, texts, configuration):
        self.inputs.append(texts)
        return EmbeddingBatch(
            vectors=tuple(tuple([float(index)] * 1536) for index, _ in enumerate(texts)),
            provider=configuration.provider,
            model=configuration.model,
        )


@dataclass
class MemoryStore:
    population: tuple[CorpusChunkSet, ...]
    persisted: list[tuple[str, str]]
    activated: list[tuple[str, str]]
    enabled: bool = False

    def authority_bound_population(self, *, workspace_id: str):
        return self.population

    def persist_embedding_set(self, *, member, configuration, batch):
        embedding_set_id = f"gemini-{member.source_key}"
        self.persisted.append((member.chunk_set_id, embedding_set_id))
        return embedding_set_id

    def activate_embedding_set(self, *, member, embedding_set_id):
        self.activated.append((member.source_key, embedding_set_id))

    def enable_v2_retrieval(self, *, workspace_id: str, population_digest: str):
        self.enabled = True


def test_reembed_uses_existing_chunk_sets_and_enables_only_after_full_population() -> None:
    population = (
        CorpusChunkSet("a", "doc-a", "set-a", "digest-a", (CorpusChunk("c1", 0, "one"),)),
        CorpusChunkSet("b", "doc-b", "set-b", "digest-b", (CorpusChunk("c2", 0, "two"),)),
    )
    store = MemoryStore(population, [], [])
    provider = RecordingProvider()

    result = ReembedProductionCorpus(provider=provider, store=store).execute(
        workspace_id="m3", configuration=EmbeddingConfiguration.gemini_m3()
    )

    assert provider.inputs == [["one"], ["two"]]
    assert store.persisted == [("set-a", "gemini-a"), ("set-b", "gemini-b")]
    assert store.activated == [("a", "gemini-a"), ("b", "gemini-b")]
    assert store.enabled is True
    assert result.reembedded_source_keys == ("a", "b")
