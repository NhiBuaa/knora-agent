import asyncio
import hashlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from evals.runners.pdf_baseline_runtime import build_evaluation_app
from evals.runners.pdf_retrieval_v3 import PdfHttpExecutor
from evals.runners.pdf_source_binding import propose_bindings, validate_binding_review
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from knora.access.keycloak import KeycloakAuthenticator
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.evaluation_reader import PostgresEvaluationReader
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.deterministic.generation import DeterministicGenerationProvider
from knora.providers.embedding import EmbeddingConfiguration


def pdf_bytes():
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (Refund requests are accepted within 30 days.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def isolated_pdf_sessions(monkeypatch):
    # Recovery scans the whole database; other suites deliberately leave expired turn fixtures.
    import knora.main
    from knora.adapters.postgres import database

    name = f"knora153s1_pdf_test_{uuid4().hex}"
    url = SessionFactory.kw["bind"].url.set(database=name)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    engine = create_engine(url)
    with admin.connect() as connection:
        connection.execute(text(f"CREATE DATABASE {name}"))
    try:
        monkeypatch.setenv("KNORA_DATABASE_URL", url.render_as_string(hide_password=False))
        backend = Path(__file__).parents[3]
        config = Config(str(backend / "alembic.ini"))
        config.set_main_option("script_location", str(backend / "migrations"))
        command.upgrade(config, "head")
        sessions = sessionmaker(bind=engine, expire_on_commit=False)
        monkeypatch.setattr(database, "SessionFactory", sessions)
        monkeypatch.setattr(knora.main, "SessionFactory", sessions)
        yield sessions
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE {name} WITH (FORCE)"))
        admin.dispose()


@pytest.mark.asyncio
async def test_real_pdf_upload_worker_trace_and_follow_up_share_source_provenance(
    tmp_path, isolated_pdf_sessions
):
    import time

    authenticator = KeycloakAuthenticator(
        issuer="https://s1-eval",
        audience="knora-api",
        token_validator=lambda token: {
            "iss": "https://s1-eval",
            "aud": "knora-api",
            "sub": "owner" + token,
            "exp": time.time() + 60,
            "capabilities": ["questions:ask", "documents:write", "documents:read"],
        },
    )
    profile = EmbeddingConfiguration.milestone_one_local()
    application = build_evaluation_app(
        embedding_provider=DeterministicEmbeddingProvider(),
        generation_provider=DeterministicGenerationProvider(),
        embedding_configuration=profile,
        objects_root=tmp_path / "objects",
        authenticator=authenticator,
    )
    headers = {"Authorization": "Bearer one"}
    reader = PostgresEvaluationReader(isolated_pdf_sessions)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://s1"
    ) as client:
        response = await client.post(
            "/v1/workspaces",
            headers=headers | {"Idempotency-Key": uuid4().hex},
            json={"name": "S1 deterministic E2E"},
        )
        assert response.status_code == 201, response.text
        workspace = response.json()["id"]
        raw = pdf_bytes()
        source = NS(
            id="policy", path=tmp_path / "policy.pdf", sha256=hashlib.sha256(raw).hexdigest()
        )
        source.path.write_bytes(raw)
        executor = PdfHttpExecutor(
            client=client,
            headers=headers,
            reader=reader,
            workspace_id=workspace,
            run_id=uuid4().hex,
            embedding_configuration_id=profile.id,
            poll_interval=0.01,
            max_polls=2000,
        )
        upload = asyncio.create_task(executor.upload(source))
        for _ in range(500):
            if upload.done():
                break
            await asyncio.to_thread(application.state.ingestion_worker.run_once, "s1-e2e-worker")
            await asyncio.sleep(0.01)
        result = await upload
        assert result["status"] == "succeeded", result
        chunks = reader.read_pdf_chunks(workspace_id=workspace)
        assert chunks[0].parser_configuration_id == "pdf-parser-pypdf-6-14-2-layout-lines-v2"
        assert chunks[0].raw_sha256 == source.sha256
        dataset = NS(
            corpus_sha256="a" * 64,
            dataset_sha256="b" * 64,
            sources=(source,),
            anchors=(NS(id="days", source_id="policy", page=1, text="30 days"),),
        )
        proposal = propose_bindings(dataset, chunks)
        bindings = validate_binding_review(
            proposal,
            {
                "status": "approved",
                "reviewer": "NhiBuaa",
                "decision_url": "https://github.com/NhiBuaa/knora-agent/issues/153#test-fixture",
                "proposal_sha256": proposal["proposal_sha256"],
                "choices": {"days": [0]},
            },
        )
        first = NS(
            id="first", question="Refund requests are accepted within 30 days.", parent_case_id=None
        )
        observed = await executor.execute(first)
        assert observed["failure_code"] is None, observed
        assert set(observed["selected_chunk_ids"]) & set(bindings["days"])
        conversation = await executor.conversation(first.id)
        parent = asyncio.create_task(executor.execute(first, conversation_id=conversation))
        for _ in range(200):
            if parent.done():
                break
            await application.state.conversation_runner.run_once(
                worker_id="s1-conversation-worker", workspace_id=workspace
            )
            await asyncio.sleep(0.01)
        parent_row = await parent
        assert parent_row["failure_code"] is None, parent_row
        follow = NS(id="follow", question="How many days?", parent_case_id="first")
        turn = asyncio.create_task(
            executor.execute(
                follow, conversation_id=conversation, parent_turn_id=parent_row["turn_id"]
            )
        )
        for _ in range(200):
            if turn.done():
                break
            await application.state.conversation_runner.run_once(
                worker_id="s1-conversation-worker", workspace_id=workspace
            )
            await asyncio.sleep(0.01)
        row = await turn
        assert row["failure_code"] is None, row
        assert row["turn_id"] and row["trace_id"] != parent_row["trace_id"]
        rejected = await client.get(
            f"/v1/workspaces/{workspace}/conversations/{conversation}/turns/{row['turn_id']}",
            headers={"Authorization": "Bearer two"},
        )
        assert rejected.status_code == 403
