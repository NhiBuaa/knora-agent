import json
from pathlib import Path

import pytest
from evals.runners.run_security_shadow import (
    evaluate_cases,
    load_capture_units,
    write_shadow_report,
)
from evals.scorers.security_shadow import scan_text

FIXTURES = Path(__file__).parent / "fixtures" / "security_shadow"


class FakePass:
    outcome = "pass"


class FakeFail:
    outcome = "fail"
    error_message = "raw-secret-must-never-appear"


class FakeValidator:
    def __init__(self, result):
        self.result = result

    def validate(self, text, metadata):
        return self.result


def test_scan_text_sanitizes_validator_failure():
    result = scan_text("api_key = fake", validator=FakeValidator(FakeFail()))

    assert result == {
        "status": "detected",
        "finding_type": "secrets_present",
        "diagnostics": {"validator": "SecretsPresent"},
    }
    assert "raw-secret" not in json.dumps(result)


def test_scan_text_reports_pass_and_error():
    assert scan_text("hello", validator=FakeValidator(FakePass()))["status"] == "clear"

    class Broken:
        def validate(self, text, metadata):
            raise RuntimeError("do not publish this")

    result = scan_text("hello", validator=Broken())
    assert result == {
        "status": "error",
        "finding_type": None,
        "diagnostics": {"error": "validator_error"},
    }


def test_evaluate_cases_reports_detection_and_false_positives():
    cases = [
        {"case_id": "tp", "label": "positive", "text": "x"},
        {"case_id": "fn", "label": "positive", "text": "x"},
        {"case_id": "fp", "label": "negative", "text": "x"},
        {"case_id": "tn", "label": "negative", "text": "x"},
        {"case_id": "unreviewed", "label": "unreviewed", "text": "x"},
    ]

    results = iter(
        [
            {"status": "detected"},
            {"status": "clear"},
            {"status": "detected"},
            {"status": "clear"},
            {"status": "detected"},
        ]
    )
    report = evaluate_cases(cases, lambda text: next(results))

    assert report["metrics"] == {
        "tp": 1,
        "fp": 1,
        "tn": 1,
        "fn": 1,
        "precision": 0.5,
        "recall": 0.5,
        "false_positive_rate": 0.5,
    }
    assert report["population"] == {
        "total": 5,
        "reviewed": 4,
        "unreviewed": 1,
        "evaluable": 4,
        "unavailable": 0,
        "errors": 0,
        "timeouts": 0,
        "unknown": 0,
    }


def test_load_capture_preserves_identity_and_marks_missing_evidence():
    units = load_capture_units(FIXTURES / "capture.json")

    assert len(units) == 2
    assert units[0]["scope"] == "output"
    assert units[0]["text"] == "Answer without exact evidence."
    assert all(unit["run_id"] == "run-1" for unit in units)
    assert units[1]["evidence_status"] == "unavailable"
    assert units[1]["text"] is None


def test_report_is_immutable_and_contains_no_raw_text(tmp_path):
    report = {"cases": [{"case_id": "tp", "status": "detected"}]}
    output = tmp_path / "shadow.json"

    write_shadow_report(output, report, source_digest="sha256:abc")
    written = json.loads(output.read_text(encoding="utf-8"))

    assert written["schema_version"] == 1
    assert written["source_digest"] == "sha256:abc"
    assert "text" not in json.dumps(written)
    with pytest.raises(FileExistsError):
        write_shadow_report(output, report, source_digest="sha256:abc")


def test_unknown_validator_result_is_not_clear():
    assert scan_text("hello", validator=FakeValidator(object()))["status"] == "unknown"


def test_capture_keeps_both_scopes_and_native_failure(tmp_path):
    capture = {
        "case_id": "c1",
        "run_id": "native-run",
        "attempt_id": "native-attempt",
        "trace_id": "t1",
        "workspace_id": "w1",
        "dataset_sha256": "native-gold",
        "failure_code": "CITATION_STRUCTURAL_ERROR",
        "public_response": {"decision": "REFUSAL", "refusal_reason": "No evidence."},
        "generation_evidence_status": "exact",
        "generation_evidence": [{"alias": "E1", "content": "exact evidence"}],
    }
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(capture), encoding="utf-8")
    units = load_capture_units(path)
    assert {unit["scope"] for unit in units} == {"generation_evidence", "output"}
    assert next(u for u in units if u["scope"] == "output")["text"] == "No evidence."
    assert all(u["failure_code"] == "CITATION_STRUCTURAL_ERROR" for u in units)
    report = evaluate_cases(units, lambda text: {"status": "clear"})
    assert all(c["run_id"] == "native-run" for c in report["cases"])
    assert all(c["dataset_sha256"] == "native-gold" for c in report["cases"])


def test_capture_rejects_malformed_or_duplicate_observations(tmp_path):
    path = tmp_path / "bad.json"
    for payload in [
        {"observations": [{"case_id": "c1"}, None]},
        {"observations": [{"case_id": "c1"}, {"case_id": "c1"}]},
    ]:
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            load_capture_units(path)


def test_labels_require_explicit_review_and_duplicate_units_fail():
    cases = [{"case_id": "p1", "scope": "output", "text": "a", "proposed_label": "positive"}]
    report = evaluate_cases(cases, lambda text: {"status": "detected"})
    assert report["population"]["evaluable"] == 0
    assert report["metrics"]["recall"] is None
    with pytest.raises(ValueError):
        evaluate_cases(cases + cases, lambda text: {"status": "clear"})


