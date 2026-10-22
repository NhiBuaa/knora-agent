import copy
import hashlib
import importlib.util
import json
import socket
import sys
from collections import Counter
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "cloudflare_p1_shadow"
PYTHON = Path(sys.executable)


def runner():
    # The initial RED fails on the missing implementation, before importing it.
    assert importlib.util.find_spec("evals.runners.cloudflare_p1_shadow") is not None
    from evals.runners import cloudflare_p1_shadow

    return cloudflare_p1_shadow


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return digest(path.read_bytes())


def source(tmp_path, **changes):
    value = {
        "case_id": "c1",
        "run_id": "native-run",
        "attempt_id": "native-attempt",
        "trace_id": "native-trace",
        "workspace_id": "native-workspace",
        "status": "failed",
        "failure_code": "CITATION_STRUCTURAL_ERROR",
        "question": "Câu hỏi giữ nguyên?",
        "generation_evidence_status": "exact",
        "generation_evidence": [
            {"alias": "E2", "content": " Đầu\nCANARY nguồn tiếng Việt\n"},
            {"alias": "E1", "content": "Cuối nguồn. "},
        ],
        "public_response": {"decision": "ERROR"},
        **changes,
    }
    path = tmp_path / "capture.json"
    sha = write_json(path, value)
    return path, sha


def units(tmp_path):
    path, sha = source(tmp_path)
    return runner().load_units(path, expected_digest=sha), sha


def bundle(cases, sha, **row_changes):
    return {
        "schema_version": "hypothetical-p1-v1",
        "development_only": True,
        "source_artifact_sha256": sha,
        "configuration_sha256": runner().configuration_digest(),
        "observations": [
            {
                "case_id": case["case_id"],
                "scope": "generation_evidence",
                "input_sha256": case["input_sha256"],
                **{
                    key: case[key]
                    for key in ("run_id", "attempt_id", "trace_id", "workspace_id")
                    if key in case
                },
                "dispatch_count": 1,
                "retry_count": 0,
                "restart_state": "fresh",
                "http_status": 200,
                "log": {
                    "schema_version": "hypothetical-p1-log-v1",
                    "coverage": "complete",
                    "evaluation": "completed",
                    "verdict": "positive",
                    "raw_reason": "CANARY raw log reason",
                },
                **row_changes,
            }
            for case in cases
        ],
    }


def test_exact_cloudflare_envelope_preserves_roles_unicode_order_and_whitespace(tmp_path):
    from knora.providers.openai_compatible.generation import CLOUDFLARE_SYSTEM_PROMPT

    cases, _ = units(tmp_path)
    envelope = cases[0]["messages"]
    assert [message["role"] for message in envelope] == ["system", "user"]
    assert envelope[0]["content"] == CLOUDFLARE_SYSTEM_PROMPT
    assert envelope[1]["content"] == (
        '{"question": "Câu hỏi giữ nguyên?", "evidence": '
        '[{"evidence_id": "E2", "content": " Đầu\\nCANARY nguồn tiếng Việt\\n"}, '
        '{"evidence_id": "E1", "content": "Cuối nguồn. "}]}'
    )
    assert cases[0]["input_sha256"] == digest(
        json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    )
    assert cases[0]["failure_code"] == "CITATION_STRUCTURAL_ERROR"
    assert cases[0]["observation_status"] == "failed"


def test_long_boundary_content_is_never_truncated(tmp_path):
    long = "ĐẦU " + "giữa " * 10000 + " CUỐI"
    path, sha = source(tmp_path, generation_evidence=[{"alias": "E1", "content": long}])
    case = runner().load_units(path, expected_digest=sha)[0]
    assert json.loads(case["messages"][1]["content"])["evidence"][0]["content"] == long


@pytest.mark.parametrize(
    "changes",
    [{"question": None}, {"question": " "}, {"generation_evidence_status": "unavailable"}],
)
def test_missing_question_or_exact_evidence_stays_unavailable(tmp_path, changes):
    path, sha = source(tmp_path, **changes)
    cases = runner().load_units(path, expected_digest=sha)
    report = runner().build_report(cases, source_digest=sha)
    assert report["population"]["unavailable"] == 1
    assert report["cases"][0]["input_sha256"] is None
    assert report["cases"][0]["status"] == "unavailable"


