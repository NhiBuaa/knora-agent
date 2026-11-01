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
async def test_create_app_lifespan_closes_reranking_provider() -> None:
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
