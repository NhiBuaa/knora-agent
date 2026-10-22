"""CI selection and result gates reject missing execution evidence."""

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.ci_checks import required_jobs_succeeded, validate_reports

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("ci_pytest_plugin", ROOT / "conftest.py")
assert spec and spec.loader
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
ci_route = plugin.ci_route
RUNTIME_NODES = plugin.RUNTIME_NODES
JOBS = ("frontend", "backend", "database", "keycloak")
SHADOW_FILES = (
    "evals/test/test_security_shadow.py",
    "evals/test/test_cloudflare_p1_shadow.py",
    "evals/test/test_cloudflare_p1_trial.py",
    "evals/test/test_cloudflare_dangerous_output.py",
    "evals/test/test_security_outcomes.py",
    "evals/test/test_security_outcomes_runner.py",
    "evals/test/test_workbench_security_projection.py",
    "evals/integration/test_security_shadow_integration.py",
)


def report(tmp_path: Path, body: str, name: str = "report.xml") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


GOOD = (
    '<testsuite tests="1" failures="0" errors="0" skipped="0">'
    '<testcase classname="Suite" name="case"/></testsuite>'
)


def test_valid_report_has_executed_case(tmp_path: Path) -> None:
    assert validate_reports([report(tmp_path, GOOD)]) == 1


@pytest.mark.parametrize("outcome", ("failure", "error", "skipped"))
def test_nonpassing_case_is_rejected(tmp_path: Path, outcome: str) -> None:
    xml = (
        '<testsuite tests="1"><testcase classname="Suite" name="case">'
        f"<{outcome}>secret output</{outcome}></testcase></testsuite>"
    )
    with pytest.raises(ValueError, match="Suite.case"):
        validate_reports([report(tmp_path, xml)])


def test_empty_report_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="zero test cases"):
        validate_reports([report(tmp_path, '<testsuite tests="0"/>')])


def test_missing_report_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing report"):
        validate_reports([tmp_path / "absent.xml"])


def test_malformed_report_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="malformed report"):
        validate_reports([report(tmp_path, "<testsuite")])


def test_duplicate_case_across_reports_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicate test case"):
        validate_reports([report(tmp_path, GOOD, "one.xml"), report(tmp_path, GOOD, "two.xml")])


def test_declared_counts_must_match_cases(tmp_path: Path) -> None:
    xml = GOOD.replace('tests="1"', 'tests="2"')
    with pytest.raises(ValueError, match="inconsistent counts"):
        validate_reports([report(tmp_path, xml)])


def test_report_cli_never_echoes_captured_output(tmp_path: Path) -> None:
    xml = (
        '<testsuite><testcase classname="Suite" name="case">'
        "<failure>private-token</failure><system-out>private-token</system-out>"
        "</testcase></testsuite>"
    )
    path = report(tmp_path, xml)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ci_checks.py"), "reports", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Suite.case" in result.stderr
    assert "private-token" not in result.stdout + result.stderr


def test_report_cli_prints_safe_case_identity(tmp_path: Path) -> None:
    path = report(tmp_path, GOOD)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ci_checks.py"), "reports", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "CASE Suite.case" in result.stdout


def test_all_required_jobs_succeed() -> None:
    assert required_jobs_succeeded({name: {"result": "success"} for name in JOBS})


@pytest.mark.parametrize("job", JOBS)
@pytest.mark.parametrize("result", ("failure", "cancelled", "skipped"))
def test_required_job_non_success_is_rejected(job: str, result: str) -> None:
    needs = {name: {"result": "success"} for name in JOBS}
    needs[job]["result"] = result
    assert required_jobs_succeeded(needs) is False


@pytest.mark.parametrize("job", JOBS)
def test_missing_or_unknown_job_is_rejected(job: str) -> None:
    needs = {name: {"result": "success"} for name in JOBS}
    assert required_jobs_succeeded({key: val for key, val in needs.items() if key != job}) is False
    assert required_jobs_succeeded({**needs, "extra": {"result": "success"}}) is False
    assert required_jobs_succeeded({**needs, "format": {"result": "success"}}) is False


