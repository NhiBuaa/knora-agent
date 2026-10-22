from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from evals.runners.milestone_3 import (
    EvaluationEnvironmentBinding,
    M3Observation,
    SourceBinding,
    VerifiedM3Environment,
)

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.evaluation.catalog import Milestone3Catalog
from knora.evaluation.runs import EvaluationRunService, RuntimeProfile, production_http_profile

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = "evaluation-m3-v1"
RUNNER = WorkspacePrincipal(
    WORKSPACE, "operator", ("operator:read", "evaluations:run", "questions:ask")
)
READER = WorkspacePrincipal(WORKSPACE, "reader", ("operator:read",))


class MemoryStore:
    def __init__(self):
        self.runs = {}
        self.keys = {}
        self.preflights = {}

    def save_preflight(self, value):
        self.preflights[value["preflight_id"]] = value

    def get_preflight(self, workspace_id, preflight_id):
        value = self.preflights.get(preflight_id)
        return value if value and value["workspace_id"] == workspace_id else None

    def create(self, run, key):
        existing = self.keys.get((run["workspace_id"], key))
        if existing:
            if self.runs[existing]["request_digest"] != run["request_digest"]:
                raise KnoraError("EVALUATION_IDEMPOTENCY_CONFLICT")
            return self.runs[existing]
        self.keys[(run["workspace_id"], key)] = run["run_id"]
        self.runs[run["run_id"]] = run
        return run

    def get(self, workspace_id, run_id):
        run = self.runs.get(run_id)
        return run if run and run["workspace_id"] == workspace_id else None

    def list(self, workspace_id):
        return [run for run in self.runs.values() if run["workspace_id"] == workspace_id]

    def claim(self, workspace_id, run_id):
        run = self.get(workspace_id, run_id)
        if run["execution_status"] != "QUEUED":
            return None
        run["execution_status"] = "RUNNING"
        return "attempt-1"

    def checkpoint(self, workspace_id, run_id, attempt_id, case_id, observation):
        self.get(workspace_id, run_id)["observations"][case_id] = observation

    def finish(self, workspace_id, run_id, attempt_id, status, report):
        run = self.get(workspace_id, run_id)
        run["execution_status"] = status
        run["report"] = report


def profile(catalog, observations):
    data = catalog.get_dataset(WORKSPACE, "m3-dataset-v1")
    manifest = data.corpus
    bindings = tuple(
        SourceBinding(ref.rsplit("#", 1)[0], "version-" + ref.rsplit("#", 1)[0], "set-1")
        for ref in sorted(manifest.chunks)
    )
    binding = EvaluationEnvironmentBinding(
        dataset_manifest_identity="m3-dataset-v1",
        corpus_manifest_identity=manifest.version,
        chunk_set_provenance_id=manifest.chunk_set_id,
        workspace_id=WORKSPACE,
        retrieval_configuration_id="retrieval-m3-vector-v2",
        embedding_configuration_id="embedding-m3-v1",
        source_bindings=bindings,
    )
    documents = tuple(
        type(
            "Document",
            (),
            {
                "source_key": item.source_key,
                "document_version_id": item.production_document_version_id,
                "chunk_set_id": item.production_chunk_set_id,
                "chunk_references": tuple(
                    ref for ref in manifest.chunks if ref.rsplit("#", 1)[0] == item.source_key
                ),
            },
        )()
        for item in bindings
    )
    corpus = type("Corpus", (), {"workspace_id": WORKSPACE, "documents": documents})()

    async def execute(case, environment):
        assert isinstance(environment, VerifiedM3Environment)
        return observations[case.id]

    return RuntimeProfile("offline-test", "offline", lambda: (binding, corpus), execute)


def test_catalog_validates_native_manifest_and_returns_full_population(tmp_path):
    catalog = Milestone3Catalog(ROOT)
    entry = catalog.get_dataset(WORKSPACE, "m3-dataset-v1")
    assert len(entry.dataset.cases) >= 50
    assert entry.reference.native_digest.startswith("sha256:")
    assert catalog.list_datasets(WORKSPACE)[0].reference == entry.reference
    with pytest.raises(KnoraError):
        catalog.get_dataset("other", "m3-dataset-v1")


def test_preflight_denies_provider_and_capability_before_lookup():
    catalog = Milestone3Catalog(ROOT)
    service = EvaluationRunService(catalog, MemoryStore(), ())
    with pytest.raises(KnoraError, match="CAPABILITY_ACCESS_DENIED"):
        service.preflight(WORKSPACE, READER, "m3-dataset-v1", ("lexical-01",), "live")
    result = service.preflight(WORKSPACE, RUNNER, "m3-dataset-v1", ("lexical-01",), "live")
    assert result["status"] == "BLOCKED"
    assert "PROVIDER_APPROVAL_REQUIRED" in result["reasons"]
    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        service.read_run("other", RUNNER, "unknown")


