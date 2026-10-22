"""Same-process Q&A host proof: real application/providers, in-memory ports, no sockets."""

import json
from contextlib import AsyncExitStack, suppress
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
from knora.providers.openai_compatible.answer_blocks import ANSWER_BLOCK_SCHEMA
from knora.providers.openai_compatible.generation import (
    CLOUDFLARE_PROMPT_VERSION,
    CLOUDFLARE_SYSTEM_PROMPT,
    OpenAICompatibleGenerationProvider,
)

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
async def host(tmp_path, no_external_io, request):
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
        "response_format": {"type": "json_schema", "json_schema": ANSWER_BLOCK_SCHEMA},
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
    port = MemoryAnsweringPort()
    mode = getattr(request, "param", "exact")
    dynamic = mode in {"dynamic", "package"}
    package = None
    max_tokens = 2048 if dynamic else 32
    if dynamic:
        import hashlib

        from knora.evaluation.live_admission import response_authority_pins

        binding["candidate_budget"] = 8
        binding.pop("approval")
        binding["approval"] = {
            "owner_issuer": "issuer",
            "owner_subject": "owner",
            "binding_digest": digest_json(binding),
        }
        payload = dict(selection=selection, binding=binding)
        inputs = {
            "payload": payload,
            "frozen": asdict(frozen),
            "retrieval_configuration": asdict(RetrievalConfiguration.milestone_one()),
            "chunk_digests": {
                "chunk-1": hashlib.sha256(port.candidate.content.encode()).hexdigest()
            },
        }
        policy["scope"] = live_scope("qa", "host-proof", WORKSPACE, payload)
        policy["max_attempts"] = 2
        policy["response_chain"] = {
            "kind": "qa",
            "input_digest": digest_json(inputs),
            "pins": response_authority_pins("qa"),
        }
        for provider in policy["providers"]:
            provider["request_digests"] = []
        policy["providers"][0].update(max_input_bytes=8192, max_output_tokens=max_tokens)
        path = tmp_path / "host.sqlite"
        if mode == "package":
            from datetime import timedelta

            from test_live_admission import package_manifest, slot_inputs

            from knora.evaluation.live_admission import LivePackage

            manifest = package_manifest(tmp_path)
            manifest.update(
                journal_path=str(path.resolve()),
                ownership={"workspace_id": WORKSPACE, "resource_id": "owned-stack"},
            )
            manifest["gold_v1"].update(
                dataset_digest=frozen.reference.digest, dataset_id=frozen.reference.dataset_id
            )
            package = LivePackage.initialize(manifest, path, clock=lambda: NOW)
            corpus = approval()
            corpus.update(approval_id=package.approval_id("corpus_prepare"))
            corpus["scope"].update(purpose="corpus_prepare", workspace_id=WORKSPACE)
            package.bind_slot(
                "corpus_prepare", corpus, slot_inputs(package, "corpus_prepare", corpus)
            )
            package.bind_execution("corpus_prepare", {"request_id": "corpus_prepare"})
            cleanup = {
                "registration_id": "test-only",
                "scope": manifest["ownership"],
                "proof_digest": "e" * 64,
                "deadline": (NOW + timedelta(minutes=15)).isoformat(),
            }
            stack_window = package.window(
                scope=manifest["ownership"], cleanup=cleanup, start=lambda: None, stop=lambda: None
            )
            stack_window.__enter__()
            with package.operation("corpus_prepare"):
                package.record_result(
                    "corpus_prepare",
                    {
                        "sources": {
                            "version-1": {
                                "raw_sha256": "a" * 64,
                                "chunk_digests": list(inputs["chunk_digests"].values()),
                            }
                        },
                        "embedding_configuration_id": EMBEDDING.id,
                    },
                )
            policy["approval_id"] = package.approval_id("qa_gold_v1_answer")
            identities = {
                "case_id": "answer",
                "request_id": "dynamic-once",
                "dataset_digest": frozen.reference.digest,
                "selection_digest": digest_json(selection),
                "binding_digest": binding["approval"]["binding_digest"],
            }
            package.bind_slot(
                "qa_gold_v1_answer",
                policy,
                slot_inputs(package, "qa_gold_v1_answer", policy, authority=inputs, **identities),
            )
        admission = LiveAdmission(
            policy,
            path,
            clock=lambda: NOW,
            response_inputs=inputs,
            qa_store=port,
            package=package,
            slot="qa_gold_v1_answer" if package else None,
        )
    else:
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
                                    "before": [
                                        {
                                            "text": "Blue",
                                            "support": ["E1"],
                                            "bold": None,
                                        }
                                    ],
                                    "items": [],
                                    "after": [],
                                    "refusal_reason": None,
                                }
                            )
                        },
                    }
                ],
            },
        )

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
                max_tokens=max_tokens,
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
            package=package,
        )
    assert qa.is_closed and sync.is_closed and async_client.is_closed
    if package:
        if package.snapshot()["stopped"]:
            with pytest.raises(ValueError, match="LIVE_PACKAGE_STOPPED"):
                stack_window.__exit__(None, None, None)
        else:
            stack_window.__exit__(None, None, None)


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
@pytest.mark.parametrize("host", ["dynamic", "package"], indirect=True)
async def test_response_dependent_qa_validates_actual_retrieval_and_saved_trace(host):
    ready = host.service.preflight(
        WORKSPACE, OWNER, "pdf-set", ("answer",), "host-proof", asdict(host.frozen.reference)
    )
    assert ready["status"] == "READY"
    run = host.service.start_run(WORKSPACE, OWNER, ready["preflight_id"], "dynamic-once")
    assert await host.service.process_run(WORKSPACE, run["run_id"])
    assert run["execution_status"] == "COMPLETED", run["observations"]
    assert run["observations"]["answer"]["generation_evidence"] == [["E1", "The sky is blue."]]
    assert [url for url, _ in host.sent] == [EMBED_ENDPOINT, ENDPOINT]
    assert host.admission.snapshot()["attempts"] == 2
    if host.package:
        output = host.package.slot_result("qa_gold_v1_answer")
        assert output["capture"]["run_id"] == run["run_id"]
        assert output["capture"]["trace_id"] == "host-trace"
        assert output["capture"]["answer"] == "Blue [[E1]]"
        assert host.package.snapshot()["attempts"] == 2


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


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["package"], indirect=True)
@pytest.mark.parametrize("failure", [None, "checkpoint", "finish"])
async def test_package_qa_completes_only_after_run_store_saves(host, monkeypatch, failure):
    saved_states = []
    store = host.service._store
    for method in ("checkpoint", "finish"):
        original = getattr(store, method)

        def save(*args, _method=method, _original=original):
            state = host.package.snapshot()["slots"]["qa_gold_v1_answer"]["status"]
            saved_states.append((_method, state))
            if _method == failure:
                raise OSError("isolated store failure")
            return _original(*args)

        monkeypatch.setattr(store, method, save)
    ready = host.service.preflight(
        WORKSPACE, OWNER, "pdf-set", ("answer",), "host-proof", asdict(host.frozen.reference)
    )
    run = host.service.start_run(WORKSPACE, OWNER, ready["preflight_id"], "dynamic-once")
    if failure:
        with suppress(OSError):
            await host.service.process_run(WORKSPACE, run["run_id"])
        assert host.package.snapshot()["stopped"]
        assert host.package.snapshot()["slots"]["qa_gold_v1_answer"]["status"] == "STARTED"
    else:
        await host.service.process_run(WORKSPACE, run["run_id"])
        assert saved_states == [("checkpoint", "STARTED"), ("finish", "STARTED")]
        assert host.package.slot_result("qa_gold_v1_answer")["capture"]["trace_id"] == "host-trace"


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["package"], indirect=True)
@pytest.mark.parametrize("drift", ["case", "gold"])
async def test_refusal_slot_cannot_rebind_the_approved_answer_case(host, drift):
    from copy import deepcopy

    from test_live_admission import slot_inputs

    policy = deepcopy(host.admission._policy)
    policy["approval_id"] = host.package.approval_id("qa_gold_v1_refusal")
    inputs = slot_inputs(
        host.package,
        "qa_gold_v1_refusal",
        policy,
        **host.package.slot_binding("qa_gold_v1_answer")["identities"],
    )
    if drift == "gold":
        inputs["identities"].update(case_id="refusal", dataset_digest="f" * 64)
    with pytest.raises(ValueError, match="LIVE_SLOT_CASE"):
        host.package.bind_slot("qa_gold_v1_refusal", policy, inputs)
    assert host.package.snapshot()["attempts"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["package"], indirect=True)
