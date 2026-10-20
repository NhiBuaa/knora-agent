"""Fresh production upload/worker/native retrieval/citation in the owned S2 runtime."""

import hashlib
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from backend.runtime_test.s2_runtime_guard import (
    require_owned_s2_database,
    require_reference_file,
    reserve_native_request,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.evaluation_reader import PostgresEvaluationReader
from knora.adapters.postgres.tables import IngestionJobTable, WorkspaceTable
from knora.infrastructure.settings import Settings
from knora.ingestion.search_indexing import lexical_point_id
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.deterministic.generation import DeterministicGenerationProvider


def test_fresh_upload_two_jobs_native_question_citation_and_archive_fence(monkeypatch):
    require_owned_s2_database(SessionFactory.kw["bind"].url)
    run_id = uuid4().hex
    artifact = Path(os.environ["KNORA_S2_EVIDENCE_ROOT"]) / ("upload-application-" + run_id)
    artifact.mkdir(parents=True, exist_ok=False)
    report = {"run_id": run_id, "status": "incomplete", "native_calls": [], "generation_calls": 0}
    transport = httpx.HTTPTransport.handle_request
    generate = DeterministicGenerationProvider.generate

    def capture(self, request):
        record = reserve_native_request(request, report["native_calls"], limit=40)
        response = transport(self, request)
        response.read()
        record.update(status=response.status_code, response=response.json())
        return response

    def forbidden_embedding(*_args, **_kwargs):
        raise AssertionError("lexical application must not embed")

    async def counted_generation(self, **kwargs):
        report["generation_calls"] += 1
        return await generate(self, **kwargs)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", capture)
    monkeypatch.setattr(DeterministicEmbeddingProvider, "embed", forbidden_embedding)
    monkeypatch.setattr(DeterministicGenerationProvider, "generate", counted_generation)
    try:
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
                lexical_qdrant_collection="s2_upload_application_" + run_id,
                object_store_backend="filesystem",
                object_store_root=str(artifact / "objects"),
            ),
        )
        workspace_id = str(uuid4())
        with SessionFactory.begin() as session:
            # Retained jobs are evidence; an occupied queue is never repaired by this test.
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(IngestionJobTable)
                    .where(
                        IngestionJobTable.status.in_(("queued", "processing", "retry_scheduled"))
                    )
                )
                == 0
            ), "isolated queue is occupied"
            session.add(WorkspaceTable(id=workspace_id, name="S2 native upload application"))
        app = main.create_app(
            api_key_authenticator=ApiKeyAuthenticator(
                (ApiCredential("s2-upload", hash_api_key(run_id), workspace_id, True),)
            )
        )
        pdf = Path("evals/fixtures/pdf_retrieval_v3_s2/refund-policy.pdf").read_bytes()
        report["source_sha256"] = hashlib.sha256(pdf).hexdigest()
        report["workspace_id"] = workspace_id
        with TestClient(app, headers={"X-API-Key": run_id}) as client:
            path = f"/v1/workspaces/{workspace_id}"
            response = client.post(
                path + "/documents",
                headers={"Idempotency-Key": run_id},
                data={"source_key": "refund-policy"},
                files={"file": ("refund-policy.pdf", pdf, "application/pdf")},
            )
            assert response.status_code == 202, response.text
            uploaded = response.json()
            report["submission"] = uploaded
            job_path = path + "/ingestion-jobs/" + uploaded["ingestion_job_id"]
            document_path = path + "/documents/" + uploaded["document_id"]
            assert client.get(job_path).json()["derivation_kind"] == "pdf_extraction"
            app.state.ingestion_worker.run_once("s2-upload-extraction")
            extracted = client.get(job_path).json()
            report["extracted"] = extracted
            assert extracted["status"] == "succeeded", extracted
            assert extracted["indexing_status"] == "queued"
            assert extracted["lexical_readiness"] == "not_indexed"
            assert extracted["poll_after_seconds"] > 0
            app.state.ingestion_worker.run_once("s2-upload-index")
            indexed = client.get(job_path).json()
            report["indexed"] = indexed
            assert indexed["ingestion_job_id"] == uploaded["ingestion_job_id"]
            assert indexed["indexing_job_id"] == extracted["indexing_job_id"]
            assert indexed["indexing_status"] == "succeeded", indexed
            document = client.get(document_path).json()
            report["document"] = document
            assert document["lexical_readiness"] == "ready"
            assert document["embedding_readiness"] == "not_indexed"
            assert document["answer_availability"] == "available"
            question = {"workspace_id": workspace_id, "question": "Refund requests within 30 days?"}
            response = client.post("/v1/questions", json=question)
            assert response.status_code == 200, response.text
            answer = response.json()
            report["answer"] = answer
            assert answer["decision"] == "ANSWER"
            assert len(answer["citations"]) == 1
            reader = PostgresEvaluationReader(
                SessionFactory,
                lexical_population=app.state.answer_question._store._lexical_population,
            )
            chunks = reader.read_pdf_chunks(workspace_id=workspace_id)
            assert len(chunks) == 1 and chunks[0].raw_sha256 == report["source_sha256"]
            trace = reader.read_trace(trace_id=answer["trace_id"], workspace_id=workspace_id)
            assert trace.embedding_configuration_id is None
            assert trace.retrieval_configuration_id == "retrieval-bm25-upload-fixture-top8-v1"
            counter_path = Path("evals/fixtures/pdf_retrieval_v3_s2/upload-native-counter-v1.json")
            counter = json.loads(counter_path.read_text(encoding="utf-8"))
            tokens = counter["chunks"][0]["tokens"]
            assert len(tokens) == len(set(tokens)) == 7
            murmur = Path(os.environ["KNORA_S2_MURMUR_REFERENCE"])
            require_reference_file(
                murmur, "45368bfe11080c4504b7804602015d93873303c5b13d5710af6c42e9abc35b4a"
            )
            hashes = subprocess.run(
                [
                    "node",
                    "-e",
                    "const fs=require('node:fs');const hash=require(process.argv[1]);"
                    "const tokens=JSON.parse(fs.readFileSync(0,'utf8'));"
                    "process.stdout.write(JSON.stringify(tokens.map(t=>Math.abs("
                    "hash(Buffer.from(t,'utf8').toString('latin1'),0).result()|0))));",
                    str(murmur),
                ],
                input=json.dumps(tokens),
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            generation_id = trace.provider_metadata["retrieval"]["lexical_generations"][0][
                "index_generation_id"
            ]
            with httpx.Client(
                base_url="http://127.0.0.1:16433", trust_env=False, timeout=10
            ) as native:
                persisted = native.post(
                    f"/collections/{main.settings.lexical_qdrant_collection}/points",
                    json={
                        "ids": [lexical_point_id(generation_id, chunks[0].chunk_id)],
                        "with_vector": True,
                        "with_payload": True,
                    },
                )
                persisted.raise_for_status()
                points = persisted.json()["result"]
            assert len(points) == 1
            vector = points[0]["vector"]["bm25"]
            # Seven distinct tokens at the measured average length each have TF weight1.
            assert dict(zip(vector["indices"], vector["values"], strict=True)) == pytest.approx(
                dict.fromkeys(json.loads(hashes.stdout), 1.0), rel=2e-6
            )
            report["fixture_native_vector_parity"] = {
                "token_count": 7,
                "status": "passed",
                "murmur_reference_sha256": hashlib.sha256(murmur.read_bytes()).hexdigest(),
                "counter_artifact_sha256": hashlib.sha256(counter_path.read_bytes()).hexdigest(),
            }
            citation = answer["citations"][0]
            for field in (
                "document_version_id",
                "content_checksum",
                "page_start",
                "page_end",
                "start_offset",
                "end_offset",
            ):
                assert citation[field] == getattr(chunks[0], field)
            assert trace.alias_mapping[citation["evidence_id"]] == chunks[0].chunk_id
            assert report["generation_calls"] == 1
            query_count = sum(c["url"].endswith("/points/query") for c in report["native_calls"])
            assert query_count == 1
            archived = client.post(
                document_path + "/archive", headers={"If-Match": str(document["revision"])}
            )
            assert archived.status_code == 200, archived.text
            blocked = client.post("/v1/questions", json=question)
            report["archived_question"] = blocked.json()
            assert blocked.status_code == 503
            assert blocked.json()["error"]["code"] == "LEXICAL_RETRIEVAL_UNAVAILABLE"
            assert sum(c["url"].endswith("/points/query") for c in report["native_calls"]) == 1
            assert report["generation_calls"] == 1
        report["status"] = "passed"
        report["scope"] = "native PG/application fixture; semantic quality not assessed"
    finally:
        (artifact / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
