"""Same-process Q&A host proof: real application/providers, in-memory ports, no sockets."""

import json
from contextlib import AsyncExitStack
from dataclasses import asdict
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.engine import Engine
from test_live_admission import ENDPOINT, MODEL, NOW, approval
from test_pdf_runs import OWNER, ROOT, WORKSPACE, GoldReader, binding_for, frozen_dataset
from test_runs import MemoryStore

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.answering.module import AnswerQuestion
from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration, RetrievalResult
from knora.evaluation.catalog import Milestone3Catalog
from knora.evaluation.contracts import digest_json, select_cases
from knora.evaluation.live_admission import LiveAdmission, binding_dispatch, live_scope
from knora.evaluation.pdf_runtime import PdfRuntimeProfile, pdf_http_profile
from knora.evaluation.runs import EvaluationRunService
from knora.main import create_app
from knora.providers.cloudflare.embedding import CloudflareEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration
from knora.providers.openai_compatible.generation import (
    CLOUDFLARE_PROMPT_VERSION,
    CLOUDFLARE_SYSTEM_PROMPT,
    OpenAICompatibleGenerationProvider,
)
from knora.providers.structured_generation import STRUCTURED_RESULT_SCHEMA

EMBEDDING = EmbeddingConfiguration.cloudflare_qwen3_06b()
EMBED_ENDPOINT = (
    "https://api.cloudflare.com/client/v4/accounts/"
    + "a" * 32
    + "/ai/run/@cf/qwen/qwen3-embedding-0.6b"
)


class MemoryAnsweringPort:
    """Replace database I/O only; answering builds the actual trace record."""

    def __init__(self):
        self.traces = {}
        self.candidate = RetrievalCandidate(
            document_id="document-1",
            document_version_id="version-1",
            source_key="source",
            source_name="sky.pdf",
            chunk_set_id="set-1",
            embedding_set_id="embedding-set-1",
            embedding_configuration_id=EMBEDDING.id,
            chunk_id="chunk-1",
            chunk_ordinal=0,
            heading_path=(),
            start_line=1,
            end_line=1,
            content="The sky is blue.",
            content_checksum="fixture-checksum",
            token_count=5,
            cosine_distance=0.1,
            similarity=0.9,
        )

    def require_compatible_corpus(self, workspace_id, embedding_configuration_id):
        assert (workspace_id, embedding_configuration_id) == (WORKSPACE, EMBEDDING.id)

    def retrieve_candidates(self, **kwargs):
        assert kwargs["workspace_id"] == WORKSPACE
        assert kwargs["query_text"] == "What color is the sky?"
        assert kwargs["query_vector"] == (1.0,) + (0.0,) * 1023
        return RetrievalResult(
            (self.candidate,), embedding_set_ids=("embedding-set-1",), chunk_set_ids=("set-1",)
        )

    def persist_trace(self, trace):
        self.traces["host-trace"] = trace
        return "host-trace"

    def read_trace(self, *, trace_id, workspace_id):
        trace = self.traces[trace_id]
        assert trace.workspace_id == workspace_id
        candidate = SimpleNamespace(
            **asdict(self.candidate),
            workspace_id=workspace_id,
            final_rank=1,
            final_decision=trace.candidate_decisions[0]["final_decision"],
        )
        return SimpleNamespace(
            **asdict(trace),
            trace_id=trace_id,
            candidates=(candidate,),
            retrieval_latency_ms=trace.provider_metadata["retrieval"]["latency_ms"],
        )


@pytest.fixture
def no_external_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("This host proof permits only ASGI and MockTransport")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    monkeypatch.setattr(Engine, "connect", forbidden)


