"""Isolated evaluation composition of the production HTTP/auth/Conversation adapters.

Run with uvicorn --factory; this module does not register a deployment policy.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from evals.datasets.vietnamese_rag_v1 import load_vietnamese_dataset
from evals.runners.vietnamese_conversation import (
    code_provenance,
    configuration_from_calibration,
    validate_evaluation_database,
)
from sqlalchemy.engine import make_url


def validate_runtime_settings(settings, context_policy):
    if (
        context_policy != "conversation-context-v2"
        or settings.embedding_provider != "ollama"
        or settings.generation_provider != "ollama"
        or not getattr(settings, "expected_generation_model_digest", None)
        or not settings.keycloak_issuer
        or not settings.keycloak_audience
        or not settings.keycloak_jwks_url
    ):
        raise ValueError("real provider, context and OIDC acceptance configuration required")


async def run_worker(runner, workspace_id, stopping):
    while not stopping.is_set():
        worked = await runner.run_once(
            worker_id="isolated-ollama-browser-evaluation", workspace_id=workspace_id
        )
        if not worked:
            with suppress(TimeoutError):
                await asyncio.wait_for(stopping.wait(), timeout=0.5)


def create_application():
    validate_evaluation_database(os.environ["KNORA_DATABASE_URL"])
    provenance = code_provenance(Path(__file__).resolve().parents[2])
    dataset = load_vietnamese_dataset(
        Path(os.environ["KNORA_EVAL_DATASET"]), Path(os.environ["KNORA_EVAL_MANIFEST"])
    )
    configuration = configuration_from_calibration(
        dataset, json.loads(Path(os.environ["KNORA_EVAL_CALIBRATION"]).read_text(encoding="utf-8"))
    )
    workspace_id = os.environ["KNORA_EVAL_WORKSPACE_ID"]

    # Import the real adapters only after the database and committed inputs are verified.
    from evals.runners.vietnamese_retrieval import load_active_bindings, validate_active_corpus

    from knora.adapters.postgres.answering_store import PostgresAnsweringStore
    from knora.adapters.postgres.database import SessionFactory as HttpSessionFactory
    from knora.answering.module import AnswerQuestion
    from knora.bootstrap import build_provider_selection
    from knora.conversations.context import CONTEXT_POLICY_ID
    from knora.infrastructure.database import SessionFactory
    from knora.infrastructure.settings import settings

    validate_runtime_settings(settings, CONTEXT_POLICY_ID)
    for factory in (SessionFactory, HttpSessionFactory):
        bound_url = factory.kw["bind"].url
        validate_evaluation_database(str(bound_url.render_as_string(hide_password=False)))
        if bound_url != make_url(os.environ["KNORA_DATABASE_URL"]):
            raise ValueError("acceptance database binding mismatch")
    validate_active_corpus(dataset, load_active_bindings(SessionFactory, workspace_id))
    providers = build_provider_selection(settings)
    if providers.embedding_configuration.id != dataset.profile_id:
        providers.embedding_provider.close()
        raise ValueError("acceptance embedding profile mismatch")
    answer = AnswerQuestion(
        embedding_provider=providers.embedding_provider,
        generation_provider=providers.generation_provider,
        store=PostgresAnsweringStore(SessionFactory),
        embedding_configuration=providers.embedding_configuration,
        retrieval_configuration=configuration,
    )
    try:
        from knora.main import app as unused_default_app
        from knora.main import create_app

        application = create_app(answer_question=answer)
    except BaseException:
        # The generation adapter's asynchronous client is lazy and has not opened.
        providers.embedding_provider.close()
        raise
    original_lifespan = application.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        # main currently composes its default app eagerly. Own that unused app's
        # lifespan as well so its bootstrap providers are closed on shutdown.
        async with (
            unused_default_app.router.lifespan_context(unused_default_app),
            original_lifespan(app),
        ):
            stopping = asyncio.Event()
            worker = asyncio.create_task(
                run_worker(app.state.conversation_runner, workspace_id, stopping)
            )
            try:
                yield
            finally:
                stopping.set()
                try:
                    await worker
                finally:
                    providers.embedding_provider.close()
                    await providers.generation_provider.aclose()

    application.router.lifespan_context = lifespan
    application.state.evaluation_provenance = provenance
    return application
