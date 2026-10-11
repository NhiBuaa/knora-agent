"""Release evidence must be complete and bound to one tested commit."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from runtime_evidence import create_evidence, validate_release  # noqa: E402

SHA = "a" * 40
WORKFLOW_SHA = "b" * 40


def _report(path: Path, *, body: str = '<testcase classname="suite" name="case"/>') -> None:
    path.write_text(f'<testsuite tests="1">{body}</testsuite>', encoding="utf-8")


def _evidence(tmp_path: Path, profile: str = "application") -> Path:
    reports = {}
    scenarios = (
        ("identity", "documents", "conversations", "operator", "workspace")
        if profile == "application"
        else ("storage", "native")
    )
    for scenario in scenarios:
        path = tmp_path / f"{scenario}.xml"
        _report(path)
        reports[scenario] = path
    return create_evidence(
        subject_sha=SHA,
        actual_sha=SHA,
        workflow_sha=WORKFLOW_SHA,
        run_id="123",
        run_attempt="1",
        profile=profile,
        reports=reports,
        output_dir=tmp_path / profile,
        started_at="2026-10-11T12:00:00Z",
        tool_identities={"python": "3.12"},
        image_identities={"keycloak": "26.3.3"},
    )


def test_release_accepts_complete_exact_sha_evidence(tmp_path: Path) -> None:
    application = _evidence(tmp_path)
    otp = _evidence(tmp_path, "otp")
    validate_release(SHA, [application, otp], ["application", "otp"])


@pytest.mark.parametrize("subject,actual", [("short", SHA), (SHA, "c" * 40)])
def test_record_rejects_invalid_or_mismatched_actual_sha(
    tmp_path: Path, subject: str, actual: str
) -> None:
    report = tmp_path / "identity.xml"
    _report(report)
    with pytest.raises(ValueError, match="SHA"):
        create_evidence(
            subject_sha=subject,
            actual_sha=actual,
            workflow_sha=WORKFLOW_SHA,
            run_id="123",
            run_attempt="1",
            profile="application",
            reports={"identity": report},
            output_dir=tmp_path / "output",
            started_at="2026-10-11T12:00:00Z",
            tool_identities={"python": "3.12"},
            image_identities={"keycloak": "26.3.3"},
        )


def test_release_rejects_missing_requested_profile(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="otp"):
        validate_release(SHA, [_evidence(tmp_path)], ["application", "otp"])


@pytest.mark.parametrize("outcome", ["failure", "cancelled", "skipped", "unknown"])
def test_release_rejects_unsuccessful_outcome(tmp_path: Path, outcome: str) -> None:
    path = _evidence(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["outcome"] = outcome
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="outcome"):
        validate_release(SHA, [path], ["application"])


def test_release_rejects_changed_report_hash(tmp_path: Path) -> None:
    path = _evidence(tmp_path)
    report = path.parent / "reports" / "identity.xml"
    report.write_text(report.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        validate_release(SHA, [path], ["application"])


@pytest.mark.parametrize(
    "body", [None, "", '<testcase classname="suite" name="case"><skipped/></testcase>']
)
def test_record_rejects_missing_empty_or_skipped_xml(tmp_path: Path, body: str | None) -> None:
    path = tmp_path / "identity.xml"
    if body is not None:
        _report(path, body=body)
    reports = {
        scenario: tmp_path / f"{scenario}.xml"
        for scenario in ("identity", "documents", "conversations", "operator", "workspace")
    }
    for _scenario, report in reports.items():
        if report != path:
            _report(report)
    if body is not None:
        _report(path, body=body)
    reports["identity"] = path
    with pytest.raises(ValueError, match="report|case|skip"):
        create_evidence(
            subject_sha=SHA,
            actual_sha=SHA,
            workflow_sha=WORKFLOW_SHA,
            run_id="123",
            run_attempt="1",
            profile="application",
            reports=reports,
            output_dir=tmp_path / "output",
            started_at="2026-10-11T12:00:00Z",
            tool_identities={"python": "3.12"},
            image_identities={"keycloak": "26.3.3"},
        )


def test_release_rejects_other_sha(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="SHA"):
        validate_release("c" * 40, [_evidence(tmp_path)], ["application"])


def test_release_rejects_narrow_scenario_selection(tmp_path: Path) -> None:
    path = _evidence(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["selected_scenarios"].pop()
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="scenario"):
        validate_release(SHA, [path], ["application"])


def test_record_sanitizes_junit_output_and_case_names(tmp_path: Path) -> None:
    reports = {}
    for scenario in ("identity", "documents", "conversations", "operator", "workspace"):
        report = tmp_path / f"{scenario}.xml"
        _report(
            report,
            body='<testcase classname="secret-user" name="auth-url-token">'
            '<system-out>private@example.test</system-out></testcase>',
        )
        reports[scenario] = report
    path = create_evidence(
        subject_sha=SHA,
        actual_sha=SHA,
        workflow_sha=WORKFLOW_SHA,
        run_id="123",
        run_attempt="1",
        profile="application",
        reports=reports,
        output_dir=tmp_path / "output",
        started_at="2026-10-11T12:00:00Z",
        tool_identities={"python": "3.12"},
        image_identities={"keycloak": "26.3.3"},
    )
    published = (path.parent / "reports" / "identity.xml").read_text(encoding="utf-8")
    assert "private@example.test" not in published
    assert "auth-url-token" not in published
    assert "secret-user" not in published
    validate_release(SHA, [path], ["application"])


@pytest.mark.parametrize(
    "field",
    [
        "workflow_source_sha",
        "run_id",
        "run_attempt",
        "started_at",
        "completed_at",
        "tool_identities",
        "image_identities",
    ],
)
def test_release_rejects_missing_provenance(tmp_path: Path, field: str) -> None:
    path = _evidence(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop(field)
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        validate_release(SHA, [path], ["application"])


@pytest.mark.parametrize(
    "xml",
    [
        '<testsuite tests="0"><testcase classname="x" name="y"/></testsuite>',
        '<testsuite failures="1"><testcase classname="x" name="y"/></testsuite>',
        '<testsuite skipped="1"><testcase classname="x" name="y"/></testsuite>',
        '<notjunit><testcase classname="x" name="y"/></notjunit>',
    ],
)
def test_record_rejects_invalid_suite_metadata(tmp_path: Path, xml: str) -> None:
    reports = {}
    for scenario in ("identity", "documents", "conversations", "operator", "workspace"):
        path = tmp_path / f"{scenario}.xml"
        _report(path)
        reports[scenario] = path
    reports["identity"].write_text(xml, encoding="utf-8")
    with pytest.raises(ValueError, match="report"):
        create_evidence(
            subject_sha=SHA,
            actual_sha=SHA,
            workflow_sha=WORKFLOW_SHA,
            run_id="123",
            run_attempt="1",
            profile="application",
            reports=reports,
            output_dir=tmp_path / "output",
            started_at="2026-10-11T12:00:00Z",
            tool_identities={"python": "3.12"},
            image_identities={"keycloak": "26.3.3"},
        )