@pytest_asyncio.fixture
async def host(tmp_path, no_external_io):
    frozen = frozen_dataset()
    binding = binding_for(frozen)
    binding["embedding_configuration_id"] = EMBEDDING.id
    binding["retrieval_configuration_id"] = "retrieval-m1-v1"
    binding["generation"] = {
        "provider": "cloudflare-workers-ai",
        "model": MODEL,
        "prompt_version": CLOUDFLARE_PROMPT_VERSION,
    }
    binding.pop("approval")
    binding["approval"] = {
        "owner_issuer": "issuer",
        "owner_subject": "owner",
        "binding_digest": digest_json(binding),
    }
    selection = json.loads(select_cases(frozen, ("answer",)).to_json())
    scope = live_scope("qa", "host-proof", WORKSPACE, dict(selection=selection, binding=binding))
    query = {
        "queries": ["What color is the sky?"],
        "instruction": "Retrieve passages that answer this Vietnamese question.",
    }
    generation = {
        "model": MODEL,
        "max_tokens": 32,
        "messages": [
            {"role": "system", "content": CLOUDFLARE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": '{"question": "What color is the sky?", "evidence": '
                '[{"evidence_id": "E1", "content": "The sky is blue."}]}',
            },
        ],
        "response_format": {"type": "json_schema", "json_schema": STRUCTURED_RESULT_SCHEMA},
    }
    policy = approval()
    policy.update(scope=scope, max_attempts=3)
    policy["providers"][0]["max_input_bytes"] = 16384
    policy["providers"][0]["request_digests"] = [digest_json(generation)]
    policy["providers"].append(
        {
            "endpoint": EMBED_ENDPOINT,
            "model": EMBEDDING.model,
            "max_input_bytes": 4096,
            "max_output_tokens": 0,
            "compatibility_digest": "d" * 64,
            "request_digests": [digest_json(query)],
        }
    )
    admission = LiveAdmission(policy, tmp_path / "host.sqlite", clock=lambda: NOW)
    sent = []

    def exchange(request):
        sent.append((str(request.url), json.loads(request.content)))
        if str(request.url) == EMBED_ENDPOINT:
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {"shape": [1, 1024], "data": [[1.0] + [0.0] * 1023]},
                },
            )
        assert str(request.url) == ENDPOINT
        return httpx.Response(
            200,
            json={
                "model": MODEL,
                "usage": {"prompt_tokens": 20, "completion_tokens": 8},
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "decision": "ANSWER",
                                    "answer": "Blue [[E1]]",
                                    "cited_evidence_ids": ["E1"],
                                    "refusal_reason": None,
                                }
                            )
                        },
                    }
                ],
            },
        )

    port = MemoryAnsweringPort()
    async with AsyncExitStack() as stack:
        sync = stack.enter_context(admission.sync_client(mock=httpx.MockTransport(exchange)))
        async_client = await stack.enter_async_context(
            admission.async_client(mock=httpx.MockTransport(exchange))
        )
        answering = AnswerQuestion(
            embedding_provider=CloudflareEmbeddingProvider(
                account_id="a" * 32, api_token="fixture", client=sync
            ),
            generation_provider=OpenAICompatibleGenerationProvider(
                base_url=ENDPOINT.removesuffix("/chat/completions"),
                api_key="fixture",
                model=MODEL,
                input_cost_per_million_tokens=None,
                output_cost_per_million_tokens=None,
                pricing_version=None,
                client=async_client,
                provider_identity="cloudflare-workers-ai",
                max_tokens=32,
                direct_json_schema=True,
            ),
            store=port,
            embedding_configuration=EMBEDDING,
            retrieval_configuration=RetrievalConfiguration.milestone_one(),
        )
        credentials = ApiKeyAuthenticator(
            tuple(
                ApiCredential(workspace, hash_api_key(workspace), workspace, True)
                for workspace in (WORKSPACE, "foreign")
            )
        )
        app = create_app(
            answer_question=answering,
            api_key_authenticator=credentials,
            embedding_configuration=EMBEDDING,
            workspace_admission_store=None,
        )
        qa = await stack.enter_async_context(
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://knora.test",
                trust_env=False,
            )
        )
        observer = pdf_http_profile(
            profile_id="observer",
            kind="offline",
            endpoint="/v1/questions",
            api_key=WORKSPACE,
            trace_reader=port,
            client=qa,
            prepare=lambda _: binding,
        )
        profile = PdfRuntimeProfile(
            "host-proof", "live", observer.prepare, observer.execute, admission, async_client
        )
        service = EvaluationRunService(
            Milestone3Catalog(ROOT),
            MemoryStore(),
            (),
            datasets=GoldReader(frozen),
            pdf_profiles=(profile,),
        )
        yield SimpleNamespace(
            service=service,
            frozen=frozen,
            binding=binding,
            profile=profile,
            admission=admission,
            qa=qa,
            port=port,
            sent=sent,
            sync=sync,
            async_client=async_client,
        )
    assert qa.is_closed and sync.is_closed and async_client.is_closed


