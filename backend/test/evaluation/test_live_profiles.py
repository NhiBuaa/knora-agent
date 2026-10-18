"""The same exact authority is checked at preflight, admission and dispatch."""

from copy import deepcopy
from dataclasses import asdict, replace

import httpx
import pytest
from backend.test.evaluation.test_gold_review import builder  # noqa: F401
from test_live_admission import ENDPOINT, NOW, approval, body, success
from test_pdf_proposals import OWNER as BUILDER_OWNER  # noqa: F401
from test_pdf_proposals import packet, prepared_builder
from test_runs import ROOT, RUNNER, WORKSPACE, MemoryStore, profile
from test_scoring import saved, scorer  # noqa: F401

from knora.domain.errors import KnoraError
from knora.evaluation.catalog import Milestone3Catalog
from knora.evaluation.live_admission import LiveAdmission, live_scope
from knora.evaluation.runs import EvaluationRunService


def authority(tmp_path, scope):
    return LiveAdmission(
        {**approval(), "scope": scope}, tmp_path / "live.sqlite", clock=lambda: NOW
    )


@pytest.mark.asyncio
async def test_http_factories_require_the_admission_created_provider_client(tmp_path):
    from types import SimpleNamespace

    from knora.evaluation.pdf_runtime import pdf_http_profile
    from knora.evaluation.runs import production_http_profile

    admission = authority(tmp_path, live_scope("qa", "factory", WORKSPACE, {"input": "x"}))
    plain = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: success(None)))
    with pytest.raises(ValueError, match="LIVE_PROVIDER_CLIENT_REQUIRED"):
        production_http_profile(
            profile_id="factory",
            kind="live",
            endpoint=ENDPOINT,
            api_key="secret",
            trace_reader=SimpleNamespace(),
            client=plain,
            prepare=lambda: (None, None),
            admission=admission,
        )
    await plain.aclose()
    guarded = admission.async_client(mock=httpx.MockTransport(lambda _: success(None)))
    runtime = production_http_profile(
        profile_id="factory",
        kind="live",
        endpoint=ENDPOINT,
        api_key="secret",
        trace_reader=SimpleNamespace(),
        client=guarded,
        prepare=lambda: (None, None),
        admission=admission,
    )
    assert runtime.provider_client is guarded
    await guarded.aclose()
    with pytest.raises(ValueError, match="LIVE_PROVIDER_CLIENT_REQUIRED"):
        pdf_http_profile(
            profile_id="factory-pdf",
            kind="live",
            endpoint=ENDPOINT,
            api_key="secret",
            trace_reader=SimpleNamespace(),
            client=plain,
            prepare=lambda _: {},
            admission=admission,
        )


def native(tmp_path):
    from evals.runners.milestone_3 import M3Observation

    catalog = Milestone3Catalog(ROOT)
    base = profile(catalog, {})
    entry = catalog.get_dataset(WORKSPACE, "m3-dataset-v1")
    selection = dict(
        reference=asdict(entry.reference),
        selected_case_ids=["lexical-01"],
        context_only_case_ids=[],
    )
    scope = live_scope(
        "qa", "live-test", WORKSPACE, dict(selection=selection, binding=asdict(base.prepare()[0]))
    )
    admission = authority(tmp_path, scope)
    sent = []
    client = admission.async_client(
        mock=httpx.MockTransport(lambda r: (sent.append(r), success(r))[1])
    )

    async def execute(case, environment):
        await client.post(ENDPOINT, json=body())
        return M3Observation.failure(case.id, "EVALUATION_OBSERVATION_FAILURE")

    live = replace(
        base,
        profile_id="live-test",
        kind="live",
        execute=execute,
        admission=admission,
        provider_client=client,
    )
    store = MemoryStore()
    return EvaluationRunService(catalog, store, (live,)), store, admission, sent, client