def test_jobs_cli_rejects_malformed_json(tmp_path: Path) -> None:
    env = {**os.environ, "CI_NEEDS": "{invalid"}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ci_checks.py"), "jobs"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert "{invalid" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("node", "expected"),
    (
        ("backend/test/answering/test_module.py::test_answer", "backend"),
        ("backend/test/config/test_keycloak_theme.py::test_theme", "backend"),
        ("backend/test/adapters/cli/test_ollama_trace_gate.py::test_trace", "backend"),
        ("backend/test/adapters/postgres/test_ingestion_store.py::test_store", "database"),
        ("backend/test/adapters/http/test_ingestion.py::test_http", "database"),
        ("backend/test/adapters/http/test_questions.py::test_http", "database"),
        ("backend/test/adapters/cli/test_ingest.py::test_cli", "database"),
        ("backend/test/adapters/cli/test_ingestion_worker.py::test_worker", "database"),
        ("backend/test/ingestion/test_issue_19_application_e2e.py::test_e2e", "database"),
        (
            "backend/test/providers/openai_compatible/test_application_integration.py::test_app",
            "database",
        ),
        ("backend/test/tools/test_execution_postgres.py::test_tool", "database"),
        ("backend/test/tools/test_proposal_postgres.py::test_tool", "database"),
        ("backend/test/tools/test_reconciliation_postgres.py::test_tool", "database"),
        ("backend/test/adapters/cli/test_dev_launcher.py::test_launcher", "windows"),
        ("backend/test/adapters/cli/test_ollama_launcher.py::test_launcher", "windows"),
        ("backend/test/config/test_keycloak_email_otp.py::test_acl", "windows"),
        ("backend/test/adapters/pdf/test_pypdf.py::test_child_eof", "windows"),
        (
            "backend/test/evaluation/test_datasets.py::test_upload_prepares_real_pdf_without_activation",
            "windows",
        ),
        (
            "backend/test/evaluation/test_datasets.py::test_invalid_or_scanned_pdf_remains_explicit",
            "windows",
        ),
        (
            "backend/test/evaluation/test_datasets.py::test_processing_source_can_be_retried_after_interruption",
            "windows",
        ),
        (
            "backend/test/evaluation/test_gold_review.py::test_anchored_offsets_must_match_exact_extraction_snapshot",
            "windows",
        ),
        (
            "backend/test/evaluation/test_pdf_workflow.py::test_retained_pdf_to_reviewed_gold_to_new_observations_and_report",
            "windows",
        ),
        (
            "backend/test/ingestion/test_s2_upload_population.py::test_upload_manifest_matches_the_real_pdf_and_measured_counter_evidence",
            "windows",
        ),
        (
            "backend/test/test_s2_http_admission.py::test_windows_worker_environment_uses_owned_endpoints_and_discards_ambient_settings",
            "windows",
        ),
        (
            "backend/test/test_s2_http_admission.py::test_application_admission_pins_local_daemon_and_owned_container[None]",
            "backend",
        ),
        ("evals/test/test_process_probe.py::test_probe", "windows"),
        ("evals/test/test_ollama_process_probe.py::test_probe", "windows"),
        (
            "backend/test/adapters/cli/test_ingestion_worker.py::test_memory_probe_blocks_a_child_that_exceeds_256_mib",
            "windows",
        ),
        (
            "backend/test/adapters/pdf/test_pypdf.py::test_windows_job_object_peak_memory_is_classified_as_extractor_memory",
            "windows",
        ),
        ("evals/test/test_ollama_grounding.py::test_real_ollama_synthetic_grounding", "runtime"),
        (
            "backend/test/adapters/pdf/test_pypdf.py::test_locked_baseline_raw_and_page_boundaries",
            "runtime",
        ),
        (
            "backend/test/adapters/pdf/test_pypdf.py::test_locked_baseline_stream_boundaries",
            "runtime",
        ),
        (
            "backend/test/adapters/pdf/test_pypdf.py::"
            "test_locked_baseline_timeout_and_memory_ceiling_keep_parent_healthy",
            "runtime",
        ),
    ),
)
def test_ci_routes_real_node(node: str, expected: str) -> None:
    assert ci_route(node) == expected


