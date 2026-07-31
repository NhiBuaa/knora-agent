from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration


def test_deterministic_embedding_uses_production_dimension_and_is_repeatable() -> None:
    provider = DeterministicEmbeddingProvider()
    configuration = EmbeddingConfiguration.milestone_one_local()

    first = provider.embed(["refund policy", "shipping policy"], configuration)
    second = provider.embed(["refund policy"], configuration)

    assert len(first.vectors) == 2
    assert len(first.vectors[0]) == 1536
    assert first.vectors[0] == second.vectors[0]
    assert first.vectors[0] != first.vectors[1]
    assert first.provider == "deterministic-local"
    assert configuration.model == "text-embedding-3-small"
    assert configuration.dimensions == 1536
    assert configuration.distance_metric == "cosine"
