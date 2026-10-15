"""Cloudflare application contracts with fake provider HTTP and isolated PostgreSQL."""

import json
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from ingestion.test_issue_19_application_e2e import _pdf_with_pages
from sqlalchemy import select, text

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.adapters.execution.thread_attempt_runner import FixedCapacityThreadAttemptRunner
from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.adapters.pdf.pypdf import PypdfTextExtractor
from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.tables import (
    DocumentTable,
    DocumentVersionTable,
    QuestionTraceTable,
    WorkspaceTable,
)
from knora.answering.module import AnswerQuestion
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    PdfDerivationHandler,
    PdfDerivationProfile,
    ProcessIngestionJob,
    RetryPolicyV1,
    SystemRandomSource,
    UuidOperationIds,
)
from knora.ingestion.jobs import IngestionJobs
from knora.main import create_app
from knora.providers.cloudflare.embedding import CloudflareEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration
from knora.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider

PROFILE = EmbeddingConfiguration.cloudflare_qwen3_06b()
ACCOUNT = "0123456789abcdef0123456789abcdef"
TOKEN = "fake-cloudflare-token"
FACT = "The unique fact is blue umbrellas."


@pytest.fixture
def cloudflare_app(tmp_path: Path, request: pytest.FixtureRequest):
    workspace_id = f"cf-contract-{uuid4()}"
    other_workspace_id = f"cf-contract-{uuid4()}"
    owner_key = f"cf-owner-{uuid4()}"
    other_key = f"cf-other-{uuid4()}"
    with SessionFactory.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE workspace_admissions, reprocess_audit_records, "
                "idempotency_records, ingestion_job_attempts, ingestion_jobs"
            )
        )
        session.add_all(
            [
                WorkspaceTable(id=workspace_id, name="Cloudflare contract owner"),
                WorkspaceTable(id=other_workspace_id, name="Cloudflare contract other"),
            ]
        )

    state = {
        "embedding_requests": [],
        "generation_requests": [],
        "embedding_response": None,
        "generation_content": None,
    }

    def embedding_endpoint(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        state["embedding_requests"].append(payload)
        if isinstance(state["embedding_response"], Exception):
            raise state["embedding_response"]
        if state["embedding_response"] is not None:
            return state["embedding_response"]
        values = payload.get("documents", payload.get("queries", []))
        vectors = [
            ([1.0, 0.0] if FACT in value or "queries" in payload else [0.0, 1.0]) + [0.0] * 1022
            for value in values
        ]
        return httpx.Response(
            200,
            headers={"cf-ray": f"embed-{len(state['embedding_requests'])}"},
            json={"result": {"data": vectors, "shape": [len(values), 1024]}},
        )

    async def generation_endpoint(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        state["generation_requests"].append(payload)
        content = state["generation_content"]
        if content is None:
            content = json.dumps(
                {
                    "decision": "ANSWER",
                    "before": [
                        {
                            "text": "Blue umbrellas.",
                            "support": ["E1"],
                            "bold": None,
                        }
                    ],
                    "items": [],
                    "after": [],
                    "refusal_reason": None,
                }
            )
        if "presentation" in payload["response_format"]["json_schema"]["properties"]:
            content = json.dumps({"presentation": "prose"})
        return httpx.Response(
            200,
            headers={"x-request-id": f"generate-{len(state['generation_requests'])}"},
            json={
                "model": "@cf/openai/gpt-oss-20b",
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            },
        )

    embedding = CloudflareEmbeddingProvider(
        account_id=ACCOUNT,
        api_token=TOKEN,
        client=httpx.Client(transport=httpx.MockTransport(embedding_endpoint)),
    )
    generation = OpenAICompatibleGenerationProvider(
        base_url=f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/v1",
        api_key=TOKEN,
        model="@cf/openai/gpt-oss-20b",
        input_cost_per_million_tokens=None,
        output_cost_per_million_tokens=None,
        pricing_version=None,
        provider_identity="cloudflare-workers-ai",
        max_tokens=1024,
        direct_json_schema=True,
        client=httpx.AsyncClient(transport=httpx.MockTransport(generation_endpoint)),
    )
    object_store = FileSystemObjectStore(tmp_path)
    store = PostgresIngestionJobStore(SessionFactory)
    app = create_app(
        ingestion_jobs=IngestionJobs(
            object_store=object_store,
            store=store,
            deployed_embedding_configuration=PROFILE,
        ),
        ingestion_worker=ProcessIngestionJob(
            store=store,
            handler=PdfDerivationHandler(
                object_store=object_store,
                extractor=PypdfTextExtractor(),
                embedding_provider=embedding,
                profile_resolver=lambda work: (
                    PdfDerivationProfile.milestone_two(
                        embedding_configuration=EmbeddingConfiguration.milestone_one_local()
                    )
                    if getattr(request, "param", False)
                    else store.pdf_profile_for_work(work)
                ),
                runtime_embedding_configuration=PROFILE,
            ),
            operation_ids=UuidOperationIds(),
            timing=AttemptTimingV1.standard(),
            retry_policy=RetryPolicyV1(SystemRandomSource()),
            runner=FixedCapacityThreadAttemptRunner(max_concurrency=1),
        ),
        answer_question=AnswerQuestion(
            embedding_provider=embedding,
            generation_provider=generation,
            store=PostgresAnsweringStore(SessionFactory),
            embedding_configuration=PROFILE,
        ),
        api_key_authenticator=ApiKeyAuthenticator(
            (
                ApiCredential("owner", hash_api_key(owner_key), workspace_id, True),
                ApiCredential("other", hash_api_key(other_key), other_workspace_id, True),
            )
        ),
        embedding_configuration=PROFILE,
        object_store=object_store,
    )
    with TestClient(app) as client:
        yield client, app, state, workspace_id, other_workspace_id, owner_key, other_key


def _upload(client: TestClient, workspace_id: str, key: str):
    return client.post(
        f"/v1/workspaces/{workspace_id}/documents",
        headers={"X-API-Key": key, "Idempotency-Key": f"cf-upload-{uuid4()}"},
        data={"source_key": f"support/{uuid4()}"},
        files={
            "file": ("fact.pdf", _pdf_with_pages("Introductory page.", FACT), "application/pdf")
        },
    )


def test_cloudflare_pdf_public_journey_preserves_citation_and_provenance(cloudflare_app) -> None:
    client, app, state, workspace_id, _, owner_key, _ = cloudflare_app
    upload = _upload(client, workspace_id, owner_key)
    assert upload.status_code == 202
    document_version_id = upload.json()["document_version_id"]
    job_id = upload.json()["ingestion_job_id"]

    worker_result = app.state.ingestion_worker.run_once("cf-contract-worker")
    assert worker_result.__class__.__name__ == "Succeeded", worker_result
    poll = client.get(
        f"/v1/workspaces/{workspace_id}/ingestion-jobs/{job_id}",
        headers={"X-API-Key": owner_key},
    )
    assert poll.status_code == 200
    assert poll.json()["status"] == "succeeded"
    assert poll.json()["serving_state"] == "current"

    question = client.post(
        "/v1/questions",
        headers={"X-API-Key": owner_key},
        json={"workspace_id": workspace_id, "question": FACT},
    )
    assert question.status_code == 200, question.text
    answer = question.json()
    assert answer["decision"] == "ANSWER"
    citation = answer["citations"][0]
    assert citation["source_key"].startswith("support/")
    assert citation["document_version_id"] == document_version_id
    assert citation["page_start"] == citation["page_end"] == 2
    assert citation["start_offset"] == 0
    assert citation["end_offset"] == len(FACT)
    assert citation["excerpt"] == FACT
    with SessionFactory() as session:
        trace = session.scalar(
            select(QuestionTraceTable).where(QuestionTraceTable.id == answer["trace_id"])
        )
        version = session.get(DocumentVersionTable, document_version_id)
        assert trace is not None and version is not None
        assert version.raw_sha256 is not None
        assert citation["content_checksum"] == sha256(FACT.encode()).hexdigest()
        assert trace.embedding_configuration_id == PROFILE.id
        assert trace.provider_metadata["embedding"]["provider"] == "cloudflare-workers-ai"
        assert trace.provider_metadata["embedding"]["model"] == PROFILE.model
        assert trace.provider_metadata["generation"]["provider"] == "cloudflare-workers-ai"
        assert trace.provider_metadata["generation"]["model"] == "@cf/openai/gpt-oss-20b"
    assert len(state["embedding_requests"]) == 2
    assert "documents" in state["embedding_requests"][0]
    assert "queries" in state["embedding_requests"][1]
    assert state["generation_requests"][0]["max_tokens"] == 1024
    assert state["generation_requests"][0]["response_format"]["type"] == "json_schema"
    assert len(state["generation_requests"]) == 2


def test_cross_workspace_requests_stop_before_cloudflare(cloudflare_app) -> None:
    client, _, state, workspace_id, _, owner_key, other_key = cloudflare_app
    upload = _upload(client, workspace_id, owner_key)
    assert upload.status_code == 202
    job_id = upload.json()["ingestion_job_id"]
    requests = (
        client.post(
            "/v1/questions",
            headers={"X-API-Key": other_key},
            json={"workspace_id": workspace_id, "question": FACT},
        ),
        _upload(client, workspace_id, other_key),
        client.get(
            f"/v1/workspaces/{workspace_id}/ingestion-jobs/{job_id}",
            headers={"X-API-Key": other_key},
        ),
        client.get(
            f"/v1/workspaces/{workspace_id}/operator/traces/{uuid4()}",
            headers={"X-API-Key": other_key},
        ),
    )
    assert [response.status_code for response in requests] == [403] * 4
    assert not state["embedding_requests"]
    assert not state["generation_requests"]


def test_empty_workspace_refuses_without_generation(cloudflare_app) -> None:
    client, _, state, _, other_workspace_id, _, other_key = cloudflare_app
    question = client.post(
        "/v1/questions",
        headers={"X-API-Key": other_key},
        json={"workspace_id": other_workspace_id, "question": FACT},
    )
    assert question.status_code == 200
    assert question.json()["decision"] == "REFUSAL"
    assert question.json()["citations"] == []
    assert question.json()["refusal_reason"] == "INSUFFICIENT_EVIDENCE"
    assert len(state["embedding_requests"]) == 1
    assert not state["generation_requests"]


@pytest.mark.parametrize(
    "content",
    [
        "fake-cloudflare-token-invalid-json",
        '{"decision":"ANSWER","before":[{"text":"Blue umbrellas.","support":["E99"],"bold":null}],'
        '"items":[],"after":[],"refusal_reason":null}',
        '{"decision":"ANSWER","before":[{"text":"Blue umbrellas.","support":["E1"],"bold":null}],'
        '"items":[],"after":[],"refusal_reason":"INSUFFICIENT_EVIDENCE"}',
    ],
)
def test_invalid_cloudflare_generation_returns_safe_error(cloudflare_app, content: str) -> None:
    client, app, state, workspace_id, _, owner_key, _ = cloudflare_app
    upload = _upload(client, workspace_id, owner_key)
    assert upload.status_code == 202
    assert (
        app.state.ingestion_worker.run_once("cf-invalid-generation").__class__.__name__
        == "Succeeded"
    )
    state["generation_content"] = content
    question = client.post(
        "/v1/questions",
        headers={"X-API-Key": owner_key},
        json={"workspace_id": workspace_id, "question": FACT},
    )
    assert question.status_code == 502
    assert question.json() == {"error": {"code": "GENERATION_OUTPUT_INVALID"}}
    assert TOKEN not in question.text
    with SessionFactory() as session:
        traces = session.scalars(
            select(QuestionTraceTable).where(QuestionTraceTable.workspace_id == workspace_id)
        ).all()
        assert not any(trace.validation_outcome == "valid" for trace in traces)


@pytest.mark.parametrize(
    "failure",
    [
        "shape",
        "timeout",
        401,
        403,
        429,
        500,
        503,
    ],
)
def test_embedding_failure_never_activates_pdf(cloudflare_app, failure: str | int) -> None:
    client, app, state, workspace_id, _, owner_key, _ = cloudflare_app
    upload = _upload(client, workspace_id, owner_key)
    assert upload.status_code == 202
    if failure == "shape":
        state["embedding_response"] = httpx.Response(
            200,
            json={"result": {"data": [[1.0] * 1023], "shape": [1, 1023]}},
        )
    elif failure == "timeout":
        state["embedding_response"] = httpx.ReadTimeout("fake-cloudflare-token")
    else:
        state["embedding_response"] = httpx.Response(failure, text=TOKEN)
    outcome = app.state.ingestion_worker.run_once(f"cf-failure-{failure}")
    assert outcome.__class__.__name__ == "RetryScheduled", outcome
    assert outcome.safe_code == (
        "worker_unexpected" if failure == "shape" else "provider_transient"
    )
    poll = client.get(
        f"/v1/workspaces/{workspace_id}/ingestion-jobs/{upload.json()['ingestion_job_id']}",
        headers={"X-API-Key": owner_key},
    )
    assert poll.status_code == 200
    assert poll.json()["status"] == "retry_scheduled"
    assert poll.json()["error_code"] is None
    assert poll.json()["failure_reason"] is None
    assert poll.json()["next_attempt_at"] is not None
    assert poll.json()["terminal_at"] is None
    assert poll.json()["serving_state"] == "unavailable"
    with SessionFactory() as session:
        document = session.scalar(
            select(DocumentTable).where(DocumentTable.workspace_id == workspace_id)
        )
        assert document is not None
        assert document.active_embedding_set_id is None
    assert not state["generation_requests"]
    assert TOKEN not in poll.text

    state["embedding_response"] = None
    question = client.post(
        "/v1/questions",
        headers={"X-API-Key": owner_key},
        json={"workspace_id": workspace_id, "question": FACT},
    )
    assert question.status_code == 200
    assert question.json()["decision"] == "REFUSAL"
    assert question.json()["refusal_reason"] == "INSUFFICIENT_EVIDENCE"
    assert question.json()["citations"] == []
    assert not state["generation_requests"]


@pytest.mark.parametrize("cloudflare_app", [True], indirect=True)
def test_pdf_profile_mismatch_fails_before_cloudflare(cloudflare_app) -> None:
    client, app, state, workspace_id, _, owner_key, _ = cloudflare_app
    upload = _upload(client, workspace_id, owner_key)
    assert upload.status_code == 202
    outcome = app.state.ingestion_worker.run_once("cf-profile-mismatch")
    assert outcome.__class__.__name__ == "FailedTerminal", outcome
    assert outcome.safe_code == "configuration_invalid"
    assert outcome.failure_reason == "terminal_config"
    poll = client.get(
        f"/v1/workspaces/{workspace_id}/ingestion-jobs/{upload.json()['ingestion_job_id']}",
        headers={"X-API-Key": owner_key},
    )
    assert poll.status_code == 200
    assert poll.json()["status"] == "failed"
    assert poll.json()["failure_reason"] == "terminal_config"
    assert poll.json()["error_code"] == "configuration_invalid"
    assert "next_attempt_at" not in poll.json()
    with SessionFactory() as session:
        document = session.scalar(
            select(DocumentTable).where(DocumentTable.workspace_id == workspace_id)
        )
        assert document is not None
        assert document.active_embedding_set_id is None
    assert not state["embedding_requests"]


def test_pytest_defaults_ignore_developer_cloudflare_selectors(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "KNORA_EMBEDDING_PROVIDER=cloudflare-workers-ai\n"
        "KNORA_GENERATION_PROVIDER=cloudflare-workers-ai\n"
        "KNORA_EMBEDDING_DIMENSION=1024\n"
        "KNORA_CLOUDFLARE_ACCOUNT_ID=0123456789abcdef0123456789abcdef\n"
        "KNORA_CLOUDFLARE_API_TOKEN=developer-secret\n"
        "KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID=embedding-cloudflare-qwen3-06b-v1\n",
        encoding="utf-8",
    )
    backend = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        environment.pop(name, None)
    environment.update(
        {
            "PYTHONPATH": os.pathsep.join((str(backend / "test"), str(backend / "src"))),
            "KNORA_EMBEDDING_PROVIDER": "cloudflare-workers-ai",
            "KNORA_GENERATION_PROVIDER": "cloudflare-workers-ai",
            "KNORA_EMBEDDING_DIMENSION": "1024",
            "KNORA_CLOUDFLARE_ACCOUNT_ID": "0123456789abcdef0123456789abcdef",
            "KNORA_CLOUDFLARE_API_TOKEN": "developer-secret",
            "KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID": "embedding-cloudflare-qwen3-06b-v1",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import conftest; from knora.infrastructure.settings import Settings; "
            "from knora.bootstrap import build_provider_selection; "
            "selected = build_provider_selection(Settings()); "
            "assert selected.embedding_configuration.provider == 'deterministic-local'; "
            "assert type(selected.generation_provider).__name__ == "
            "'DeterministicGenerationProvider'",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