def test_failure_statuses_and_groups_have_explicit_denominators():
    cases = [
        {"case_id": "a", "scope": "output", "language": "vi", "label": "positive", "text": "a"},
        {"case_id": "b", "scope": "output", "language": "vi", "label": "negative", "text": "b"},
        {
            "case_id": "c",
            "scope": "generation_evidence",
            "language": "en",
            "label": "negative",
            "text": None,
        },
        {"case_id": "d", "scope": "output", "language": "en", "label": "negative", "text": "d"},
    ]
    results = iter([{"status": "detected"}, {"status": "timeout"}, {"status": "unknown"}])
    report = evaluate_cases(cases, lambda text: next(results))
    assert report["population"]["evaluable"] == 1
    assert report["population"]["timeouts"] == 1
    assert report["population"]["unknown"] == 1
    assert report["population"]["unavailable"] == 1
    vi_output = next(g for g in report["groups"] if g["language"] == "vi")
    assert vi_output["metrics"]["recall"] == 1.0
    assert vi_output["metrics"]["false_positive_rate"] is None


def test_report_projection_drops_arbitrary_diagnostics_and_text():
    cases = [{"case_id": "c1", "scope": "output", "text": "canary-must-not-leak"}]
    report = evaluate_cases(
        cases,
        lambda text: {
            "status": "detected",
            "diagnostics": {"raw": "canary-must-not-leak"},
            "fix_value": "canary-must-not-leak",
        },
    )
    assert "canary-must-not-leak" not in json.dumps(report)


def test_local_worker_is_bounded_and_hides_process_errors(monkeypatch):
    import subprocess

    from evals.scorers.security_shadow import scan_local

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 30
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        assert "OPENAI_API_KEY" not in kwargs["env"]
        raise subprocess.TimeoutExpired(args[0], 30, stderr=b"canary-must-not-leak")

    monkeypatch.setenv("OPENAI_API_KEY", "ambient-secret")
    monkeypatch.setattr(subprocess, "run", timeout)
    assert scan_local("text") == {
        "status": "timeout",
        "finding_type": None,
        "diagnostics": {"error": "validator_timeout"},
    }


def test_real_validator_runs_without_network_or_temp_leak(tmp_path, monkeypatch):
    import importlib.util

    from evals.scorers.security_shadow import scan_local

    if importlib.util.find_spec("guardrails") is None:
        pytest.skip("security-shadow optional packages are not installed")
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    result = scan_local("Mật khẩu giả cho kiểm thử.\npassword = 'KnoraCanary_188_x8k2'\n")
    assert result["status"] in {"detected", "clear"}
    assert result["diagnostics"]["blocked_network_attempts"] == 0
    assert list(tmp_path.iterdir()) == []


def test_review_is_bound_to_exact_artifact():
    from evals.runners.run_security_shadow import apply_review

    cases = [{"case_id": "c", "proposed_label": "positive"}]
    review = {
        "artifact_sha256": "sha256:abc",
        "reviewed_by": "owner",
        "decision_ref": "https://github.com/NhiBuaa/knora-agent/issues/188#issuecomment-1",
    }
    assert apply_review(cases, review, "sha256:abc")[0]["label"] == "positive"
    with pytest.raises(ValueError, match="REVIEW"):
        apply_review(cases, review, "sha256:def")


def test_blank_failure_is_unavailable_and_refusal_scans_reason(tmp_path):
    path = tmp_path / "capture.json"
    for response, expected in [
        ({"answer": "  ", "decision": "ANSWER"}, None),
        ({"answer": "", "decision": "REFUSAL", "refusal_reason": "No evidence."}, "No evidence."),
    ]:
        path.write_text(json.dumps({"case_id": "c", "public_response": response}))
        assert load_capture_units(path)[0]["text"] == expected


def test_root_provenance_is_preserved_and_conflicts_rejected(tmp_path):
    path = tmp_path / "report.json"
    payload = {
        "provenance": {"dataset_digest": "sha256:gold", "workspace_id": "w1"},
        "run_id": "run1",
        "observations": [
            {
                "case_id": "c",
                "public_answer": "hello",
                "error_code": "FAILED",
                "answer_sha256": "sha256:answer",
            }
        ],
    }
    path.write_text(json.dumps(payload))
    units = load_capture_units(path)
    assert units[0]["dataset_digest"] == "sha256:gold"
    assert units[0]["run_id"] == "run1"
    assert units[0]["error_code"] == "FAILED"
    assert units[0]["answer_sha256"] == "sha256:answer"
    payload["observations"][0]["workspace_id"] = "w2"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="IDENTITY"):
        load_capture_units(path)


def test_package_versions_are_preserved_and_drift_is_not_scored():
    from evals.scorers.security_shadow import APPROVED_PACKAGES

    cases = [{"case_id": "c", "text": "hello", "label": "negative"}]
    report = evaluate_cases(cases, lambda text: {"status": "clear", "packages": APPROVED_PACKAGES})
    assert report["cases"][0]["packages"] == APPROVED_PACKAGES
    report = evaluate_cases(
        cases, lambda text: {"status": "clear", "packages": {"guardrails-ai": "99"}}
    )
    assert report["population"]["errors"] == 1
    assert report["population"]["evaluable"] == 0
    assert report["cases"][0]["diagnostics"]["error"] == "dependency_version_mismatch"