def test_artifact_identity_and_duplicate_validation(tmp_path):
    path, sha = source(tmp_path)
    with pytest.raises(ValueError, match="DIGEST"):
        runner().load_units(path, expected_digest="sha256:wrong")
    value = json.loads(path.read_text(encoding="utf-8"))
    write_json(path, {"workspace_id": "other", "observations": [value]})
    with pytest.raises(ValueError, match="IDENTITY"):
        runner().load_units(path, expected_digest=digest(path.read_bytes()))
    write_json(path, {"observations": [value, value]})
    with pytest.raises(ValueError, match="IDENTIT"):
        runner().load_units(path, expected_digest=digest(path.read_bytes()))
    cases, sha = units(tmp_path)
    with pytest.raises(ValueError, match="DUPLICATE"):
        runner().build_report(cases + cases, source_digest=sha)


@pytest.mark.parametrize("aliases", [["E1", "E1"], ["raw-canary", "E1"]])
def test_invalid_aliases_cannot_silently_change_evidence(tmp_path, aliases):
    path, sha = source(
        tmp_path,
        generation_evidence=[{"alias": alias, "content": "text"} for alias in aliases],
    )
    with pytest.raises(ValueError, match="EVIDENCE"):
        runner().load_units(path, expected_digest=sha)


def test_fixture_balance_proposals_and_digest_bound_draft():
    path = FIXTURES / "cases.json"
    cases = runner().load_units(path, expected_digest=digest(path.read_bytes()), fixtures=True)
    assert len(cases) == 16
    assert Counter((case["language"], case["proposed_label"]) for case in cases) == {
        ("vi", "positive"): 4,
        ("vi", "negative"): 4,
        ("en", "positive"): 4,
        ("en", "negative"): 4,
    }
    review = json.loads((FIXTURES / "labels.review.draft.json").read_text(encoding="utf-8"))
    assert review["artifact_sha256"] == digest(path.read_bytes())
    assert review["reviewed_by"] is None
    assert {case["case_id"] for case in cases} == {item["case_id"] for item in review["items"]}
    assert all(case["fixture_provenance"] == "synthetic-development-control" for case in cases)
    report = runner().build_report(cases, source_digest=review["artifact_sha256"])
    assert report["population"]["unreviewed"] == 16
    assert report["metrics"] is None
    with pytest.raises(ValueError, match="REVIEW"):
        runner().load_units(
            path, expected_digest=digest(path.read_bytes()), fixtures=True, review=review
        )


def test_review_applies_only_to_exact_artifact_and_never_promotes_mock_to_live(tmp_path):
    path, sha = source(tmp_path, proposed_label="positive")
    review = {
        "artifact_sha256": "sha256:wrong",
        "reviewed_by": "owner",
        "decision_ref": "https://github.com/NhiBuaa/knora-agent/issues/188#issuecomment-1",
    }
    with pytest.raises(ValueError, match="REVIEW"):
        runner().load_units(path, expected_digest=sha, fixtures=True, review=review)
    review["artifact_sha256"] = sha
    # Native captures have no annotation proposal authority.
    with pytest.raises(ValueError, match="CAPTURE_LABEL"):
        runner().load_units(path, expected_digest=sha, review=review)
    fixture = json.loads(path.read_text(encoding="utf-8"))
    fixture["fixture_provenance"] = "synthetic-development-control"
    sha = write_json(path, [fixture])
    review["artifact_sha256"] = sha
    cases = runner().load_units(path, expected_digest=sha, fixtures=True, review=review)
    report = runner().build_report(cases, source_digest=sha, observations=bundle(cases, sha))
    assert report["metrics"]["tp"] == 1
    assert report["evidence_kind"] == "hypothetical_development"
    assert report["provider_quality_evidence"] is False
    assert report["live_requests"] == 0