@pytest.mark.parametrize("file", SHADOW_FILES)
def test_shadow_nodes_have_an_independent_partition(file: str) -> None:
    assert ci_route(f"{file}::test_contract") == "security-shadow"
    assert ci_route(f"{file}::test_contract".replace("/", "\\")) == "security-shadow"


@pytest.mark.parametrize("suite", ("backend", "windows", "database", "security-shadow"))
def test_ci_partition_never_imports_other_surface(tmp_path: Path, suite: str) -> None:
    (tmp_path / "conftest.py").write_bytes((ROOT / "conftest.py").read_bytes())
    (tmp_path / "pytest.ini").write_bytes((ROOT / "pytest.ini").read_bytes())
    package = tmp_path / "backend/src/knora"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    ordinary = {
        "backend": "backend/test/answering/test_module.py",
        "windows": "evals/test/test_process_probe.py",
        "database": "backend/test/adapters/postgres/test_store.py",
    }
    selected_files = set(SHADOW_FILES) if suite == "security-shadow" else {ordinary[suite]}
    for file in (*ordinary.values(), *SHADOW_FILES):
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        # A cross-surface import fails collection before any test can be deselected.
        body = (
            "raise RuntimeError('wrong surface imported')\n"
            if (file in SHADOW_FILES) != (suite == "security-shadow")
            else "def test_contract():\n    assert True\n"
        )
        path.write_text(body, encoding="utf-8")
    selection = tmp_path / "selection.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:deepeval",
            "--rootdir=.",
            "--collect-only",
            "-q",
            "backend/test",
            "evals/test",
            "evals/integration",
            f"--ci-suite={suite}",
            f"--ci-selection={selection}",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(selection.read_text(encoding="utf-8"))
    assert set(data["selected"]) == {f"{file}::test_contract" for file in selected_files}
    assert set(data["selected"]).isdisjoint(data["deselected"])


def test_jobs_cli_accepts_only_complete_success_object() -> None:
    env = {**os.environ, "CI_NEEDS": json.dumps({name: {"result": "success"} for name in JOBS})}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ci_checks.py"), "jobs"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0


def test_collected_ci_partitions_cover_default_collection(tmp_path: Path) -> None:
    """Required and runtime partitions retain every non-research node exactly once."""

    def collect(*args: str) -> set[str]:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--rootdir=.", "--collect-only", "-q", *args],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "backend/src")},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return {
            line
            for line in result.stdout.splitlines()
            if re.match(r"^(?:backend|evals)/.+::", line)
        }

    # Research modules must not be imported by the required collection gate either.
    full = collect("backend/test", "evals/test", *(f"--ignore={file}" for file in SHADOW_FILES))
    selected: dict[str, set[str]] = {}
    for suite in ("backend", "windows", "database"):
        selection = tmp_path / f"{suite}.json"
        assert not selection.exists()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--rootdir=.",
                "--collect-only",
                "-q",
                "backend/test",
                "evals/test",
                f"--ci-suite={suite}",
                f"--ci-selection={selection}",
            ],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "backend/src")},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(selection.read_text(encoding="utf-8"))
        assert data["suite"] == suite
        selected[suite] = set(data["selected"])
        assert selected[suite].isdisjoint(data["deselected"])
        assert selected[suite] | set(data["deselected"]) == full
        assert all(node.split("::", 1)[0] not in SHADOW_FILES for node in selected[suite])

    assert set.union(*selected.values()).isdisjoint(RUNTIME_NODES)
    assert set.union(*selected.values(), RUNTIME_NODES) == full
    assert all(
        selected[left].isdisjoint(selected[right])
        for left in selected
        for right in selected
        if left != right
    )
