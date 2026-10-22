"""Explicit, opt-in pytest partitions for required and research CI jobs."""

import json
from pathlib import Path

import pytest

SECURITY_SHADOW_FILES = {
    "evals/test/test_security_shadow.py",
    "evals/test/test_cloudflare_p1_shadow.py",
    "evals/test/test_cloudflare_p1_trial.py",
    "evals/test/test_cloudflare_dangerous_output.py",
    "evals/test/test_security_outcomes.py",
    "evals/test/test_security_outcomes_runner.py",
    "evals/test/test_workbench_security_projection.py",
    "evals/integration/test_security_shadow_integration.py",
}

DATABASE_FILES = {
    "backend/test/adapters/cli/test_ingest.py",
    "backend/test/adapters/cli/test_ingestion_worker.py",
    "backend/test/adapters/http/test_ingestion.py",
    "backend/test/adapters/http/test_questions.py",
    "backend/test/ingestion/test_issue_19_application_e2e.py",
    "backend/test/providers/openai_compatible/test_application_integration.py",
    "backend/test/tools/test_execution_postgres.py",
    "backend/test/tools/test_proposal_postgres.py",
    "backend/test/tools/test_reconciliation_postgres.py",
}
WINDOWS_FILES = {
    "backend/test/adapters/cli/test_dev_launcher.py",
    "backend/test/adapters/cli/test_ollama_launcher.py",
    "backend/test/config/test_keycloak_email_otp.py",
    "backend/test/adapters/pdf/test_pypdf.py",
    "backend/test/ingestion/test_s2_upload_population.py",
    "evals/test/test_process_probe.py",
    "evals/test/test_ollama_process_probe.py",
}
WINDOWS_NODES = {
    # Real PDF extraction needs the Windows Job Object or delegated Linux cgroups.
    "backend/test/evaluation/test_datasets.py::test_upload_prepares_real_pdf_without_activation",
    "backend/test/evaluation/test_datasets.py::test_invalid_or_scanned_pdf_remains_explicit",
    "backend/test/evaluation/test_datasets.py::test_processing_source_can_be_retried_after_interruption",
    "backend/test/evaluation/test_gold_review.py::test_anchored_offsets_must_match_exact_extraction_snapshot",
    "backend/test/evaluation/test_pdf_workflow.py::test_retained_pdf_to_reviewed_gold_to_new_observations_and_report",
    "backend/test/test_s2_http_admission.py::test_windows_worker_environment_uses_owned_endpoints_and_discards_ambient_settings",
    "backend/test/adapters/cli/test_ingestion_worker.py::test_cli_preflight_proves_pdf_child_memory_limit",
    "backend/test/adapters/cli/test_ingestion_worker.py::test_memory_probe_rejects_missing_job_object_limit",
    "backend/test/adapters/cli/test_ingestion_worker.py::test_memory_probe_blocks_a_child_that_exceeds_256_mib",
}
RUNTIME_NODES = {
    "evals/test/test_ollama_grounding.py::test_real_ollama_synthetic_grounding",
    "backend/test/adapters/pdf/test_pypdf.py::test_locked_baseline_raw_and_page_boundaries",
    "backend/test/adapters/pdf/test_pypdf.py::test_locked_baseline_stream_boundaries",
    "backend/test/adapters/pdf/test_pypdf.py::test_locked_baseline_timeout_and_memory_ceiling_keep_parent_healthy",
}


def ci_route(nodeid: str) -> str:
    node = nodeid.replace("\\", "/")
    file = node.split("::", 1)[0]
    if file in SECURITY_SHADOW_FILES:
        return "security-shadow"
    if node in RUNTIME_NODES:
        return "runtime"
    if file in WINDOWS_FILES or node in WINDOWS_NODES:
        return "windows"
    if file.startswith("backend/test/adapters/postgres/") or file in DATABASE_FILES:
        return "database"
    return "backend"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--ci-suite", choices=("backend", "windows", "database", "security-shadow"))
    parser.addoption("--ci-selection", type=Path)


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    suite = config.getoption("--ci-suite")
    if suite and collection_path.is_file():
        relative = collection_path.relative_to(Path(__file__).parent).as_posix()
        is_shadow = relative in SECURITY_SHADOW_FILES
        # Isolate imports before collection, rather than only deselecting executed tests.
        if is_shadow != (suite == "security-shadow"):
            return True
    return None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    suite = config.getoption("--ci-suite")
    path = config.getoption("--ci-selection")
    if not suite:
        if path:
            raise pytest.UsageError("--ci-selection requires --ci-suite")
        return
    if not path:
        raise pytest.UsageError("--ci-suite requires --ci-selection")
    root = Path(__file__).parent
    selected, deselected = [], []
    for item in items:
        relative = item.path.relative_to(root).as_posix()
        suffix = item.nodeid.partition("::")[2]
        node = f"{relative}::{suffix}" if suffix else relative
        (selected if ci_route(node) == suite else deselected).append(item)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "suite": suite,
                "selected": [item.nodeid for item in selected],
                "deselected": [item.nodeid for item in deselected],
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)
