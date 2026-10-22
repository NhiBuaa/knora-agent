"""Opt-in rollback proof with fresh fixture PDF; retains all earlier jobs/points."""

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from backend.runtime_test.s2_runtime_guard import require_owned_s2_database
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.adapters.pdf.pypdf import PypdfTextExtractor
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import (
    ChunkTable,
    IngestionJobTable,
    LexicalGenerationTable,
    LexicalHeadTable,
    WorkspaceTable,
)
from knora.infrastructure.settings import Settings
from knora.ingestion.search_indexing import StaleGenerationError, lexical_point_id
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.deterministic.generation import DeterministicGenerationProvider


def _jobs():
    with SessionFactory() as session:
        return dict(
            session.execute(
                text("SELECT id,to_jsonb(j)::text FROM ingestion_jobs j ORDER BY id")
            ).all()
        )


def test_rollback_reextracts_a_into_c_and_fences_b(monkeypatch):
    require_owned_s2_database(SessionFactory.kw["bind"].url)
    run_id = uuid4().hex
    artifact = Path(os.environ["KNORA_S2_EVIDENCE_ROOT"]) / ("rollback-application-" + run_id)
    artifact.mkdir(parents=True, exist_ok=False)
    collection = "s2_rollback_" + run_id
    report = {
        "status": "incomplete",
        "native_calls": [],
        "extractions": 0,
        "collection": collection,
    }
    before = _jobs()
    blocker = SessionFactory()
    transport = httpx.HTTPTransport.handle_request
    extract = PypdfTextExtractor.extract

    def capture(self, request):
        # Reserve the budget and validate exact collection before any actual send.
        assert (request.url.scheme, request.url.host, request.url.port) == (
            "http",
            "127.0.0.1",
            16433,
        )
        prefix = "/collections/" + collection
        assert request.url.path == prefix or request.url.path.startswith(prefix + "/")
        assert len(report["native_calls"]) < 40
        record = {
            "method": request.method,
            "url": str(request.url),
            "request": json.loads(request.content) if request.content else None,
        }
        report["native_calls"].append(record)
        response = transport(self, request)
        response.read()
        record.update(status=response.status_code, response=response.json())
        return response

    def counted_extract(self, *args, **kwargs):
        report["extractions"] += 1
        return extract(self, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("rollback proof must not call embedding or generation")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", capture)
    monkeypatch.setattr(PypdfTextExtractor, "extract", counted_extract)
    monkeypatch.setattr(DeterministicEmbeddingProvider, "embed", forbidden)
    monkeypatch.setattr(DeterministicGenerationProvider, "generate", forbidden)
    try:
        # Existing queued/retry rows remain locked, unchanged; SKIP LOCKED admits only new work.
        blocker.scalars(
            select(IngestionJobTable)
            .where(IngestionJobTable.status.in_(("queued", "retry_scheduled")))
            .with_for_update()
        ).all()
        from knora import main

        monkeypatch.setattr(
            main,
            "settings",
            Settings(
                _env_file=None,
                provider_mode="deterministic-local",
                embedding_provider="deterministic-local",
                generation_provider="deterministic-local",
                retrieval_configuration_id="retrieval-bm25-upload-fixture-top8-v1",
                lexical_population_manifest="evals/fixtures/pdf_retrieval_v3_s2/upload-lexical-population-v1.json",
                lexical_qdrant_url="http://127.0.0.1:16433",
                lexical_qdrant_collection=collection,
                object_store_backend="filesystem",
                object_store_root=str(artifact / "objects"),
            ),
        )
        workspace_id = str(uuid4())
        with SessionFactory.begin() as session:
            session.add(WorkspaceTable(id=workspace_id, name="S2 rollback fixture"))
        app = main.create_app(
            api_key_authenticator=ApiKeyAuthenticator(
                (ApiCredential("s2-rollback", hash_api_key(run_id), workspace_id, True),)
            )
        )
        # Global expired recovery belongs to separate tests; never recover retained work here.
        monkeypatch.setattr(
            app.state.ingestion_worker._store, "observe_expired_attempt", lambda: None
        )
        report["recovery_scope"] = (
            "global expired recovery disabled only in fixture; claim/lease/finalization remain real"
        )
        pdf = Path("evals/fixtures/pdf_retrieval_v3_s2/refund-policy.pdf").read_bytes()
        report["source_sha256"] = hashlib.sha256(pdf).hexdigest()
        store = PostgresSearchIndexStore(SessionFactory)
        with TestClient(app, headers={"X-API-Key": run_id}) as client:
            path = "/v1/workspaces/" + workspace_id
            response = client.post(
                path + "/documents",
                headers={"Idempotency-Key": "initial"},
                data={"source_key": "refund-policy"},
                files={"file": ("refund-policy.pdf", pdf, "application/pdf")},
            )
            assert response.status_code == 202, response.text
            uploaded = response.json()
            job_path = path + "/ingestion-jobs/" + uploaded["ingestion_job_id"]
            app.state.ingestion_worker.run_once("s2-rollback-initial-extraction")
            app.state.ingestion_worker.run_once("s2-rollback-initial-index")
            status = client.get(job_path).json()
            assert status["status"] == status["indexing_status"] == "succeeded", status
            assert status["lexical_revision"] == 1
            with SessionFactory() as session:
                head = session.get(LexicalHeadTable, uploaded["document_id"])
                a = store._decode_generation(
                    session.get(LexicalGenerationTable, head.active_generation_id)
                )
                texts = dict(
                    session.execute(
                        select(ChunkTable.id, ChunkTable.content).where(
                            ChunkTable.chunk_set_id == a.chunk_set_id
                        )
                    ).all()
                )
            native = app.state.ingestion_worker._handler._index_handler._index
            d = replace(a, generation_id=str(uuid4()), revision=2)
            store.request_generation(d, expected_revision=1)
            store.activate_ready(d, native.stage_generation(d, texts))
            # Only this new fixture's superseded A points are removed, never retained run evidence.
            with SessionFactory.begin() as session:
                assert (
                    store.cleanup_generation_in_transaction(
                        session, a.generation_id, native.remove_generation
                    )
                    == "removed"
                )
            b = replace(a, generation_id=str(uuid4()), revision=3)
            store.request_generation(b, expected_revision=2)
            b_receipt = native.stage_generation(b, texts)
            status = client.get(job_path).json()
            assert status["lexical_revision"] == 3
            reprocess_path = (
                path + "/document-versions/" + uploaded["document_version_id"] + "/reprocess"
            )
            command = {
                "config_mode": "same_as_job",
                "config_source_job_id": uploaded["ingestion_job_id"],
                "expected_lexical_revision": status["lexical_revision"],
            }
            response = client.post(
                reprocess_path, headers={"Idempotency-Key": "rollback"}, json=command
            )
            assert response.status_code == 202, response.text
            rollback = response.json()
            assert (
                rollback["outcome"] == "created"
                and rollback["ingestion_job_id"] != uploaded["ingestion_job_id"]
            )
            replay = client.post(
                reprocess_path, headers={"Idempotency-Key": "rollback"}, json=command
            )
            assert replay.json()["outcome"] == "idempotency_replay"
            conflict = client.post(
                reprocess_path, headers={"Idempotency-Key": "stale-rollback"}, json=command
            )
            assert (
                conflict.status_code == 409
                and conflict.json()["error"]["code"] == "REVISION_CONFLICT"
            )
            with pytest.raises(StaleGenerationError):
                store.activate_ready(b, b_receipt)
            app.state.ingestion_worker.run_once("s2-rollback-C-extraction")
            app.state.ingestion_worker.run_once("s2-rollback-C-index")
            c_status = client.get(path + "/ingestion-jobs/" + rollback["ingestion_job_id"]).json()
            assert c_status["status"] == c_status["indexing_status"] == "succeeded", c_status
            with SessionFactory() as session:
                head = session.get(LexicalHeadTable, a.document_id)
                c = store._decode_generation(
                    session.get(LexicalGenerationTable, head.active_generation_id)
                )
                parent = session.get(IngestionJobTable, rollback["ingestion_job_id"])
                children = session.scalars(
                    select(IngestionJobTable).where(
                        IngestionJobTable.parent_ingestion_job_id.in_(
                            (uploaded["ingestion_job_id"], parent.id)
                        )
                    )
                ).all()
                assert parent.lexical_head_revision == 4 and c.revision == head.revision == 5
                assert len(children) == 2
                assert {row.parent_ingestion_job_id for row in children} == {
                    uploaded["ingestion_job_id"],
                    parent.id,
                }
                assert (
                    next(
                        row for row in children if row.parent_ingestion_job_id == parent.id
                    ).lexical_generation_id
                    == c.generation_id
                )
                assert c.lexical_profile == a.lexical_profile and c.chunk_set_id == a.chunk_set_id
                assert c.generation_id not in {a.generation_id, b.generation_id, d.generation_id}
            with pytest.raises(StaleGenerationError):
                store.activate_ready(b, b_receipt)
            assert report["extractions"] == 2
            with httpx.Client(
                base_url="http://127.0.0.1:16433", trust_env=False, timeout=10
            ) as wire:
                points = wire.post(
                    "/collections/" + collection + "/points",
                    json={
                        "ids": [
                            lexical_point_id(g.generation_id, a.chunks[0].chunk_id) for g in (a, c)
                        ]
                    },
                )
                points.raise_for_status()
                assert {p["id"] for p in points.json()["result"]} == {
                    lexical_point_id(c.generation_id, c.chunks[0].chunk_id)
                }
            report.update(
                status="passed",
                a=a.generation_id,
                b=b.generation_id,
                c=c.generation_id,
                public_revision=c_status["lexical_revision"],
                rollback=rollback,
                scope=(
                    "fresh deterministic fixture, real extraction/native stage+readback/CAS; "
                    "no query/generation"
                ),
            )
    finally:
        blocker.rollback()
        blocker.close()
        after = _jobs()
        report["existing_job_count"] = len(before)
        report["existing_jobs_unchanged"] = all(
            after.get(key) == value for key, value in before.items()
        )

        def digest(rows):
            return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()

        report["existing_jobs_before_sha256"] = digest(before)
        report["existing_jobs_after_sha256"] = digest({key: after.get(key) for key in before})
        (artifact / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        assert report["existing_jobs_unchanged"]