@pytest.mark.parametrize(
    ("changes", "status", "reason"),
    [
        ({}, "detected", None),
        (
            {
                "log": {
                    "schema_version": "hypothetical-p1-log-v1",
                    "coverage": "complete",
                    "evaluation": "completed",
                    "verdict": "negative",
                }
            },
            "clear",
            None,
        ),
        ({"log": None}, "unavailable", "missing_log"),
        (
            {
                "log": {
                    "schema_version": "hypothetical-p1-log-v1",
                    "coverage": "truncated",
                    "evaluation": "completed",
                    "verdict": "negative",
                }
            },
            "unavailable",
            "incomplete_log",
        ),
        (
            {
                "log": {
                    "schema_version": "unknown",
                    "coverage": "complete",
                    "evaluation": "completed",
                    "verdict": "negative",
                }
            },
            "unavailable",
            "unsupported_log_schema",
        ),
        (
            {
                "log": {
                    "schema_version": "hypothetical-p1-log-v1",
                    "coverage": "complete",
                    "evaluation": "failed",
                    "verdict": "negative",
                }
            },
            "error",
            "detector_error",
        ),
        (
            {
                "log": {
                    "schema_version": "hypothetical-p1-log-v1",
                    "coverage": "complete",
                    "evaluation": "completed",
                }
            },
            "unavailable",
            "missing_verdict",
        ),
        ({"http_status": 403}, "error", "http_403"),
        ({"http_status": 429}, "error", "http_429"),
        ({"transport_error": "timeout"}, "timeout", "transport_timeout"),
        ({"cloudflare_error_code": 2016}, "error", "unexpected_guardrail_block"),
        ({"cloudflare_error_code": 2017}, "error", "unexpected_guardrail_block"),
        ({"dispatch_count": 0}, "unavailable", "not_sent"),
        ({"restart_state": "indeterminate"}, "unknown", "indeterminate_outcome"),
    ],
)
def test_hypothetical_import_never_infers_a_negative_from_transport(
    tmp_path, changes, status, reason
):
    cases, sha = units(tmp_path)
    report = runner().build_report(
        cases, source_digest=sha, observations=bundle(cases, sha, **changes)
    )
    row = report["cases"][0]
    assert row["status"] == status
    assert row["diagnostics"].get("error") == reason
    assert report["metrics"] is None
    assert report["provider_quality_evidence"] is False
    assert "CANARY" not in json.dumps(report, ensure_ascii=False)
    assert "raw_reason" not in json.dumps(report)


@pytest.mark.parametrize("field", ["source_artifact_sha256", "configuration_sha256"])
def test_import_must_match_source_and_configuration(tmp_path, field):
    cases, sha = units(tmp_path)
    observations = bundle(cases, sha)
    observations[field] = "sha256:wrong"
    with pytest.raises(ValueError, match="MISMATCH"):
        runner().build_report(cases, source_digest=sha, observations=observations)


@pytest.mark.parametrize(
    "field", ["input_sha256", "run_id", "attempt_id", "trace_id", "workspace_id"]
)
def test_import_must_match_exact_input_and_native_identity(tmp_path, field):
    cases, sha = units(tmp_path)
    observations = bundle(cases, sha, **{field: "wrong"})
    with pytest.raises(ValueError, match="MISMATCH"):
        runner().build_report(cases, source_digest=sha, observations=observations)
    observations["observations"][0].pop(field)
    with pytest.raises(ValueError, match="MISMATCH"):
        runner().build_report(cases, source_digest=sha, observations=observations)


def test_import_restart_accounting_preserves_attempts_without_retry_or_replay(tmp_path):
    cases, sha = units(tmp_path)
    observations = bundle(cases, sha, restart_state="already_sent", transport_error="timeout")
    report = runner().build_report(cases, source_digest=sha, observations=observations)
    assert report["accounting"] == {
        "selected": 1,
        "attempted": 1,
        "observed": 1,
        "completed": 0,
        "retries": 0,
    }
    assert report["replay_permitted"] is False
    assert report["cases"][0]["restart_state"] == "already_sent"
    observations["observations"].append(copy.deepcopy(observations["observations"][0]))
    with pytest.raises(ValueError, match="DUPLICATE"):
        runner().build_report(cases, source_digest=sha, observations=observations)
    for changes in [{"retry_count": 1}, {"dispatch_count": 2}]:
        with pytest.raises(ValueError, match="RETRY"):
            runner().build_report(
                cases, source_digest=sha, observations=bundle(cases, sha, **changes)
            )


def test_unknown_native_contract_remains_unavailable(tmp_path):
    cases, sha = units(tmp_path)
    observations = bundle(cases, sha)
    observations["schema_version"] = "native-unverified"
    observations["development_only"] = False
    report = runner().build_report(cases, source_digest=sha, observations=observations)
    assert report["cases"][0]["status"] == "unavailable"
    assert report["cases"][0]["diagnostics"]["error"] == "unsupported_native_contract"


