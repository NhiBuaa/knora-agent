import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from evals.runners.run_deepeval_capture import run_capture
from evals.scorers.deepeval_cloudflare import (
    AttemptLedger,
    CloudflareJudge,
    JudgeError,
    derive_captures,
    publish_supplement,
    score_capture,
    validate_free_preflight,
)
from pydantic import BaseModel


class Judgment(BaseModel):
    score: float


def _capture(**overrides):
    return {
        "run_id": "run-1",
        "case_id": "case-1",
        "attempt": 1,
        "trace_id": "trace-1",
        "question": "What is the refund window?",
        "answer": "Thirty days.",
        "reference_answer": "Refunds are accepted within 30 days.",
        "generation_evidence": [{"alias": "E1", "content": "Refunds: 30 days."}],
        "evidence_status": "exact",
        "data_classification": "synthetic",
        "egress_approved": True,
        **overrides,
    }


def test_attempt_ledger_persists_timeout_attempts_and_enforces_cap(tmp_path) -> None:
    path = tmp_path / "attempts.sqlite3"
    deadline = datetime.now(UTC) + timedelta(minutes=60)
    ledger = AttemptLedger(path, run_id="run-1", deadline=deadline, cap=2)
    assert ledger.reserve() == 1
    assert AttemptLedger(path, run_id="run-1", deadline=deadline, cap=2).reserve() == 2
    with pytest.raises(JudgeError, match="ATTEMPT_CAP_REACHED"):
        ledger.reserve()
    assert ledger.count() == 2


def test_schema_aware_judge_rejects_truncation_and_counts_attempts(tmp_path) -> None:
    requests = []

    def endpoint(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "length", "message": {"content": '{"score": 0.7}'}}]
            },
        )

    ledger = AttemptLedger(
        tmp_path / "attempts.sqlite3",
        run_id="run-1",
        deadline=datetime.now(UTC) + timedelta(minutes=1),
        cap=24,
    )
    judge = CloudflareJudge(
        endpoint="https://api.cloudflare.com/client/v4/accounts/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/ai/v1/chat/completions",
        token="secret",
        model="@cf/openai/gpt-oss-20b",
        ledger=ledger,
        client=httpx.Client(transport=httpx.MockTransport(endpoint)),
    )
    with pytest.raises(JudgeError, match="JUDGE_RESPONSE_TRUNCATED"):
        judge.generate("prompt", schema=Judgment)
    assert ledger.count() == 1
    assert requests[0]["response_format"]["type"] == "json_schema"
    assert requests[0]["model"] == "@cf/openai/gpt-oss-20b"


def test_timeout_reserves_attempt_before_transport(tmp_path) -> None:
    def endpoint(_request):
        raise httpx.ReadTimeout("timeout")

    ledger = AttemptLedger(
        tmp_path / "attempts.sqlite3",
        run_id="run-1",
        deadline=datetime.now(UTC) + timedelta(minutes=1),
        cap=24,
    )
    judge = CloudflareJudge(
        endpoint="https://api.cloudflare.com/client/v4/accounts/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/ai/v1/chat/completions",
        token="secret",
        model="@cf/openai/gpt-oss-20b",
        ledger=ledger,
        client=httpx.Client(transport=httpx.MockTransport(endpoint)),
    )
    with pytest.raises(JudgeError, match="JUDGE_TIMEOUT"):
        judge.generate("prompt")
    assert ledger.count() == 1


def test_private_capture_is_rejected_before_http(tmp_path) -> None:
    judge = CloudflareJudge(
        endpoint="https://api.cloudflare.com/client/v4/accounts/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/ai/v1/chat/completions",
        token="secret",
        model="@cf/openai/gpt-oss-20b",
        ledger=AttemptLedger(
            tmp_path / "attempts.sqlite3",
            run_id="run-1",
            deadline=datetime.now(UTC) + timedelta(minutes=1),
            cap=24,
        ),
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _request: pytest.fail("unexpected HTTP"))
        ),
    )
    with pytest.raises(JudgeError, match="EGRESS_NOT_APPROVED"):
        score_capture(_capture(data_classification="private"), judge)
    assert judge.ledger.count() == 0


def test_judge_rejects_non_cloudflare_endpoint_before_http(tmp_path) -> None:
    ledger = AttemptLedger(
        tmp_path / "attempts.sqlite3",
        run_id="run-1",
        deadline=datetime.now(UTC) + timedelta(minutes=1),
        cap=24,
    )
    with pytest.raises(JudgeError, match="JUDGE_CONFIGURATION_INVALID"):
        CloudflareJudge(
            endpoint="https://judge.example/chat/completions",
            token="secret",
            model="@cf/openai/gpt-oss-20b",
            ledger=ledger,
        )
    assert ledger.count() == 0


def test_missing_exact_evidence_cannot_receive_faithfulness_score(tmp_path) -> None:
    judge = SimpleNamespace(get_model_name=lambda: "mock", ledger=SimpleNamespace(count=lambda: 0))
    result = score_capture(
        _capture(generation_evidence=[], evidence_status="unavailable", egress_approved=False),
        judge,
        measure=False,
    )
    assert result["metrics"]["faithfulness"]["status"] == "not_applicable"
    assert result["metrics"]["faithfulness"]["score"] is None


