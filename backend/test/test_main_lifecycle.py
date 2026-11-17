import asyncio
from datetime import UTC, datetime

import pytest

from knora.main import create_app


class ObjectStore:
    def put_stream(self, *, workspace_id, stream, media_type):
        del workspace_id, stream, media_type
        raise AssertionError("not used")

    def open_read(self, *, workspace_id, object_key):
        del workspace_id, object_key
        raise AssertionError("not used")

    def head(self, *, workspace_id, object_key):
        del workspace_id, object_key
        raise AssertionError("not used")

    def delete(self, *, workspace_id, object_key):
        del workspace_id, object_key


class Inventory:
    def objects(self, *, workspace_id):
        del workspace_id
        return []


class Clock:
    def now(self):
        return datetime.now(UTC)


def test_create_app_composes_lifecycle_worker_and_optional_reconciler() -> None:
    application = create_app(
        object_store=ObjectStore(),
        lifecycle_inventory=Inventory(),
        lifecycle_clock=Clock(),
    )

    assert application.state.object_lifecycle_worker is not None
    assert application.state.object_lifecycle_reconciler is not None
    assert application.state.operational_observability is not None
    assert application.state.conversation_store is not None
    assert application.state.conversation_service is not None
    assert callable(application.state.conversation_runner.run_once)


def test_create_app_injects_reranking_provider_and_resolver() -> None:
    class DummyRerankingProvider:
        def rerank(self, query, candidates):
            raise AssertionError("not used")

    from knora.answering.reranking_configuration import (
        DeploymentRerankingConfigurationResolver,
        RerankingConfiguration,
    )

    mock_provider = DummyRerankingProvider()
    mock_resolver = DeploymentRerankingConfigurationResolver(
        RerankingConfiguration.cloudflare_bge_reranker_v1()
    )
    application = create_app(
        object_store=ObjectStore(),
        lifecycle_inventory=Inventory(),
        lifecycle_clock=Clock(),
        reranking_provider=mock_provider,
        reranking_configuration_resolver=mock_resolver,
    )
    aq = application.state.answer_question
    assert aq._reranking_provider is mock_provider
    assert aq._reranking_configuration_resolver is mock_resolver


@pytest.mark.asyncio
async def test_create_app_lifespan_closes_reranking_provider(monkeypatch) -> None:
    from knora.adapters.qdrant.native_search_index import NativeQdrantSearchIndex

    monkeypatch.setattr(NativeQdrantSearchIndex, "ensure_collection", lambda self: None)
    closed = []

    class ClosableReranker:
        def close(self):
            closed.append(True)

    provider = ClosableReranker()
    application = create_app(
        object_store=ObjectStore(),
        lifecycle_inventory=Inventory(),
        lifecycle_clock=Clock(),
        reranking_provider=provider,
    )
    async with application.router.lifespan_context(application):
        pass
    assert closed == [True]


@pytest.mark.asyncio
async def test_create_app_lifespan_starts_and_stops_embedded_workers(monkeypatch) -> None:
    from knora.adapters.qdrant.native_search_index import NativeQdrantSearchIndex
    from knora.ingestion.job_processing import NoEligibleJob

    monkeypatch.setattr(NativeQdrantSearchIndex, "ensure_collection", lambda self: None)

    ingest_runs = []
    conv_runs = []

    class MockIngestionWorker:
        def run_once(self, worker_id: str):
            ingest_runs.append(worker_id)
            return NoEligibleJob()

    class MockConversationRunner:
        async def run_once(self, worker_id: str):
            conv_runs.append(worker_id)
            return False

    application = create_app(
        embedded_workers=True,
        object_store=ObjectStore(),
        lifecycle_inventory=Inventory(),
        lifecycle_clock=Clock(),
        ingestion_worker=MockIngestionWorker(),
    )
    application.state.conversation_runner = MockConversationRunner()

    async with application.router.lifespan_context(application):
        await asyncio.sleep(0.05)

    assert len(ingest_runs) >= 1
    assert any("embedded-ingest:" in r for r in ingest_runs)
    assert len(conv_runs) >= 1
    assert any("embedded-conv:" in r for r in conv_runs)
