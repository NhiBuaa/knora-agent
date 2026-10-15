from copy import deepcopy
from dataclasses import asdict, replace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from test_pdf_runs import GoldReader, frozen_dataset
from test_runs import ROOT

from knora.adapters.postgres.evaluation_runs import PostgresEvaluationRunStore
from knora.adapters.postgres.evaluation_runs_tables import (
    EvaluationPreflightTable,
    EvaluationRunTable,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.evaluation.catalog import Milestone3Catalog
from knora.evaluation.contracts import digest_json
from knora.evaluation.runs import EvaluationRunService


@pytest.fixture
def saved():
    frozen = frozen_dataset()
    workspace = frozen.reference.workspace_id
    owner = WorkspacePrincipal(
        workspace, "owner", ("operator:read", "documents:read", "evaluations:run")
    )
    engine = create_engine("sqlite://")
    EvaluationRunTable.__table__.create(engine)
    EvaluationPreflightTable.__table__.create(engine)
    store = PostgresEvaluationRunStore(sessionmaker(engine, expire_on_commit=False))
    selection = {
        "reference": asdict(frozen.reference),
        "selected_case_ids": ["answer", "refusal"],
        "context_only_case_ids": [],
    }
    run = {
        "run_id": "saved-run",
        "workspace_id": workspace,
        "request_digest": "a" * 64,
        "selection": selection,
        "selection_digest": digest_json(selection),
        "profile_id": "not-registered",
        "binding": {"binding_id": "saved-binding"},
        "execution_status": "COMPLETED",
        "quality_status": "SEMANTIC_PENDING",
        "observations": {
            "answer": {
                "case_id": "answer",
                "status": "OBSERVED",
                "trace_id": "trace-answer",
                "decision": "ANSWER",
                "public_answer": "Blue [E1]",
                "generation_evidence": [["E1", "The sky is blue."]],
            },
            "refusal": {
                "case_id": "refusal",
                "status": "OBSERVED",
                "trace_id": "trace-refusal",
                "decision": "REFUSAL",
                "public_answer": None,
            },
        },
        "report": {
            "report_kind": "deterministic_partial_pdf",
            "quality_status": "SEMANTIC_PENDING",
            "retrieval": {"value": 1.0},
        },
    }
    store.create(run, "source")
    runs = EvaluationRunService(Milestone3Catalog(ROOT), store, (), datasets=GoldReader(frozen))
    return runs, store, run, owner


def scorer(saved, score=None, kind="offline"):
    from knora.evaluation.scoring import EvaluationScoringService, ScoringProfile

    runs, store, run, owner = saved
    captures = []

    def measure(capture):
        from evals.scorers.deepeval_cloudflare import _scoring_input_sha256

        captures.append(deepcopy(capture))
        return {
            "run_id": capture["run_id"],
            "case_id": capture["case_id"],
            "trace_id": capture["trace_id"],
            "attempt": 1,
            "input_sha256": _scoring_input_sha256(capture),
            "tool": "deepeval-4.2.8",
            "model": "offline-fixture",
            "method": "direct-measure-v1",
            "metrics": {
                name: {"status": "scored", "score": 0.8, "rationale": "Fixture judgment"}
                for name in ("correctness", "answer_relevancy", "faithfulness")
            },
            "http_attempts": 0,
        }

    service = EvaluationScoringService(
        runs,
        store,
        (
            ScoringProfile(
                "fixture", kind, "offline-fixture", "direct-measure-v1", {}, score or measure
            ),
        ),
    )
    return service, captures, run, owner


@pytest.mark.asyncio
async def test_scores_exact_saved_pdf_answer_without_registered_qa_runtime_or_report_changes(saved):
    service, captures, run, owner = scorer(saved)
    before = deepcopy(run)
    ready = service.preflight(
        owner.workspace_id, owner, run["run_id"], ("answer", "refusal"), "fixture"
    )
    assert ready["status"] == "READY"
    assert ready["cases"][1]["reason"] == "REFUSAL_USES_DETERMINISTIC_CHECKS"
    batch = await service.score(
        owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "request-1"
    )
    assert batch["status"] == "COMPLETED"
    assert batch["quality_status"] == "UNCALIBRATED"
    assert batch["release_gate"] is False
    assert captures[0]["question"] == "What color is the sky?"
    assert captures[0]["reference_answer"] == "Blue"
    assert captures[0]["answer"] == "Blue [E1]"
    assert captures[0]["generation_evidence"] == [{"alias": "E1", "content": "The sky is blue."}]
    assert list(batch["results"]) == ["answer", "refusal"]
    assert batch["results"]["refusal"]["metrics"]["correctness"]["status"] == "not_applicable"
    assert len(captures) == 1
    again = await service.score(
        owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "request-1"
    )
    assert again == batch
    assert len(captures) == 1
    current = saved[1].get(owner.workspace_id, run["run_id"])
    assert current["report"] == before["report"]
    assert current["observations"] == before["observations"]
    assert current["quality_status"] == "SEMANTIC_PENDING"
    assert len(service.read(owner.workspace_id, owner, run["run_id"])["batches"]) == 1


@pytest.mark.asyncio
async def test_uncertain_judge_is_checkpointed_and_not_replayed(saved):
    calls = []

    def fail(capture):
        calls.append(capture)
        raise TimeoutError("private contents must not enter error diagnostics")

    service, _, run, owner = scorer(saved, fail)
    ready = service.preflight(owner.workspace_id, owner, run["run_id"], ("answer",), "fixture")
    result = await service.score(
        owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "uncertain"
    )
    assert result["status"] == "INDETERMINATE"
    assert result["results"]["answer"]["reason"] == "JUDGE_RESULT_UNAVAILABLE"
    assert "private contents" not in str(result)
    assert (
        await service.score(
            owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "uncertain"
        )
        == result
    )
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_cancelled_judge_recovers_dispatched_case_as_uncertain_without_replay(saved):
    import asyncio

    calls = []

    def cancel(capture):
        calls.append(capture["case_id"])
        raise asyncio.CancelledError

    service, _, run, owner = scorer(saved, cancel)
    ready = service.preflight(
        owner.workspace_id, owner, run["run_id"], ("answer", "refusal"), "fixture"
    )
    with pytest.raises(asyncio.CancelledError):
        await service.score(
            owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "cancelled"
        )
    recovered = await service.score(
        owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "cancelled"
    )
    assert recovered["status"] == "INDETERMINATE"
    assert recovered["results"]["answer"]["status"] == "INDETERMINATE"
    assert recovered["results"]["answer"]["reason"] == "JUDGE_RESULT_UNAVAILABLE"
    assert recovered["results"]["answer"]["metrics"]["correctness"]["status"] == "indeterminate"
    assert recovered["results"]["refusal"]["status"] == "NOT_APPLICABLE"
    assert calls == ["answer"]


@pytest.mark.asyncio
async def test_stale_capture_or_profile_and_live_profiles_never_dispatch(saved):
    service, captures, run, owner = scorer(saved)
    ready = service.preflight(owner.workspace_id, owner, run["run_id"], ("answer",), "fixture")
    from knora.evaluation.scoring import EvaluationScoringService

    changed = EvaluationScoringService(saved[0], saved[1], ())
    with pytest.raises(KnoraError, match="EVALUATION_SCORING_NOT_READY"):
        await changed.score(
            owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "changed"
        )
    live, _, _, _ = scorer(saved, kind="live")
    assert live.preflight(owner.workspace_id, owner, run["run_id"], ("answer",), "fixture")[
        "reasons"
    ] == ["JUDGE_APPROVAL_REQUIRED"]
    with pytest.raises(KnoraError, match="EVALUATION_SCORING_NOT_READY"):
        await live.score(owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "live")
    assert captures == []


def test_read_only_and_wrong_workspace_are_denied_before_lookup(saved):
    service, _, run, owner = scorer(saved)
    reader = WorkspacePrincipal(owner.workspace_id, "reader", ("operator:read",))
    with pytest.raises(KnoraError, match="CAPABILITY_ACCESS_DENIED"):
        service.preflight(owner.workspace_id, reader, "missing", ("answer",), "fixture")
    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        service.read("other", owner, run["run_id"])


def test_missing_trace_and_unsupported_observations_stay_in_population(saved):
    from knora.evaluation.scoring import capture_saved_cases

    runs, _, run, owner = saved
    run["observations"]["answer"]["trace_id"] = None
    cases = capture_saved_cases(runs, run, owner, ("answer", "refusal"))
    assert [case["case_id"] for case in cases] == ["answer", "refusal"]
    assert cases[0]["reason"] == "CAPTURE_TRACE_UNAVAILABLE"
    assert cases[1]["status"] == "NOT_APPLICABLE"


def test_legacy_pdf153_is_not_assumed_compatible_with_builder_or_m3_mapping(saved):
    from knora.evaluation.scoring import capture_saved_cases

    runs, _, run, owner = saved
    run["selection"]["reference"]["format"] = "pdf-retrieval-v3"
    run["selection_digest"] = digest_json(run["selection"])
    result = capture_saved_cases(runs, run, owner, ("answer", "refusal"))
    assert [item["reason"] for item in result] == [
        "UNSUPPORTED_DATASET_MAPPING",
        "UNSUPPORTED_DATASET_MAPPING",
    ]


@pytest.mark.asyncio
async def test_new_scoring_request_appends_without_overwriting_previous_judgment(saved):
    service, captures, run, owner = scorer(saved)
    ready = service.preflight(owner.workspace_id, owner, run["run_id"], ("answer",), "fixture")
    first = await service.score(
        owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "first"
    )
    second = await service.score(
        owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "second"
    )
    assert first["id"] != second["id"]
    assert service.read(owner.workspace_id, owner, run["run_id"])["batches"] == [first, second]
    assert len(captures) == 2


@pytest.mark.asyncio
async def test_scoring_preflight_cannot_dispatch_question_or_be_reused_for_other_run(saved):
    service, captures, run, owner = scorer(saved)
    ready = service.preflight(owner.workspace_id, owner, run["run_id"], ("answer",), "fixture")
    qa_owner = WorkspacePrincipal(
        owner.workspace_id, "owner", (*owner.capabilities, "questions:ask")
    )
    with pytest.raises(KnoraError, match="EVALUATION_PREFLIGHT_STALE"):
        saved[0].start_run(owner.workspace_id, qa_owner, ready["preflight_id"], "not-qa")
    with pytest.raises(KnoraError, match="EVALUATION_IDEMPOTENCY_CONFLICT"):
        await service.score(
            owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "same-key"
        )
        other = service.preflight(owner.workspace_id, owner, run["run_id"], ("answer",), "fixture")
        await service.score(
            owner.workspace_id, owner, run["run_id"], other["preflight_id"], "same-key"
        )
    assert len(captures) == 1


def test_native_m3_saved_mapping_keeps_exact_question_reference_and_generation_text():
    from knora.evaluation.scoring import capture_saved_cases

    catalog = Milestone3Catalog(ROOT)
    owner = WorkspacePrincipal("evaluation-m3-v1", "reader", ("operator:read",))
    entry = catalog.get_dataset(owner.workspace_id, "m3-dataset-v1")
    selection = {
        "reference": asdict(entry.reference),
        "selected_case_ids": ["lexical-01"],
        "context_only_case_ids": [],
    }
    run = {
        "run_id": "m3-saved",
        "workspace_id": owner.workspace_id,
        "selection": selection,
        "selection_digest": digest_json(selection),
        "observations": {
            "lexical-01": {
                "status": "OBSERVED",
                "decision": "ANSWER",
                "trace_id": "m3-trace",
                "public_answer": "Thirty days [E1]",
                "generation_evidence": [["E1", "Refunds are accepted within 30 days."]],
            }
        },
    }
    result = capture_saved_cases(
        EvaluationRunService(catalog, None, ()), run, owner, ("lexical-01",)
    )
    assert result[0]["capture"] == {
        "run_id": "m3-saved",
        "case_id": "lexical-01",
        "attempt": 1,
        "trace_id": "m3-trace",
        "question": "What is the refund period?",
        "reference_answer": "30 days",
        "answer": "Thirty days [E1]",
        "generation_evidence": [{"alias": "E1", "content": "Refunds are accepted within 30 days."}],
        "evidence_status": "exact",
    }


def test_missing_legacy_reference_and_generation_evidence_are_explicitly_inapplicable(tmp_path):
    import hashlib
    import json
    import shutil

    from knora.evaluation.scoring import _pending, capture_saved_cases

    (tmp_path / "evals/datasets").mkdir(parents=True)
    shutil.copytree(ROOT / "evals/corpora/milestone_3", tmp_path / "evals/corpora/milestone_3")
    records = [
        json.loads(line)
        for line in (ROOT / "evals/datasets/milestone_3.jsonl").read_text().splitlines()
    ]
    records[0]["answer_expectations"].pop("reference_answer")
    path = tmp_path / "evals/datasets/milestone_3.jsonl"
    path.write_bytes("\n".join(json.dumps(row) for row in records).encode("utf-8"))
    manifest = json.loads((ROOT / "evals/datasets/milestone_3.manifest.json").read_text())
    manifest["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (path.parent / "milestone_3.manifest.json").write_text(json.dumps(manifest))
    catalog = Milestone3Catalog(tmp_path)
    owner = WorkspacePrincipal("evaluation-m3-v1", "reader", ("operator:read",))
    entry = catalog.get_dataset(owner.workspace_id, "m3-dataset-v1")
    selection = {
        "reference": asdict(entry.reference),
        "selected_case_ids": ["lexical-01"],
        "context_only_case_ids": [],
    }
    run = {
        "run_id": "legacy",
        "workspace_id": owner.workspace_id,
        "selection": selection,
        "selection_digest": digest_json(selection),
        "observations": {
            "lexical-01": {
                "status": "OBSERVED",
                "decision": "ANSWER",
                "trace_id": "trace",
                "public_answer": "30 days",
                "generation_evidence": [],
            }
        },
    }
    item = capture_saved_cases(
        EvaluationRunService(catalog, None, ()), run, owner, ("lexical-01",)
    )[0]
    assert item["capture"]["evidence_status"] == "unavailable"
    assert {name: m["status"] for name, m in _pending(item)["metrics"].items()} == {
        "correctness": "not_applicable",
        "answer_relevancy": "not_run",
        "faithfulness": "not_applicable",
    }


@pytest.mark.asyncio
async def test_changed_saved_observation_rejects_old_scoring_preflight(saved):
    service, captures, run, owner = scorer(saved)
    ready = service.preflight(owner.workspace_id, owner, run["run_id"], ("answer",), "fixture")
    with saved[1]._sessions.begin() as session:
        row = session.get(EvaluationRunTable, run["run_id"])
        observations = deepcopy(row.observations)
        observations["answer"]["public_answer"] = "Different saved answer"
        row.observations = observations
    with pytest.raises(KnoraError, match="EVALUATION_SCORING_NOT_READY"):
        await service.score(
            owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "drift"
        )
    assert captures == []


@pytest.mark.asyncio
async def test_judge_cannot_mutate_bound_capture_to_relabel_its_input_digest(saved):
    service, captures, run, owner = scorer(saved)
    profile = service._profiles["fixture"]
    original_measure = profile.measure

    def mutate(capture):
        capture["answer"] = "A different answer"
        return original_measure(capture)

    service._profiles["fixture"] = replace(profile, measure=mutate)
    ready = service.preflight(owner.workspace_id, owner, run["run_id"], ("answer",), "fixture")
    result = await service.score(
        owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "mutated"
    )
    assert result["status"] == "INDETERMINATE"
    assert result["results"]["answer"]["reason"] == "JUDGE_RESULT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_profile_config_remains_the_preflight_snapshot_when_callback_changes_it(saved):
    service, _, run, owner = scorer(saved)
    profile = service._profiles["fixture"]
    profile.config["parameters"] = {"temperature": 0}
    original_measure = profile.measure

    def mutate_config(capture):
        profile.config["parameters"]["temperature"] = 1
        return original_measure(capture)

    service._profiles["fixture"] = replace(profile, measure=mutate_config)
    ready = service.preflight(owner.workspace_id, owner, run["run_id"], ("answer",), "fixture")
    result = await service.score(
        owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "config"
    )
    assert (
        result["scorer"]["config"]
        == ready["scorer"]["config"]
        == {"parameters": {"temperature": 0}}
    )
    assert service.read(owner.workspace_id, owner, run["run_id"])["batches"][0] == result


@pytest.mark.asyncio
async def test_real_deepeval_adapter_scores_saved_pdf_only_through_mock_transport(saved, tmp_path):
    import json
    from datetime import UTC, datetime, timedelta

    import httpx
    from evals.scorers.deepeval_cloudflare import AttemptLedger, CloudflareJudge, score_capture

    from knora.evaluation.scoring import EvaluationScoringService, ScoringProfile

    def schema_value(schema, definitions):
        if "$ref" in schema:
            return schema_value(definitions[schema["$ref"].split("/")[-1]], definitions)
        if "anyOf" in schema:
            return schema_value(
                next(s for s in schema["anyOf"] if s.get("type") != "null"), definitions
            )
        if schema.get("type") == "object":
            return {
                k: schema_value(v, definitions) for k, v in schema.get("properties", {}).items()
            }
        if schema.get("type") == "array":
            return [schema_value(schema["items"], definitions)]
        if schema.get("type") in ("number", "integer"):
            return 1
        return schema.get("enum", ["supported"])[0]

    requests = []

    def endpoint(request):
        payload = json.loads(request.content)
        requests.append(payload)
        schema = payload["response_format"]["json_schema"]["schema"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(schema_value(schema, schema.get("$defs", {})))
                        },
                    }
                ]
            },
        )

    runs, store, run, owner = saved
    with httpx.Client(transport=httpx.MockTransport(endpoint)) as client:
        judge = CloudflareJudge(
            endpoint="https://api.cloudflare.com/client/v4/accounts/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/ai/v1/chat/completions",
            token="fixture-only",
            model="@cf/openai/gpt-oss-20b",
            client=client,
            ledger=AttemptLedger(
                tmp_path / "attempts.sqlite3",
                run_id=run["run_id"],
                deadline=datetime.now(UTC) + timedelta(minutes=1),
                cap=24,
            ),
        )
        profile = ScoringProfile(
            "fixture",
            "offline",
            judge.get_model_name(),
            "direct-measure-v1",
            {},
            lambda capture: score_capture(
                {**capture, "data_classification": "synthetic", "egress_approved": True}, judge
            ),
        )
        service = EvaluationScoringService(runs, store, (profile,))
        ready = service.preflight(
            owner.workspace_id, owner, run["run_id"], ("answer", "refusal"), "fixture"
        )
        batch = await service.score(
            owner.workspace_id, owner, run["run_id"], ready["preflight_id"], "native-sdk"
        )
        assert batch["status"] == "COMPLETED"
        assert {m["status"] for m in batch["results"]["answer"]["metrics"].values()} == {"scored"}
        assert batch["results"]["answer"]["http_attempts"] == len(requests) == judge.ledger.count()
        assert requests
        assert all("/questions" not in str(request) for request in requests)
