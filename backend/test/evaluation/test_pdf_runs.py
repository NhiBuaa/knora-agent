from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_runs import MemoryStore

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.evaluation.catalog import Milestone3Catalog
from knora.evaluation.contracts import (
    Case,
    DatasetIdentity,
    EvidenceAnchor,
    EvidenceGroup,
    FreezeApproval,
    GoldDataset,
    NoAnswerScope,
    PdfSource,
    digest_json,
    freeze_dataset,
)
from knora.evaluation.pdf_runtime import PdfRuntimeProfile, validate_pdf_binding
from knora.evaluation.runs import EvaluationRunService

WORKSPACE = "pdf-workspace"
OWNER = WorkspacePrincipal(
    WORKSPACE, "owner", ("operator:read", "evaluations:run", "questions:ask")
)
ROOT = Path(__file__).resolve().parents[3]


def frozen_dataset():
    anchor = EvidenceAnchor("version-1", 1, "The sky is blue.")
    gold = GoldDataset(
        DatasetIdentity("pdf-set", 1, WORKSPACE, "pdf-gold-v1", "pdf-metrics-v1"),
        (PdfSource("document-1", "version-1", "a" * 64),),
        (
            Case(
                "answer",
                "What color is the sky?",
                "ANSWER",
                "Blue",
                ("Blue",),
                "en",
                "single-hop",
                (EvidenceGroup((anchor,)),),
            ),
            Case(
                "refusal",
                "Who discovered it?",
                "REFUSAL",
                None,
                (),
                "en",
                "no-answer",
                (),
                no_answer_scope=NoAnswerScope(("version-1",), "Verified in original PDF"),
            ),
        ),
    )
    return freeze_dataset(gold, FreezeApproval("issuer", "owner", gold.digest))


def binding_for(frozen):
    anchor = frozen.gold.cases[0].evidence_groups[0].alternatives[0]
    binding = {
        "schema_version": 1,
        "binding_id": "pdf-binding-1",
        "reference": asdict(frozen.reference),
        "retrieval_configuration_id": "retrieval-test",
        "embedding_configuration_id": "embedding-test",
        "generation_configuration_id": "generation-test",
        "generation": {"provider": "offline", "model": "fixture", "prompt_version": "prompt-1"},
        "candidate_budget": 200,
        "sources": {
            "version-1": {
                "raw_sha256": "a" * 64,
                "status": "READY",
                "chunk_set_id": "set-1",
                "embedding_set_id": "embedding-set-1",
                "chunk_ids": ["chunk-1"],
            }
        },
        "anchors": {digest_json(asdict(anchor)): {"status": "READY", "chunk_ids": ["chunk-1"]}},
    }
    binding["approval"] = {
        "owner_issuer": "issuer",
        "owner_subject": "owner",
        "binding_digest": digest_json(binding),
    }
    return binding


class GoldReader:
    def __init__(self, frozen):
        self.frozen = frozen

    def get_frozen_dataset(self, workspace_id, dataset_id, principal, version=None):
        if (
            workspace_id != WORKSPACE
            or dataset_id != self.frozen.reference.dataset_id
            or version != self.frozen.reference.version
        ):
            raise KnoraError("DATASET_NOT_FOUND")
        return self.frozen

    def list_sources(self, workspace_id, dataset_id, principal):
        return (
            SimpleNamespace(
                id="source-1",
                document_version_id="version-1",
                raw_sha256="a" * 64,
                status="FAILED",
                failure_code="PDF_NO_TEXT",
                snapshot_id=None,
            ),
        )


def setup_run(*, kind="offline", execute=None):
    frozen = frozen_dataset()
    binding = binding_for(frozen)
    calls = []

    async def observe(case, snapshot):
        calls.append(case.case_id)
        return {
            "case_id": case.case_id,
            "status": "OBSERVED",
            "trace_id": "trace-" + case.case_id,
            "decision": case.expected,
            "candidate_chunk_ids": ["chunk-1"],
            "generation_chunk_ids": ["chunk-1"],
            "public_answer": "Blue [E1]" if case.expected == "ANSWER" else None,
            "citation_correctness": True,
        }

    profile = PdfRuntimeProfile(
        "pdf-offline", kind, lambda _: deepcopy(binding), execute or observe
    )
    store = MemoryStore()
    reader = GoldReader(frozen)
    service = EvaluationRunService(
        Milestone3Catalog(ROOT), store, (), datasets=reader, pdf_profiles=(profile,)
    )
    return service, store, reader, binding, calls


def preflight(service, frozen, selected=("answer", "refusal")):
    return service.preflight(
        WORKSPACE, OWNER, "pdf-set", selected, "pdf-offline", asdict(frozen.reference)
    )