@pytest.mark.parametrize("drift", [None, "batch", "source", "original_digest"])
async def test_ragas_qa_requires_saved_proposal_ancestry_and_allows_reviewed_edits(host, drift):
    from copy import deepcopy
    from dataclasses import replace

    from test_live_admission import slot_inputs

    from knora.evaluation.contracts import FreezeApproval, freeze_dataset
    from knora.evaluation.live_admission import response_authority_pins

    package = host.package
    source = {
        "dataset_id": "pdf-set",
        "pdf_sources": [
            {
                "document_id": "document-1",
                "document_version_id": "version-1",
                "raw_sha256": "a" * 64,
            }
        ],
    }
    payload = {"source": source}
    proposal_policy = approval()
    proposal_policy.update(
        approval_id=package.approval_id("ragas_vi_draft"),
        max_attempts=1,
        scope=live_scope("proposals", "proposal", WORKSPACE, payload),
    )
    package.bind_slot(
        "ragas_vi_draft",
        proposal_policy,
        slot_inputs(
            package,
            "ragas_vi_draft",
            proposal_policy,
            authority=payload,
            dataset_id="pdf-set",
            request_id="proposal",
        ),
    )
    execution = {"dataset_id": "pdf-set", "request_id": "proposal", "batch_id": "batch"}
    package.bind_execution("ragas_vi_draft", execution)
    generated = replace(host.frozen.gold.cases[0], case_id="ragas-batch-01")
    result = {
        "identities": execution,
        "source": deepcopy(source),
        "cases": {
            generated.case_id: {
                "case": asdict(generated),
                "case_digest": digest_json(asdict(generated)),
            }
        },
        "case_ids": [generated.case_id],
    }
    if drift == "batch":
        result["identities"] = {**execution, "batch_id": "foreign"}
    elif drift == "source":
        result["source"]["pdf_sources"][0]["raw_sha256"] = "f" * 64
    elif drift == "original_digest":
        result["cases"][generated.case_id]["case_digest"] = "f" * 64
    with package.operation("ragas_vi_draft"):
        package.record_result("ragas_vi_draft", result)

    # save_case permits editing the whole Case; each new digest needs owner review/freeze.
    edited = replace(
        generated,
        question="Reviewed question?",
        reference_answer="Reviewed answer",
        required_facts=("Reviewed fact",),
        category="multi-hop",
        evidence_groups=(
            replace(
                generated.evidence_groups[0],
                alternatives=(
                    replace(generated.evidence_groups[0].alternatives[0], quote="sky is blue"),
                ),
            ),
        ),
    )
    gold = replace(
        host.frozen.gold, identity=replace(host.frozen.gold.identity, version=2), cases=(edited,)
    )
    frozen = freeze_dataset(gold, FreezeApproval("issuer", "owner", gold.digest))
    inputs = deepcopy(host.admission._response_inputs)
    inputs["frozen"] = asdict(frozen)
    selection = json.loads(select_cases(frozen, (edited.case_id,)).to_json())
    binding = deepcopy(host.binding)
    binding["reference"] = asdict(frozen.reference)
    binding["anchors"] = {
        digest_json(asdict(a)): {"status": "READY", "chunk_ids": ["chunk-1"]}
        for g in edited.evidence_groups
        for a in g.alternatives
    }
    binding.pop("approval")
    binding["approval"] = {
        "owner_issuer": "issuer",
        "owner_subject": "owner",
        "binding_digest": digest_json(binding),
    }
    inputs["payload"] = {"selection": selection, "binding": binding}
    policy = deepcopy(host.admission._policy)
    policy.update(
        approval_id=package.approval_id("qa_ragas_answer"),
        scope=live_scope("qa", "host-proof", WORKSPACE, inputs["payload"]),
    )
    policy["response_chain"] = {
        "kind": "qa",
        "input_digest": digest_json(inputs),
        "pins": response_authority_pins("qa"),
    }
    package.bind_slot(
        "qa_ragas_answer",
        policy,
        slot_inputs(
            package,
            "qa_ragas_answer",
            policy,
            authority=inputs,
            request_id="r3",
            case_id=edited.case_id,
            dataset_digest=frozen.reference.digest,
            selection_digest=digest_json(selection),
            binding_digest=binding["approval"]["binding_digest"],
        ),
    )
    if drift:
        with pytest.raises(ValueError, match="LIVE_SLOT_ANCESTRY"):
            LiveAdmission(
                policy,
                package._path,
                clock=lambda: NOW,
                package=package,
                slot="qa_ragas_answer",
                response_inputs=inputs,
                qa_store=host.port,
            )
    else:
        admission = LiveAdmission(
            policy,
            package._path,
            clock=lambda: NOW,
            package=package,
            slot="qa_ragas_answer",
            response_inputs=inputs,
            qa_store=host.port,
        )
        assert admission._case == edited
    assert host.sent == []
    assert package.snapshot()["attempts"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["package"], indirect=True)