@pytest.mark.asyncio
async def test_two_case_run_preserves_population_and_partial_report():
    catalog = Milestone3Catalog(ROOT)
    observations = {
        "lexical-01": M3Observation.failure("lexical-01", "EVALUATION_OBSERVATION_FAILURE"),
        "refusal-04": M3Observation.success(
            case_id="refusal-04",
            candidates=(),
            retrieval_latency_ms=1,
            end_to_end_latency_ms=2,
            retrieval_configuration_id="retrieval-m3-vector-v2",
            chunk_set_provenance_id="chunk-set-m3-v1",
            source_bindings=profile(catalog, {}).prepare()[0].source_bindings,
            decision="REFUSAL",
            refusal_reason="INSUFFICIENT_EVIDENCE",
            refusal_correctness=True,
        ),
    }
    store = MemoryStore()
    service = EvaluationRunService(catalog, store, (profile(catalog, observations),))
    preflight = service.preflight(
        WORKSPACE, RUNNER, "m3-dataset-v1", ("lexical-01", "refusal-04"), "offline-test"
    )
    assert preflight["status"] == "READY"
    run = service.start_run(WORKSPACE, RUNNER, preflight["preflight_id"], "key-1")
    assert (
        service.start_run(WORKSPACE, RUNNER, preflight["preflight_id"], "key-1")["run_id"]
        == run["run_id"]
    )
    with pytest.raises(KnoraError, match="EVALUATION_IDEMPOTENCY_CONFLICT"):
        second = service.preflight(
            WORKSPACE, RUNNER, "m3-dataset-v1", ("refusal-04",), "offline-test"
        )
        service.start_run(WORKSPACE, RUNNER, second["preflight_id"], "key-1")
    await service.process_run(WORKSPACE, run["run_id"])
    saved = service.read_run(WORKSPACE, READER, run["run_id"])
    assert saved["execution_status"] == "COMPLETED"
    assert set(saved["observations"]) == {"lexical-01", "refusal-04"}
    assert saved["report"]["retrieval"]["denominator"] == 0
    assert saved["report"]["quality_status"] == "SEMANTIC_PENDING"
    assert not await service.process_run(WORKSPACE, run["run_id"])


def test_stale_preflight_rejected():
    catalog = Milestone3Catalog(ROOT)
    service = EvaluationRunService(catalog, MemoryStore(), (profile(catalog, {}),))
    preflight = service.preflight(
        WORKSPACE, RUNNER, "m3-dataset-v1", ("lexical-01",), "offline-test"
    )
    service.invalidate_preflights()
    with pytest.raises(KnoraError, match="EVALUATION_PREFLIGHT_STALE"):
        service.start_run(WORKSPACE, RUNNER, preflight["preflight_id"], "key")


def test_ready_preflight_survives_service_recreation():
    catalog = Milestone3Catalog(ROOT)
    store = MemoryStore()
    runtime = profile(catalog, {})
    first = EvaluationRunService(catalog, store, (runtime,))
    preflight = first.preflight(WORKSPACE, RUNNER, "m3-dataset-v1", ("lexical-01",), "offline-test")
    second = EvaluationRunService(catalog, store, (runtime,))
    run = second.start_run(WORKSPACE, RUNNER, preflight["preflight_id"], "key-after-reload")
    assert run["selection"]["selected_case_ids"] == ["lexical-01"]


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["dataset", "profile_missing"])
async def test_queued_run_blocks_drift_before_any_question_dispatch(monkeypatch, drift):
    catalog = Milestone3Catalog(ROOT)
    store = MemoryStore()
    runtime = profile(catalog, {})

    async def forbidden_execute(case, environment):
        pytest.fail("Changed dataset or missing profile must never execute Q&A")

    runtime = replace(runtime, execute=forbidden_execute)
    service = EvaluationRunService(catalog, store, (runtime,))
    preflight = service.preflight(
        WORKSPACE, RUNNER, "m3-dataset-v1", ("lexical-01",), runtime.profile_id
    )
    run = service.start_run(WORKSPACE, RUNNER, preflight["preflight_id"], "drift-key")
    if drift == "dataset":
        entry = catalog.get_dataset(WORKSPACE, "m3-dataset-v1")
        changed = replace(
            entry, reference=replace(entry.reference, native_digest="sha256:" + "0" * 64)
        )
        monkeypatch.setattr(catalog, "get_dataset", lambda *args: changed)
    else:
        service = EvaluationRunService(catalog, store, ())
    await service.process_run(WORKSPACE, run["run_id"])
    saved = service.read_run(WORKSPACE, READER, run["run_id"])
    assert saved["execution_status"] == "BLOCKED"
    assert saved["observations"] == {"lexical-01": {"status": "NOT_RUN"}}