@pytest.mark.asyncio
async def test_pdf_selection_runs_new_qa_and_saves_canonical_report_without_deepeval():
    service, store, reader, binding, calls = setup_run()
    original = reader.frozen.to_json()
    ready = preflight(service, reader.frozen)
    assert ready["status"] == "READY"
    assert ready["dataset_reference"] == asdict(reader.frozen.reference)
    run = service.start_run(WORKSPACE, OWNER, ready["preflight_id"], "key")
    assert (
        service.start_run(WORKSPACE, OWNER, ready["preflight_id"], "key")["run_id"] == run["run_id"]
    )
    assert await service.process_run(WORKSPACE, run["run_id"])
    assert calls == ["answer", "refusal"]
    assert run["execution_status"] == "COMPLETED"
    assert run["report"]["retrieval"]["value"] == 1.0
    assert run["report"]["population"] == {
        "dataset": 2,
        "selected": 2,
        "context_only": 0,
        "attempted": 2,
        "observed": 2,
        "applicable": 1,
        "evaluable": 1,
    }
    assert run["report"]["dataset"] == asdict(reader.frozen.reference)
    assert run["report"]["binding_digest"] == binding["approval"]["binding_digest"]
    assert run["report"]["quality_status"] == "SEMANTIC_PENDING"
    assert run["report"]["source_preparation"][0]["status"] == "FAILED"
    assert reader.frozen.to_json() == original
    assert not await service.process_run(WORKSPACE, run["run_id"])


@pytest.mark.parametrize("change", ["digest", "workspace", "version"])
def test_pdf_preflight_rejects_wrong_exact_reference(change):
    service, _, reader, _, calls = setup_run()
    reference = asdict(reader.frozen.reference)
    reference[change if change != "workspace" else "workspace_id"] = {
        "digest": "0" * 64,
        "workspace": "other",
        "version": 2,
    }[change]
    with pytest.raises(KnoraError):
        service.preflight(WORKSPACE, OWNER, "pdf-set", ("answer",), "pdf-offline", reference)
    assert calls == []


def test_live_pdf_profile_never_prepares_or_dispatches():
    service, _, reader, _, calls = setup_run(kind="live")
    ready = preflight(service, reader.frozen)
    assert ready["status"] == "BLOCKED"
    assert "PROVIDER_APPROVAL_REQUIRED" in ready["reasons"]
    assert calls == []


def test_missing_retained_source_stays_visible_in_preflight(monkeypatch):
    service, _, reader, _, _ = setup_run()
    monkeypatch.setattr(reader, "list_sources", lambda *_: ())
    ready = preflight(service, reader.frozen)
    assert ready["source_preparation"][0]["document_version_id"] == "version-1"
    assert ready["source_preparation"][0]["status"] == "MISSING"


@pytest.mark.asyncio
async def test_unavailable_source_is_recorded_without_dispatch_or_population_loss():
    service, _, reader, binding, calls = setup_run()
    binding["sources"]["version-1"].update(
        status="FAILED", chunk_ids=[], chunk_set_id=None, embedding_set_id=None
    )
    binding["anchors"][next(iter(binding["anchors"]))] = {"status": "MISSING", "chunk_ids": []}
    binding["approval"]["binding_digest"] = digest_json(
        {k: v for k, v in binding.items() if k != "approval"}
    )
    ready = preflight(service, reader.frozen)
    assert all(case["status"] == "BLOCKED" for case in ready["case_readiness"])
    run = service.start_run(WORKSPACE, OWNER, ready["preflight_id"], "failed-source")
    await service.process_run(WORKSPACE, run["run_id"])
    assert calls == []
    assert {v["status"] for v in run["observations"].values()} == {"BLOCKED"}
    assert run["report"]["population"]["selected"] == 2
    assert run["report"]["retrieval"]["applicable_denominator"] == 1
    assert run["report"]["retrieval"]["value"] is None


@pytest.mark.asyncio
async def test_ambiguous_dispatch_keeps_partial_capture_and_never_replays():
    calls = []

    async def fail_second(case, _):
        calls.append(case.case_id)
        if case.case_id == "refusal":
            raise TimeoutError("uncertain provider outcome")
        return {
            "case_id": "answer",
            "status": "OBSERVED",
            "decision": "ANSWER",
            "trace_id": "trace-1",
            "candidate_chunk_ids": [],
            "generation_chunk_ids": [],
        }

    service, _, reader, _, _ = setup_run(execute=fail_second)
    ready = preflight(service, reader.frozen)
    run = service.start_run(WORKSPACE, OWNER, ready["preflight_id"], "timeout")
    await service.process_run(WORKSPACE, run["run_id"])
    assert run["execution_status"] == "INDETERMINATE"
    assert run["observations"]["refusal"]["status"] == "INDETERMINATE"
    assert run["report"]["population"]["attempted"] == 2
    assert run["report"]["population"]["observed"] == 1
    assert not await service.process_run(WORKSPACE, run["run_id"])
    assert calls == ["answer", "refusal"]


