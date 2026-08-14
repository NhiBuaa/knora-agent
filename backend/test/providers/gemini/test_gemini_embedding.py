import json
import unicodedata

import httpx
import pytest

from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingConfiguration
from knora.providers.gemini.embedding import GeminiEmbeddingProvider


def test_gemini_embedding_uses_r9_asymmetric_inputs_and_config() -> None:
    observed: list[dict[str, object]] = []

    def endpoint(request: httpx.Request) -> httpx.Response:
        observed.append(json.loads(request.content))
        return httpx.Response(200, json={"embedding": {"values": [0.25] * 1536}})

    provider = GeminiEmbeddingProvider(
        api_key="runtime-only",
        client=httpx.Client(transport=httpx.MockTransport(endpoint)),
    )
    configuration = EmbeddingConfiguration.gemini_m3()
    raw = "Ａ refund\u0301"

    document = provider.embed_documents([raw], configuration)
    query = provider.embed_queries([raw], configuration)

    normalized = unicodedata.normalize("NFKC", raw)
    assert [item["content"]["parts"][0]["text"] for item in observed] == [
        f"title: none | text: {normalized}",
        f"task: question answering | query: {normalized}",
    ]
    assert all(item["output_dimensionality"] == 1536 for item in observed)
    assert all("taskType" not in item and "outputDimensionality" not in item for item in observed)
    assert all(len(item["content"]["parts"]) == 1 for item in observed)
    assert document.provider == query.provider == "google-gemini-api"
    assert document.model == query.model == "gemini-embedding-2"


@pytest.mark.parametrize("size", [1535, 1537])
def test_gemini_embedding_rejects_wrong_response_dimension(size: int) -> None:
    provider = GeminiEmbeddingProvider(
        api_key="runtime-only",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"embedding": {"values": [0.0] * size}}
                )
            )
        ),
    )

    with pytest.raises(KnoraError, match="EMBEDDING_DIMENSION_MISMATCH"):
        provider.embed_queries(["refund"], EmbeddingConfiguration.gemini_m3())