def test_supplement_rejects_wrong_trace_and_never_clobbers(tmp_path) -> None:
    source = {
        "provenance": {"dataset_digest": "sha256:abc"},
        "observations": [{"case_id": "case-1", "trace_id": "trace-1"}],
    }
    output = tmp_path / "supplement.json"
    with pytest.raises(JudgeError, match="CAPTURE_TRACE_MISMATCH"):
        publish_supplement(output, source, [_capture(trace_id="wrong")], [])
    result = score_capture(
        _capture(), SimpleNamespace(get_model_name=lambda: "offline"), measure=False
    )
    report = publish_supplement(output, source, [_capture()], [result])
    assert report["cases"][0]["trace_id"] == "trace-1"
    assert output.exists()
    assert list(tmp_path.glob(".*.tmp")) == []
    with pytest.raises(FileExistsError):
        publish_supplement(output, source, [_capture()], [result])


@pytest.mark.parametrize(
    "changed,replacement",
    (
        ("question", "How long can I return an item?"),
        ("answer", "Forty days."),
        ("reference_answer", "Refunds are accepted within 40 days."),
        ("generation_evidence", [{"alias": "E1", "content": "Refunds: 40 days."}]),
        ("evidence_status", "unavailable"),
    ),
)
def test_supplement_rejects_scores_from_stale_inputs(tmp_path, changed, replacement) -> None:
    source = {"observations": [{"case_id": "case-1", "trace_id": "trace-1"}]}
    original = _capture()
    result = score_capture(
        original, SimpleNamespace(get_model_name=lambda: "offline"), measure=False
    )
    current = _capture(**{changed: replacement})
    with pytest.raises(JudgeError, match="RESULT_INPUT_MISMATCH"):
        publish_supplement(tmp_path / "supplement.json", source, [current], [result])
    assert not (tmp_path / "supplement.json").exists()


@pytest.mark.parametrize(
    "field,value", (("run_id", "other-run"), ("attempt", 2), ("trace_id", "other-trace"))
)
def test_supplement_rejects_mismatched_result_identity(tmp_path, field, value) -> None:
    source = {"observations": [{"case_id": "case-1", "trace_id": "trace-1"}]}
    result = score_capture(
        _capture(), SimpleNamespace(get_model_name=lambda: "offline"), measure=False
    )
    result[field] = value
    with pytest.raises(JudgeError, match="RESULT_IDENTITY_MISMATCH"):
        publish_supplement(tmp_path / "supplement.json", source, [_capture()], [result])


@pytest.mark.parametrize("field", ("run_id", "attempt", "trace_id", "input_sha256"))
def test_supplement_rejects_missing_result_binding(tmp_path, field) -> None:
    source = {"observations": [{"case_id": "case-1", "trace_id": "trace-1"}]}
    result = score_capture(
        _capture(), SimpleNamespace(get_model_name=lambda: "offline"), measure=False
    )
    result.pop(field, None)
    error = "RESULT_INPUT_MISMATCH" if field == "input_sha256" else "RESULT_IDENTITY_MISMATCH"
    with pytest.raises(JudgeError, match=error):
        publish_supplement(tmp_path / "supplement.json", source, [_capture()], [result])
    assert not (tmp_path / "supplement.json").exists()


def test_capture_derives_answer_and_exact_context_only_from_report() -> None:
    case = SimpleNamespace(
        id="case-1",
        question="What is the refund window?",
        answer_expectations=SimpleNamespace(reference_answer="30 days."),
    )
    source = {
        "observations": [
            {
                "case_id": "case-1",
                "status": "observed",
                "trace_id": "trace-1",
                "decision": "ANSWER",
                "public_answer": "Thirty days.",
                "generation_evidence_status": "exact",
                "generation_evidence": [{"alias": "E1", "content": "Refunds: 30 days."}],
            }
        ]
    }
    captures = derive_captures(source, [case], run_id="run-1")
    assert captures[0]["answer"] == "Thirty days."
    assert captures[0]["generation_evidence"] == [{"alias": "E1", "content": "Refunds: 30 days."}]
    source["observations"][0]["generation_evidence_status"] = "unavailable"
    assert derive_captures(source, [case], run_id="run-1")[0]["generation_evidence"] == []
    source["observations"][0]["trace_id"] = None
    assert derive_captures(source, [case], run_id="run-1")[0]["trace_id"] is None