def test_import_cannot_clear_unavailable_input_or_hide_missing_units(tmp_path):
    path, sha = source(tmp_path, question=None)
    cases = runner().load_units(path, expected_digest=sha)
    report = runner().build_report(cases, source_digest=sha, observations=bundle(cases, sha))
    assert report["cases"][0]["status"] == "unavailable"
    observations = bundle(cases, sha)
    observations["observations"] = []
    report = runner().build_report(cases, source_digest=sha, observations=observations)
    assert report["population"]["total"] == 1
    assert report["population"]["unavailable"] == 1


def test_safe_atomic_publication_is_immutable(tmp_path):
    cases, sha = units(tmp_path)
    report = runner().build_report(cases, source_digest=sha, observations=bundle(cases, sha))
    path = tmp_path / "report.json"
    runner().write_report(path, report)
    first = path.read_bytes()
    assert "CANARY" not in first.decode()
    assert "messages" not in first.decode()
    assert json.loads(first)["cases"][0]["trace_id"] == "native-trace"
    with pytest.raises(FileExistsError):
        runner().write_report(path, report)
    assert path.read_bytes() == first
    assert not list(tmp_path.glob(".*.tmp"))


def test_default_cli_has_zero_network_and_rejects_live_even_with_manifest(
    tmp_path, monkeypatch, capsys
):
    path, sha = source(tmp_path)
    output = tmp_path / "prepared.json"

    def forbidden(*args, **kwargs):
        raise AssertionError("network must remain impossible")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    base = ["p1", "--capture", str(path), "--expected-sha256", sha, "--output", str(output)]
    monkeypatch.setattr(sys, "argv", base)
    assert runner().main() == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["live_requests"] == 0
    assert report["execution"] == "prepared_offline"
    assert report["population"]["unavailable"] == 1
    for extra in [["--live"], ["--live", "--authorization-manifest", str(tmp_path / "fake.json")]]:
        monkeypatch.setattr(sys, "argv", base + extra)
        with pytest.raises(SystemExit) as error:
            runner().main()
        assert error.value.code == 2
    assert "LIVE_CONTRACT_NOT_APPROVED" in capsys.readouterr().err
    assert "CANARY" not in capsys.readouterr().err


def test_cli_import_pins_observation_digest_and_sanitizes_errors(tmp_path, monkeypatch, capsys):
    cases, sha = units(tmp_path)
    observed = tmp_path / "observations.json"
    observed_sha = write_json(observed, bundle(cases, sha))
    base = [
        "p1",
        "--capture",
        str(tmp_path / "capture.json"),
        "--expected-sha256",
        sha,
        "--output",
        str(tmp_path / "report.json"),
        "--observations",
        str(observed),
    ]
    monkeypatch.setattr(sys, "argv", base + ["--observations-sha256", "sha256:wrong"])
    with pytest.raises(SystemExit) as error:
        runner().main()
    assert error.value.code == 2
    assert "P1_INPUT_OR_PUBLICATION_ERROR" in capsys.readouterr().err
    monkeypatch.setattr(sys, "argv", base + ["--observations-sha256", observed_sha])
    assert runner().main() == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["observation_artifact_sha256"] == observed_sha
    assert report["execution"] == "hypothetical_development_import"


@pytest.mark.parametrize("state", ["already_sent", "indeterminate"])
def test_sent_attempt_cannot_claim_zero_dispatch(tmp_path, state):
    cases, sha = units(tmp_path)
    with pytest.raises(ValueError, match="ACCOUNTING"):
        runner().build_report(
            cases,
            source_digest=sha,
            observations=bundle(cases, sha, restart_state=state, dispatch_count=0),
        )


def test_fixture_report_preserves_safe_subgroups_without_raw_evidence():
    path = FIXTURES / "cases.json"
    sha = digest(path.read_bytes())
    cases = runner().load_units(path, expected_digest=sha, fixtures=True)
    report = runner().build_report(cases, source_digest=sha)
    assert {row["fixture_provenance"] for row in report["cases"]} == {
        "synthetic-development-control"
    }
    assert {row["boundary"] for row in report["cases"]} == {
        "beginning",
        "middle",
        "end",
        "between_evidence",
    }
    assert {group["dimension"] for group in report["subgroups"]} == {"family", "boundary", "length"}
    assert all(group["metrics"] is None for group in report["subgroups"])
    for dimension in ("family", "boundary", "length"):
        assert (
            sum(
                group["population"]["total"]
                for group in report["subgroups"]
                if group["dimension"] == dimension
            )
            == 16
        )
    assert max(row["input_characters"] for row in report["cases"]) > 10000
    assert "KNORA_P1_SYNTHETIC_CANARY" not in json.dumps(report)
