import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from evals.runners import pdf_retrieval_v3 as runner
from evals.runners.pdf_source_binding import digest


def selection(tmp_path):
    row = {
        "run_id": "run",
        "case_id": "q1",
        "attempt_id": "run:q1:1",
        "attempt": 1,
        "workspace_id": "workspace",
        "conversation_id": "conversation-1",
        "turn_id": "turn-1",
        "trace_id": "trace-1",
        "corpus_sha256": "corpus",
        "dataset_sha256": "gold",
        "derivation_sha256": "derivation",
        "public_response": {
            "trace_id": "trace-1",
            "workspace_id": "workspace",
            "decision": "REFUSAL",
        },
        "failure_code": "CASE_FAILED_NO_RETRY",
        "observation_failure_code": "CITATION_STRUCTURAL_ERROR",
        "end_to_end_latency_ms": 8287.24,
    }
    row["response_sha256"] = digest(row["public_response"])
    capture = tmp_path / "case-q1-attempt-1.json"
    runner.publish_json(capture, row)
    observation = row | {
        "failure_code": None,
        "decision": "REFUSAL",
        "selected_chunk_ids": [],
        "candidates": [],
        "retrieval_latency_ms": 3.5,
        "provider_metadata": {},
    }
    record = {
        "schema_version": 1,
        "status": "approved",
        "reviewer": "NhiBuaa",
        "decision_url": "https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6186149890",
        "original_capture_sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
        "identity": {
            k: v
            for k, v in row.items()
            if k
            not in {
                "public_response",
                "failure_code",
                "observation_failure_code",
                "end_to_end_latency_ms",
            }
        },
        "proposal_sha256": "proposal",
        "evaluator_sha256": runner.revalidation_evaluator_sha256(),
        "observation": observation,
        "observation_sha256": digest(observation),
    }
    return capture, row, record


def write_record(tmp_path, record):
    path = tmp_path / "revalidation.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def dataset():
    return NS(
        cases=(NS(id="q1", parent_case_id=None), NS(id="q2", parent_case_id="q1")),
        dataset_sha256="gold",
        corpus_sha256="corpus",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse_captures", [False, True])
async def test_reviewed_attempt_continues_follow_up_without_reanswering_or_rewriting(
    tmp_path, monkeypatch, reverse_captures
):
    capture, original, record = selection(tmp_path)
    before = capture.read_bytes()
    calls = []

    async def execute(case, **kwargs):
        calls.append((case.id, kwargs))
        return original | {"case_id": case.id, "attempt_id": "run:q2:1", "failure_code": None}

    executor = NS(
        run_id="run",
        workspace_id="workspace",
        execute=execute,
        assert_not_paused=lambda: None,
        is_paused=lambda: False,
    )
    path = write_record(tmp_path, record)
    options = dict(
        revalidation_record=path, proposal_sha256="proposal", derivation_sha256="derivation"
    )
    rows = await runner.collect_cases(dataset(), executor, tmp_path, **options)
    assert rows[0] == record["observation"]
    assert calls == [
        ("q2", {"conversation_id": "conversation-1", "parent_turn_id": "turn-1", "attempt": 1})
    ]
    assert capture.read_bytes() == before
    assert not (tmp_path / "case-q1-attempt-2.json").exists()
    glob = type(tmp_path).glob
    monkeypatch.setattr(
        type(tmp_path),
        "glob",
        lambda path, pattern: sorted(glob(path, pattern), reverse=reverse_captures),
    )
    assert {r["case_id"]: r for r in runner.selected_observations(tmp_path, **options)}[
        "q1"
    ] == rows[0]
    assert {r["case_id"]: r for r in runner.selected_observations(tmp_path)}["q1"][
        "failure_code"
    ] == "CASE_FAILED_NO_RETRY"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed",
    [
        "status",
        "reviewer",
        "decision_url",
        "original_capture_sha256",
        "proposal_sha256",
        "derivation_sha256",
        "evaluator_sha256",
        "observation_sha256",
        "response_sha256",
        "run_id",
        "workspace_id",
        "conversation_id",
        "turn_id",
        "trace_id",
        "attempt_id",
        "corpus_sha256",
        "dataset_sha256",
        "case_id",
        "attempt",
        "public_response",
        "end_to_end_latency_ms",
        "unreviewed_field",
        "missing_identity",
        "failure_code",
        "original_failure",
    ],
)
async def test_invalid_selection_fails_before_dispatch(tmp_path, changed):
    capture, original, record = selection(tmp_path)
    if changed in record["identity"] and changed not in {"case_id", "attempt"}:
        record["identity"][changed] = "wrong"
    elif changed == "case_id":
        record["identity"][changed] = "../q1"
    elif changed == "attempt":
        record["identity"][changed] = True
    elif changed == "missing_identity":
        del record["identity"]["turn_id"]
    elif changed in {
        "public_response",
        "end_to_end_latency_ms",
        "unreviewed_field",
        "failure_code",
    }:
        record["observation"][changed] = "wrong"
        record["observation_sha256"] = digest(record["observation"])
    elif changed == "original_failure":
        original["observation_failure_code"] = "PROVIDER_FAILED"
        capture.write_text(json.dumps(original), encoding="utf-8")
        record["original_capture_sha256"] = hashlib.sha256(capture.read_bytes()).hexdigest()
    else:
        record[changed] = "pending" if changed == "status" else "wrong"
    path = write_record(tmp_path, record)
    # q0 would dispatch first if validation were deferred until the selected q1.
    data = dataset()
    data.cases = (NS(id="q0", parent_case_id=None), *data.cases)
    executor = NS(
        run_id="run",
        workspace_id="workspace",
        assert_not_paused=lambda: pytest.fail("invalid selection reached dispatch"),
    )
    with pytest.raises(ValueError, match="revalidation"):
        await runner.collect_cases(
            data,
            executor,
            tmp_path,
            revalidation_record=path,
            proposal_sha256="proposal",
            derivation_sha256="derivation",
        )


def test_record_is_bound_to_current_capture_and_latest_attempt(tmp_path):
    capture, original, record = selection(tmp_path)
    path = write_record(tmp_path, record)
    options = dict(proposal_sha256="proposal", derivation_sha256="derivation")
    assert runner.load_revalidation_selection(tmp_path, path, **options) == {
        "q1": record["observation"]
    }
    capture.write_bytes(capture.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="revalidation"):
        runner.load_revalidation_selection(tmp_path, path, **options)
    record["original_capture_sha256"] = hashlib.sha256(capture.read_bytes()).hexdigest()
    write_record(tmp_path, record)
    runner.publish_json(tmp_path / "case-q1-attempt-2.json", deepcopy(original) | {"attempt": 2})
    with pytest.raises(ValueError, match="revalidation"):
        runner.selected_observations(tmp_path, revalidation_record=path, **options)