@pytest.mark.asyncio
async def test_native_live_authority_is_saved_and_survives_worker_restart(tmp_path):
    service, store, admission, sent, client = native(tmp_path)
    async with client:
        preflight = service.preflight(
            WORKSPACE, RUNNER, "m3-dataset-v1", ("lexical-01",), "live-test"
        )
        assert preflight["status"] == "READY"
        assert admission.snapshot()["attempts"] == 0
        run = service.start_run(WORKSPACE, RUNNER, preflight["preflight_id"], "once")
        provenance = deepcopy(run["binding"]["live_admission"])
        assert provenance["provenance"]["approval_id"] == "owner-decision-1"
        restarted = EvaluationRunService(service._catalog, store, tuple(service._profiles.values()))
        await restarted.process_run(WORKSPACE, run["run_id"])
        result = store.get(WORKSPACE, run["run_id"])
        assert result["execution_status"] == "COMPLETED"
        assert result["report"]["binding"]["live_admission"] == provenance
        assert len(sent) == admission.snapshot()["attempts"] == 1


@pytest.mark.parametrize("stage", ["admission", "worker"])
@pytest.mark.asyncio
async def test_stop_after_preflight_blocks_admission_or_dispatch(tmp_path, stage):
    service, store, admission, sent, client = native(tmp_path)
    async with client:
        preflight = service.preflight(
            WORKSPACE, RUNNER, "m3-dataset-v1", ("lexical-01",), "live-test"
        )
        assert preflight["status"] == "READY"
        if stage == "admission":
            admission.stop()
            with pytest.raises(KnoraError, match="EVALUATION_PREFLIGHT_STALE"):
                service.start_run(WORKSPACE, RUNNER, preflight["preflight_id"], "once")
            assert not store.runs
        else:
            run = service.start_run(WORKSPACE, RUNNER, preflight["preflight_id"], "once")
            admission.stop()
            await service.process_run(WORKSPACE, run["run_id"])
            assert run["execution_status"] == "BLOCKED"
        assert sent == [] and admission.snapshot()["attempts"] == 0


@pytest.mark.asyncio
async def test_saved_answer_scoring_checks_live_scope_and_keeps_provenance(tmp_path, saved):  # noqa: F811
    service, captures, run, owner = scorer(saved)
    base = service._profiles["fixture"]
    live = replace(base, kind="live")
    service._profiles["fixture"] = live
    payload, _ = service._input(owner.workspace_id, owner, run["run_id"], ("answer",), "fixture")
    admission = authority(tmp_path, live_scope("scoring", "fixture", owner.workspace_id, payload))
    client = admission.sync_client(mock=httpx.MockTransport(success))

    def measure(capture):
        client.post(ENDPOINT, json=body())
        return base.measure(capture)

    service._profiles["fixture"] = replace(
        live, measure=measure, admission=admission, provider_client=client
    )
    ready = service.preflight(owner.workspace_id, owner, run["run_id"], ("answer",), "fixture")
    assert ready["status"] == "READY"
    batch = await service.score(
        owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "once"
    )
    assert batch["status"] == "COMPLETED"
    assert batch["scorer"]["live_admission"]["provenance"]["approval_id"] == "owner-decision-1"
    assert len(captures) == admission.snapshot()["attempts"] == 1
    assert run["report"]["report_kind"] == "deterministic_partial_pdf"
    assert (
        await service.score(owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "once")
        == batch
    )
    assert admission.snapshot()["attempts"] == 1
    client.close()