def test_preflight_cannot_start_after_profile_becomes_live():
    catalog = Milestone3Catalog(ROOT)
    store = MemoryStore()
    runtime = profile(catalog, {})
    first = EvaluationRunService(catalog, store, (runtime,))
    preflight = first.preflight(
        WORKSPACE, RUNNER, "m3-dataset-v1", ("lexical-01",), runtime.profile_id
    )

    def forbidden_prepare():
        pytest.fail("A live profile must be blocked before preparation")

    second = EvaluationRunService(
        catalog, store, (replace(runtime, kind="live", prepare=forbidden_prepare),)
    )
    with pytest.raises(KnoraError, match="EVALUATION_PREFLIGHT_STALE"):
        second.start_run(WORKSPACE, RUNNER, preflight["preflight_id"], "live-drift-key")
    assert store.list(WORKSPACE) == []


@pytest.mark.asyncio
async def test_offline_run_uses_production_executor_and_exact_trace():
    catalog = Milestone3Catalog(ROOT)
    binding, corpus = profile(catalog, {}).prepare()
    posts = []
    trace_reads = []

    def handle(request):
        posts.append(request)
        return httpx.Response(
            200,
            json={
                "decision": "REFUSAL",
                "answer": None,
                "citations": [],
                "refusal_reason": "INSUFFICIENT_EVIDENCE",
                "trace_id": "trace-refusal-1",
            },
        )

    def read_trace(**kwargs):
        trace_reads.append(kwargs)
        return SimpleNamespace(
            trace_id="trace-refusal-1",
            workspace_id=WORKSPACE,
            retrieval_configuration_id=binding.retrieval_configuration_id,
            embedding_configuration_id=binding.embedding_configuration_id,
            decision="REFUSAL",
            answer=None,
            refusal_reason="INSUFFICIENT_EVIDENCE",
            parsed_markers=[],
            candidates=(),
            retrieval_latency_ms=1.0,
            alias_mapping={},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        runtime = production_http_profile(
            profile_id="offline-http",
            kind="offline",
            endpoint="http://production.test/v1/questions",
            api_key="test-key",
            trace_reader=SimpleNamespace(read_trace=read_trace),
            client=client,
            prepare=lambda: (binding, corpus),
        )
        service = EvaluationRunService(catalog, MemoryStore(), (runtime,))
        preflight = service.preflight(
            WORKSPACE, RUNNER, "m3-dataset-v1", ("refusal-04",), "offline-http"
        )
        run = service.start_run(
            WORKSPACE, RUNNER, preflight["preflight_id"], "key-production-executor"
        )
        await service.process_run(WORKSPACE, run["run_id"])
        saved = service.read_run(WORKSPACE, READER, run["run_id"])
    assert len(posts) == 1
    assert posts[0].url.path == "/v1/questions"
    assert trace_reads == [{"trace_id": "trace-refusal-1", "workspace_id": WORKSPACE}]
    assert saved["observations"]["refusal-04"]["trace_id"] == "trace-refusal-1"
    assert saved["report"]["cases"][0]["refusal_correctness"] is True


def test_live_http_profile_is_blocked_before_dispatch():
    catalog = Milestone3Catalog(ROOT)
    binding, corpus = profile(catalog, {}).prepare()

    async def no_dispatch(_request):
        pytest.fail("live profile must not dispatch")

    runtime = production_http_profile(
        profile_id="live-owned",
        kind="live",
        endpoint="http://production.test/v1/questions",
        api_key="test-key",
        trace_reader=object(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(no_dispatch)),
        prepare=lambda: (binding, corpus),
    )
    service = EvaluationRunService(catalog, MemoryStore(), (runtime,))
    preflight = service.preflight(WORKSPACE, RUNNER, "m3-dataset-v1", ("refusal-04",), "live-owned")
    assert preflight["status"] == "BLOCKED"
    with pytest.raises(KnoraError, match="EVALUATION_PREFLIGHT_STALE"):
        service.start_run(WORKSPACE, RUNNER, preflight["preflight_id"], "key-live")