@pytest.mark.asyncio
async def test_real_qa_providers_and_pdf_observer_share_exact_dispatch_context(host):
    ready = host.service.preflight(
        WORKSPACE, OWNER, "pdf-set", ("answer",), "host-proof", asdict(host.frozen.reference)
    )
    assert ready["status"] == "READY"
    assert host.admission.snapshot()["attempts"] == 0
    run = host.service.start_run(WORKSPACE, OWNER, ready["preflight_id"], "once")
    assert await host.service.process_run(WORKSPACE, run["run_id"])
    observed = run["observations"]["answer"]
    assert observed["status"] == "OBSERVED", (
        observed,
        host.admission.snapshot(),
        list(host.port.traces),
    )
    assert observed["public_answer"] == "Blue [[E1]]"
    assert observed["generation_evidence"] == [["E1", "The sky is blue."]]
    assert observed["trace_id"] == "host-trace"
    assert host.port.traces["host-trace"].provider_metadata["embedding"]["model"] == EMBEDDING.model
    assert host.admission.snapshot() == {"attempts": 2, "pending": None, "stopped": False}
    assert [url for url, _ in host.sent] == [EMBED_ENDPOINT, ENDPOINT]
    assert run["execution_status"] == "COMPLETED"
    assert run["report"]["population"]["observed"] == 1
    assert run["report"]["cases"][0]["status"] == "OBSERVED"
    assert run["report"]["cases"][0]["trace_id"] == "host-trace"
    assert run["report"]["quality_status"] == "SEMANTIC_PENDING"
    assert not await host.service.process_run(WORKSPACE, run["run_id"])
    assert host.admission.snapshot()["attempts"] == 2
    response = await host.qa.post(
        "/v1/questions",
        headers={"X-API-Key": WORKSPACE},
        json={"workspace_id": WORKSPACE, "question": "What color is the sky?"},
    )
    assert response.status_code == 502
    assert host.admission.snapshot()["attempts"] == 2
    assert len(host.port.traces) == 1


@pytest.mark.asyncio
async def test_qa_outside_dispatch_cannot_consume_provider_attempt_or_save_trace(host):
    response = await host.qa.post(
        "/v1/questions",
        headers={"X-API-Key": WORKSPACE},
        json={"workspace_id": WORKSPACE, "question": "What color is the sky?"},
    )
    assert response.status_code == 502
    assert response.json() == {"error": {"code": "PROVIDER_RESPONSE_INVALID"}}
    assert host.admission.snapshot()["attempts"] == 0
    assert host.sent == [] and host.port.traces == {}


@pytest.mark.asyncio
async def test_foreign_qa_credential_is_denied_even_inside_admitted_dispatch(host):
    from knora.evaluation.live_admission import admitted_binding

    selection = json.loads(select_cases(host.frozen, ("answer",)).to_json())
    binding = admitted_binding(host.profile, WORKSPACE, selection, host.binding)
    with binding_dispatch(host.profile, binding):
        response = await host.qa.post(
            "/v1/questions",
            headers={"X-API-Key": "foreign"},
            json={"workspace_id": WORKSPACE, "question": "What color is the sky?"},
        )
    assert response.status_code == 403
    assert response.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
    assert host.admission.snapshot()["attempts"] == 0
    assert host.sent == [] and host.port.traces == {}
