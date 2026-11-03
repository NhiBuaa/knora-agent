"""Bounded HTTP delivery check against the already admitted S2 Compose application."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from backend.runtime_test.s2_runtime_guard import (
    require_owned_s2_application_rows,
    require_owned_s2_database,
    require_reference_file,
    selected_s2_volumes,
)
from sqlalchemy import select

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.evaluation_reader import PostgresEvaluationReader
from knora.adapters.postgres.tables import IngestionJobTable, WorkspaceTable
from knora.answering.retrieval_configuration import retrieval_configuration_for_id
from knora.infrastructure.lexical_configuration import load_lexical_population


def _owned_application(root):
    selected_s2_volumes()
    run_id = os.environ.get("KNORA_S2_RUN_ID")
    project = (
        f"knora-retrieval-test-{run_id}"
        if run_id
        else os.environ.get("KNORA_S2_PROJECT", "knora-153-s2")
    )
    command = ["docker", "--host", "npipe:////./pipe/dockerDesktopLinuxEngine"]
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("DOCKER_", "COMPOSE_"))
    }
    inspected = subprocess.run(
        command
        + [
            "inspect",
            f"{project}-verification-api-1",
            f"{project}-verification-postgres-1",
            f"{project}-verification-qdrant-1",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    rows = json.loads(inspected.stdout)
    api_row = require_owned_s2_application_rows(rows, root)
    return command, environment, api_row["Id"], api_row["Image"]


def _windows_worker_environment(root, environment):
    assert os.name == "nt", "Q18 requires the existing Windows PDF hard limit"
    worker_environment = {
        key: value for key, value in environment.items() if not key.upper().startswith("KNORA_")
    }
    worker_environment.update(
        {
            "PYTHONPATH": str(root / "backend/src") + os.pathsep + str(root),
            "KNORA_DATABASE_URL": SessionFactory.kw["bind"].url.render_as_string(
                hide_password=False
            ),
            "KNORA_PROVIDER_MODE": "deterministic-local",
            "KNORA_EMBEDDING_PROVIDER": "deterministic-local",
            "KNORA_GENERATION_PROVIDER": "deterministic-local",
            "KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID": "embedding-local-m1-v2",
            "KNORA_RETRIEVAL_CONFIGURATION_ID": "retrieval-bm25-upload-fixture-top8-v1",
            "KNORA_LEXICAL_POPULATION_MANIFEST": str(
                root / "evals/fixtures/pdf_retrieval_v3_s2/upload-lexical-population-v1.json"
            ),
            "KNORA_LEXICAL_QDRANT_URL": "http://127.0.0.1:16433",
            "KNORA_LEXICAL_QDRANT_COLLECTION": os.environ["KNORA_S2_APPLICATION_COLLECTION"],
            "KNORA_OBJECT_STORE_BACKEND": "filesystem",
            "KNORA_OBJECT_STORE_ROOT": os.environ["KNORA_S2_OBJECT_STORE_ROOT"],
        }
    )
    return worker_environment


def test_owned_compose_http_upload_worker_question_and_archive():
    require_owned_s2_database(SessionFactory.kw["bind"].url)
    workspace_id = str(UUID(os.environ["KNORA_S2_HTTP_WORKSPACE_ID"]))
    api_key = os.environ["KNORA_S2_HTTP_API_KEY"]
    assert len(api_key) >= 32
    root = Path(__file__).resolve().parents[2]
    docker, environment, container_id, image_id = _owned_application(root)
    artifact = Path(os.environ["KNORA_S2_EVIDENCE_ROOT"]) / ("http-application-" + uuid4().hex)
    artifact.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "incomplete",
        "workspace_id": workspace_id,
        "workers": [],
        "container_id": container_id,
        "image_id": image_id,
        "docker_endpoint": docker[2],
    }
    resume = None
    if resume_path := os.environ.get("KNORA_S2_HTTP_RESUME_REPORT"):
        resume_path = Path(resume_path).resolve()
        assert resume_path.parent.parent == artifact.parent.resolve()
        require_reference_file(resume_path, os.environ["KNORA_S2_HTTP_RESUME_REPORT_SHA256"])
        resume = json.loads(resume_path.read_text(encoding="utf-8"))
        assert resume["workspace_id"] == workspace_id and resume["status"] == "incomplete"
        assert resume["extracted"]["status"] == "retry_scheduled"
        report["resumed_report"] = str(resume_path)
        report["resumed_report_sha256"] = os.environ["KNORA_S2_HTTP_RESUME_REPORT_SHA256"]
    try:
        with SessionFactory.begin() as session:
            workspace = session.get(WorkspaceTable, workspace_id)
            assert (workspace is not None) if resume else (workspace is None)
            retained = session.scalars(
                select(IngestionJobTable).where(
                    IngestionJobTable.status.in_(("queued", "processing", "retry_scheduled"))
                )
            ).all()
            if resume:
                assert len(retained) == 1
                job = retained[0]
                assert job.id == resume["submission"]["ingestion_job_id"]
                assert job.workspace_id == workspace_id and job.derivation_kind == "pdf_extraction"
                assert job.status == "retry_scheduled" and job.attempt_count == 1
            else:
                assert not retained, "retained queue must not be changed to admit the check"
                session.add(WorkspaceTable(id=workspace_id, name="S2 Compose HTTP application"))
        population = load_lexical_population(
            retrieval_configuration_for_id("retrieval-bm25-upload-fixture-top8-v1"),
            str(root / "evals/fixtures/pdf_retrieval_v3_s2/upload-lexical-population-v1.json"),
        )
        pdf = (root / "evals/fixtures/pdf_retrieval_v3_s2/refund-policy.pdf").read_bytes()
        report["source_sha256"] = hashlib.sha256(pdf).hexdigest()
        with httpx.Client(
            base_url="http://127.0.0.1:18053",
            headers={"X-API-Key": api_key},
            timeout=30,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            path = f"/v1/workspaces/{workspace_id}"
            if resume:
                assert resume["source_sha256"] == report["source_sha256"]
                uploaded = resume["submission"]
            else:
                response = client.post(
                    path + "/documents",
                    headers={"Idempotency-Key": uuid4().hex},
                    data={"source_key": "refund-policy"},
                    files={"file": ("refund-policy.pdf", pdf, "application/pdf")},
                )
                assert response.status_code == 202, response.text
                uploaded = response.json()
            report["submission"] = uploaded
            job_path = path + "/ingestion-jobs/" + uploaded["ingestion_job_id"]
            document_path = path + "/documents/" + uploaded["document_id"]
            assert client.get(job_path).json()["derivation_kind"] == "pdf_extraction"
            worker_environment = _windows_worker_environment(root, environment)
            isolation = subprocess.run(
                [sys.executable, "-m", "knora.adapters.cli.worker", "--check-pdf-isolation"],
                cwd=root,
                env=worker_environment,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            report["pdf_isolation"] = {
                "returncode": isolation.returncode,
                "stdout": isolation.stdout,
                "stderr": isolation.stderr,
            }
            assert isolation.returncode == 0 and isolation.stdout.strip() == "PDF_ISOLATION_OK"
            for phase in ("extracted", "indexed"):
                worker = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "knora.adapters.cli.worker",
                        "--once",
                    ],
                    cwd=root,
                    env=worker_environment,
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
                report["workers"].append(
                    {
                        "phase": phase,
                        "returncode": worker.returncode,
                        "stdout": worker.stdout,
                        "stderr": worker.stderr,
                    }
                )
                assert worker.returncode == 0, report["workers"][-1]
                response = client.get(job_path)
                assert response.status_code == 200, response.text
                status = response.json()
                report[phase] = status
                assert status["status"] == "succeeded", status
                assert status["ingestion_job_id"] == uploaded["ingestion_job_id"]
                if phase == "extracted":
                    assert status["indexing_status"] == "queued"
                    assert status["lexical_readiness"] == "not_indexed"
                    assert status["poll_after_seconds"] > 0
                else:
                    assert status["indexing_status"] == "succeeded", status
                    assert status["indexing_job_id"] == report["extracted"]["indexing_job_id"]
            response = client.get(document_path)
            assert response.status_code == 200, response.text
            document = response.json()
            report["document"] = document
            assert document["lexical_readiness"] == "ready"
            assert document["embedding_readiness"] == "not_indexed"
            assert document["answer_availability"] == "available"
            question = {"workspace_id": workspace_id, "question": "Refund requests within 30 days?"}
            response = client.post("/v1/questions", json=question)
            assert response.status_code == 200, response.text
            answer = response.json()
            report["answer"] = answer
            assert answer["decision"] == "ANSWER" and len(answer["citations"]) == 1
            reader = PostgresEvaluationReader(SessionFactory, lexical_population=population)
            chunks = reader.read_pdf_chunks(workspace_id=workspace_id)
            trace = reader.read_trace(trace_id=answer["trace_id"], workspace_id=workspace_id)
            assert len(chunks) == 1 and chunks[0].raw_sha256 == report["source_sha256"]
            assert trace.embedding_configuration_id is None
            assert trace.provider_metadata["embedding"] == {"status": "not_run"}
            assert trace.provider_metadata["generation"]["provider"] == "deterministic-local"
            assert trace.retrieval_configuration_id == "retrieval-bm25-upload-fixture-top8-v1"
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
            response = client.post(
                document_path + "/archive", headers={"If-Match": str(document["revision"])}
            )
            assert response.status_code == 200, response.text
            response = client.post("/v1/questions", json=question)
            report["archived_question"] = response.json()
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "LEXICAL_RETRIEVAL_UNAVAILABLE"
        report["status"] = "passed"
        report["scope"] = (
            "real loopback HTTP/Compose deterministic application; no semantic assessment"
        )
    finally:
        (artifact / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