def test_binding_drift_after_preflight_cannot_start():
    service, _, reader, binding, calls = setup_run()
    ready = preflight(service, reader.frozen)
    binding["generation_configuration_id"] = "changed"
    with pytest.raises(KnoraError, match="EVALUATION_PREFLIGHT_STALE"):
        service.start_run(WORKSPACE, OWNER, ready["preflight_id"], "drift")
    assert calls == []


@pytest.mark.asyncio
async def test_binding_drift_after_queue_retains_gold_and_blocked_report():
    service, _, reader, binding, calls = setup_run()
    ready = preflight(service, reader.frozen)
    run = service.start_run(WORKSPACE, OWNER, ready["preflight_id"], "queued-drift")
    binding["generation_configuration_id"] = "changed"
    await service.process_run(WORKSPACE, run["run_id"])
    assert run["execution_status"] == "BLOCKED"
    assert run["report"]["population"]["selected"] == 2
    assert run["report"]["population"]["attempted"] == 0
    assert all(case["status"] == "BLOCKED" for case in run["report"]["cases"])
    assert calls == []


@pytest.mark.asyncio
async def test_pdf_run_round_trips_existing_sql_run_store():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from knora.adapters.postgres.evaluation_runs import PostgresEvaluationRunStore
    from knora.adapters.postgres.evaluation_runs_tables import (
        EvaluationPreflightTable,
        EvaluationRunTable,
    )

    service, _, reader, _, calls = setup_run()
    engine = create_engine("sqlite://")
    EvaluationRunTable.__table__.create(engine)
    EvaluationPreflightTable.__table__.create(engine)
    store = PostgresEvaluationRunStore(sessionmaker(bind=engine, expire_on_commit=False))
    service._store = store
    ready = preflight(service, reader.frozen)
    run = service.start_run(WORKSPACE, OWNER, ready["preflight_id"], "sql-key")
    # Re-read as a restarted worker would; JSON tuples/lists and source snapshots must survive.
    assert (
        store.get(WORKSPACE, run["run_id"])["report"]["source_preparation"][0]["source_id"]
        == "source-1"
    )
    await service.process_run(WORKSPACE, run["run_id"])
    saved = store.get(WORKSPACE, run["run_id"])
    assert saved["execution_status"] == "COMPLETED"
    assert saved["quality_status"] == "SEMANTIC_PENDING"
    assert saved["report"]["retrieval"]["value"] == 1.0
    assert calls == ["answer", "refusal"]


@pytest.mark.parametrize(
    "mutation", ["unreviewed", "wrong_source", "foreign_chunk", "wrong_reference"]
)
def test_binding_validation_rejects_untrusted_or_inconsistent_mapping(mutation):
    frozen = frozen_dataset()
    binding = binding_for(frozen)
    if mutation == "unreviewed":
        binding["approval"]["owner_subject"] = ""
    elif mutation == "wrong_source":
        binding["sources"]["version-1"]["raw_sha256"] = "b" * 64
    elif mutation == "foreign_chunk":
        binding["anchors"][next(iter(binding["anchors"]))]["chunk_ids"] = ["foreign"]
    else:
        binding["reference"]["dataset_id"] = "wrong"
    binding["approval"]["binding_digest"] = digest_json(
        {k: v for k, v in binding.items() if k != "approval"}
    )
    with pytest.raises(ValueError):
        validate_pdf_binding(frozen, binding)


def test_follow_up_is_explicit_readiness_blocker_and_context_not_metric_population():
    service, _, reader, binding, _ = setup_run()
    gold = replace(
        reader.frozen.gold,
        cases=(
            reader.frozen.gold.cases[0],
            replace(reader.frozen.gold.cases[1], context_dependencies=("answer",)),
        ),
    )
    reader.frozen = freeze_dataset(gold, FreezeApproval("issuer", "owner", gold.digest))
    binding["reference"] = asdict(reader.frozen.reference)
    binding["approval"]["binding_digest"] = digest_json(
        {k: v for k, v in binding.items() if k != "approval"}
    )
    ready = preflight(service, reader.frozen, ("refusal",))
    assert ready["status"] == "BLOCKED"
    assert "CONTEXT_EXECUTION_UNSUPPORTED" in ready["reasons"]
    assert ready["context_only_case_ids"] == ["answer"]