@pytest.mark.parametrize("boundary", ["bind", "dispatch"])
async def test_package_rejects_source_drift_between_slots_before_egress(
    host, monkeypatch, boundary
):
    from copy import deepcopy
    from pathlib import Path

    from test_live_admission import slot_inputs

    original = Path.read_text

    def changed(path, *args, **kwargs):
        content = original(path, *args, **kwargs)
        return (
            content + "\n# changed schema\n"
            if path.as_posix().endswith("providers/structured_generation.py")
            else content
        )

    monkeypatch.setattr(Path, "read_text", changed)
    with pytest.raises(ValueError, match="LIVE_PACKAGE_BUILD"):
        if boundary == "dispatch":
            with host.admission.dispatch(host.admission._policy["scope"]):
                pytest.fail("source drift reached dispatch")
        else:
            policy = deepcopy(host.admission._policy)
            policy["approval_id"] = host.package.approval_id("qa_gold_v1_refusal")
            identities = {
                **host.package.slot_binding("qa_gold_v1_answer")["identities"],
                "case_id": "refusal",
            }
            host.package.bind_slot(
                "qa_gold_v1_refusal",
                policy,
                slot_inputs(
                    host.package,
                    "qa_gold_v1_refusal",
                    policy,
                    authority=host.admission._response_inputs,
                    **identities,
                ),
            )
    monkeypatch.setattr(Path, "read_text", original)
    assert host.sent == []
    assert host.package.snapshot()["attempts"] == 0