def test_free_preflight_requires_fresh_bound_approval() -> None:
    digest = "sha256:" + "a" * 64
    record = {
        "run_id": "run-1",
        "capture_sha256": digest,
        "account_id": "b" * 32,
        "plan": "Workers Free",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "trial_started_at_utc": datetime.now(UTC).isoformat(),
        "quota_resets_at_utc": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "reviewed_by": "owner",
        "used_neurons_today": 0,
        "remaining_neurons_today": 1000,
        "zero_paid_budget_confirmed": True,
        "approved_data_classification": "synthetic",
    }
    assert validate_free_preflight(record, run_id="run-1", capture_sha256=digest) == "b" * 32
    record["plan"] = "unknown"
    with pytest.raises(JudgeError, match="FREE_PREFLIGHT_UNVERIFIED"):
        validate_free_preflight(record, run_id="run-1", capture_sha256=digest)
    record["plan"] = "Workers Free"
    record["trial_started_at_utc"] = record["observed_at_utc"]
    record["quota_resets_at_utc"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    with pytest.raises(JudgeError, match="FREE_PREFLIGHT_UNVERIFIED"):
        validate_free_preflight(record, run_id="run-1", capture_sha256=digest)
    record["plan"] = "Workers Free"
    record["trial_started_at_utc"] = (datetime.now(UTC) - timedelta(minutes=61)).isoformat()
    with pytest.raises(JudgeError, match="FREE_PREFLIGHT_UNVERIFIED"):
        validate_free_preflight(record, run_id="run-1", capture_sha256=digest)


@pytest.mark.parametrize("ambient_mode", ["hybrid", "system_one"])
def test_real_deepeval_metrics_use_only_mocked_cloudflare_transport(
    tmp_path, monkeypatch, ambient_mode
) -> None:
    monkeypatch.setenv("DEEPEVAL_EVAL_MODE", ambient_mode)
    monkeypatch.setattr(
        "deepeval.metrics.utils.models.TypeSafeModel",
        lambda *_args, **_kwargs: pytest.fail("UNAPPROVED_PROVIDER_SELECTED"),
    )
    prompts = []

    def value(schema, defs):
        if "$ref" in schema:
            return value(defs[schema["$ref"].split("/")[-1]], defs)
        if "anyOf" in schema:
            return value(next(item for item in schema["anyOf"] if item.get("type") != "null"), defs)
        if schema.get("type") == "object":
            return {key: value(spec, defs) for key, spec in schema.get("properties", {}).items()}
        if schema.get("type") == "array":
            return [value(schema["items"], defs)]
        if schema.get("type") in ("number", "integer"):
            return 1
        if "enum" in schema:
            return schema["enum"][0]
        return "supported"

    def endpoint(request):
        payload = json.loads(request.content)
        prompts.append(payload["messages"][0]["content"])
        schema = payload["response_format"]["json_schema"]["schema"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(value(schema, schema.get("$defs", {})))},
                    }
                ]
            },
        )

    judge = CloudflareJudge(
        endpoint="https://api.cloudflare.com/client/v4/accounts/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/ai/v1/chat/completions",
        token="secret",
        model="@cf/openai/gpt-oss-20b",
        ledger=AttemptLedger(
            tmp_path / "attempts.sqlite3",
            run_id="run-1",
            deadline=datetime.now(UTC) + timedelta(minutes=1),
            cap=24,
        ),
        client=httpx.Client(transport=httpx.MockTransport(endpoint)),
    )
    result = score_capture(_capture(), judge)
    assert set(result["metrics"]) == {"correctness", "answer_relevancy", "faithfulness"}
    assert {item["status"] for item in result["metrics"].values()} == {"scored"}
    assert judge.ledger.count() == len(prompts)
    assert result["http_attempts"] == len(prompts)
    assert prompts


def test_runner_defaults_to_offline_and_immutable_supplement(tmp_path) -> None:
    case = SimpleNamespace(
        id="case-1",
        question="What is the refund window?",
        answer_expectations=SimpleNamespace(reference_answer="30 days."),
    )
    source = {
        "provenance": {"dataset_digest": "sha256:abc"},
        "observations": [
            {
                "case_id": "case-1",
                "status": "observed",
                "trace_id": "trace-1",
                "decision": "ANSWER",
                "public_answer": "Thirty days.",
                "generation_evidence_status": "unavailable",
                "generation_evidence": [],
            }
        ],
    }
    output = tmp_path / "supplement.json"
    report = run_capture(source, [case], run_id="run-1", output=output)
    assert report["cases"][0]["metrics"]["faithfulness"]["status"] == "not_applicable"
    assert output.exists()
    with pytest.raises(FileExistsError):
        run_capture(source, [case], run_id="run-1", output=output)
    with pytest.raises(JudgeError, match="CASE_SELECTION_INVALID"):
        run_capture(
            source, [case], run_id="run-1", output=tmp_path / "other.json", case_ids=("missing",)
        )


def test_live_trial_rejects_more_than_two_cases_before_preflight(tmp_path) -> None:
    cases = [
        SimpleNamespace(
            id=f"case-{index}",
            question="q",
            answer_expectations=SimpleNamespace(reference_answer="a"),
        )
        for index in range(3)
    ]
    source = {
        "observations": [
            {
                "case_id": case.id,
                "status": "observed",
                "trace_id": f"trace-{index}",
                "decision": "ANSWER",
                "public_answer": "a",
            }
            for index, case in enumerate(cases)
        ]
    }
    with pytest.raises(JudgeError, match="LIVE_CASE_LIMIT_EXCEEDED"):
        run_capture(
            source, cases, run_id="run-1", output=tmp_path / "supplement.json", preflight={}
        )
