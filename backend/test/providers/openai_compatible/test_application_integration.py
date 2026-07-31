from decimal import Decimal
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.tables import QuestionTraceTable, WorkspaceTable
from knora.answering.module import AnswerQuestion
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import DocumentProcessor
from knora.main import create_app
from knora.providers.embedding import EmbeddingConfiguration
from knora.providers.openai_compatible.embedding import OpenAICompatibleEmbeddingProvider
from knora.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider


def test_openai_compatible_mode_reuses_ingestion_and_answer_http_seams() -> None:
    workspace_id = f"compatible-{uuid4()}"
    raw_key = f"key-{uuid4()}"
    embedding_requests: list[dict] = []
    generation_requests: list[dict] = []

    def embedding_endpoint(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        embedding_requests.append(payload)
        return httpx.Response(
            200,
            headers={"x-request-id": f"embedding-{len(embedding_requests)}"},
            json={
                "model": "text-embedding-3-small",
                "data": [
                    {"index": index, "embedding": [1.0] * 1536}
                    for index, _ in enumerate(payload["input"])
                ],
                "usage": {"prompt_tokens": 4, "total_tokens": 4},
            },
        )

    async def generation_endpoint(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        generation_requests.append(payload)
        return httpx.Response(
            200,
            headers={"x-request-id": "generation-1"},
            json={
                "model": "compatible-chat-model",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"decision":"ANSWER","answer":"Refunds are available for '
                                'thirty days. [[E1]]","cited_evidence_ids":["E1"],'
                                '"refusal_reason":null}'
                            )
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )

    configuration = EmbeddingConfiguration.openai_compatible(
        configuration_id="embedding-openai-m1-v1",
        model="text-embedding-3-small",
    )
    embedding_provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://provider.example/v1",
        api_key="provider-runtime-key",
        input_cost_per_million_tokens=Decimal("0.02"),
        pricing_version="test-pricing-v1",
        client=httpx.Client(transport=httpx.MockTransport(embedding_endpoint)),
    )
    generation_provider = OpenAICompatibleGenerationProvider(
        base_url="https://provider.example/v1",
        api_key="provider-runtime-key",
        model="compatible-chat-model",
        input_cost_per_million_tokens=Decimal("1"),
        output_cost_per_million_tokens=Decimal("2"),
        pricing_version="test-pricing-v1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(generation_endpoint)),
    )
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Compatible provider acceptance"))
    authenticator = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="compatible-acceptance",
                key_hash=hash_api_key(raw_key),
                workspace_id=workspace_id,
                enabled=True,
            ),
        )
    )
    client = TestClient(
        create_app(
            ingest_document=IngestDocument(
                processor=DocumentProcessor(),
                embedding_provider=embedding_provider,
                store=PostgresIngestionStore(SessionFactory),
            ),
            answer_question=AnswerQuestion(
                embedding_provider=embedding_provider,
                generation_provider=generation_provider,
                store=PostgresAnsweringStore(SessionFactory),
                embedding_configuration=configuration,
            ),
            api_key_authenticator=authenticator,
            embedding_configuration=configuration,
        )
    )

    ingested = client.post(
        f"/v1/workspaces/{workspace_id}/documents",
        headers={"X-API-Key": raw_key},
        data={"source_key": "support/refunds"},
        files={
            "file": (
                "refunds.md",
                b"# Refunds\n\nRefunds are available for thirty days.\n",
            )
        },
    )
    answered = client.post(
        "/v1/questions",
        headers={"X-API-Key": raw_key},
        json={"workspace_id": workspace_id, "question": "What is the refund policy?"},
    )

    assert ingested.status_code == 201
    assert ingested.json()["embedding_configuration_id"] == configuration.id
    assert answered.status_code == 200
    assert answered.json()["decision"] == "ANSWER"
    assert answered.json()["answer"].endswith("[[E1]]")
    assert answered.json()["citations"][0]["source_key"] == "support/refunds"
    assert len(embedding_requests) == 2
    assert len(generation_requests) == 1
    with SessionFactory() as session:
        trace = session.scalar(
            select(QuestionTraceTable).where(
                QuestionTraceTable.id == answered.json()["trace_id"]
            )
        )
        assert trace is not None
        assert trace.embedding_configuration_id == configuration.id
        assert trace.provider_metadata["embedding"]["provider_request_id"] == "embedding-2"
        assert trace.provider_metadata["generation"]["provider_request_id"] == "generation-1"
        assert trace.provider_metadata["generation"]["cost"] == {
            "amount_usd": "0.00002",
            "currency": "USD",
            "pricing_version": "test-pricing-v1",
        }