@pytest.mark.asyncio
async def test_pdf_live_binding_provenance_roundtrips_through_sqlite_run_store(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from test_pdf_runs import OWNER, GoldReader, binding_for, frozen_dataset

    from knora.adapters.postgres.evaluation_runs import PostgresEvaluationRunStore
    from knora.adapters.postgres.evaluation_runs_tables import (
        EvaluationPreflightTable,
        EvaluationRunTable,
    )
    from knora.evaluation.contracts import select_cases
    from knora.evaluation.pdf_runtime import PdfRuntimeProfile

    frozen = frozen_dataset()
    binding = binding_for(frozen)
    selection = select_cases(frozen, ("answer",))
    import json

    scope = live_scope(
        "qa",
        "live-pdf",
        OWNER.workspace_id,
        dict(selection=json.loads(selection.to_json()), binding=binding),
    )
    admission = authority(tmp_path, scope)
    sent = []
    client = admission.async_client(
        mock=httpx.MockTransport(lambda r: (sent.append(r), success(r))[1])
    )

    async def execute(case, binding):
        assert "live_admission" not in binding
        await client.post(ENDPOINT, json=body())
        return {"case_id": case.case_id, "status": "FAILED", "failure_code": "OFFLINE_TEST"}

    engine = create_engine("sqlite://")
    EvaluationRunTable.__table__.create(engine)
    EvaluationPreflightTable.__table__.create(engine)
    store = PostgresEvaluationRunStore(sessionmaker(engine, expire_on_commit=False))
    profiles = (
        PdfRuntimeProfile(
            "live-pdf", "live", lambda _: deepcopy(binding), execute, admission, client
        ),
    )
    service = EvaluationRunService(
        Milestone3Catalog(ROOT), store, (), datasets=GoldReader(frozen), pdf_profiles=profiles
    )
    ready = service.preflight(
        OWNER.workspace_id,
        OWNER,
        frozen.reference.dataset_id,
        ("answer",),
        "live-pdf",
        asdict(frozen.reference),
    )
    assert ready["status"] == "READY"
    run = service.start_run(OWNER.workspace_id, OWNER, ready["preflight_id"], "once")
    assert run["binding"]["live_admission"]["scope"] == scope
    await service.process_run(OWNER.workspace_id, run["run_id"])
    read = service.read_run(OWNER.workspace_id, OWNER, run["run_id"])
    assert read["execution_status"] == "COMPLETED"
    assert read["report"]["binding"]["live_admission"] == run["binding"]["live_admission"]
    assert len(sent) == admission.snapshot()["attempts"] == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_proposals_live_approval_preserves_unreviewed_drafts_and_never_replays(
    tmp_path,
    builder,  # noqa: F811
):
    from knora.evaluation.proposals import ProposalProfile

    service, dataset_id, source = prepared_builder(builder)

    admission = None
    client = None

    async def generate(chunks, identity, language, count):
        await client.post(ENDPOINT, json=body())
        return packet(chunks, identity)

    profile = ProposalProfile("live-ragas", "live", "offline-fixture", "v1", generate)
    service._proposal_profiles = {profile.profile_id: profile}
    blocked = service.proposal_preflight(
        "w1", dataset_id, (source.id,), profile.profile_id, "vi", 1, BUILDER_OWNER
    )
    assert blocked["status"] == "BLOCKED"
    scope = live_scope("proposals", profile.profile_id, "w1", blocked["input"])
    admission = authority(tmp_path, scope)
    client = admission.async_client(mock=httpx.MockTransport(success))
    service._proposal_profiles[profile.profile_id] = replace(
        profile, admission=admission, provider_client=client
    )
    ready = service.proposal_preflight(
        "w1", dataset_id, (source.id,), profile.profile_id, "vi", 1, BUILDER_OWNER
    )
    assert ready["status"] == "READY"
    args = (
        "w1",
        dataset_id,
        (source.id,),
        profile.profile_id,
        "vi",
        1,
        ready["expected_revision"],
        ready["input_digest"],
        "once",
        BUILDER_OWNER,
    )
    batch = await service.generate_proposals(*args)
    assert batch["status"] == "COMPLETED"
    assert batch["input"]["live_admission"]["scope"] == scope
    assert service.get_dataset("w1", dataset_id, BUILDER_OWNER).reviews == ()
    assert service.get_dataset("w1", dataset_id, BUILDER_OWNER).cases == ()
    admission.stop()
    assert await service.generate_proposals(*args) == batch
    assert admission.snapshot()["attempts"] == 1
    changed = service.proposal_preflight(
        "w1", dataset_id, (source.id,), profile.profile_id, "en", 1, BUILDER_OWNER
    )
    assert changed["status"] == "BLOCKED"
    await client.aclose()
