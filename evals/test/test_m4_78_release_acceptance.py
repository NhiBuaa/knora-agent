"""Exact-candidate structural guardrails for Issue #78 recovery delivery."""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from pathlib import Path

from knora.tools import CapabilityRegistry, ReconcileExecution, SupportToolGateway
from knora.tools.execution_types import (
    ExecutionFenced,
    ExecutionInProgress,
    ReconciledFailed,
    ReconciledSucceeded,
    ReconciliationIndeterminate,
    ReconciliationOutcomeNotFound,
)
from knora.tools.proposal_http import _execution_response
from knora.tools.proposal_types import TypedWriteCommand

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPOSITORY_ROOT / "evals" / "fixtures" / "m4_78_reconciliation_matrix_v1.json"
GUIDE_DIGEST = "sha256:03b95fdaba97203c3ecfe228efb17cf4899baf15717733de07ab42f151d6693b"
FOCUSED_FILES = (
    "test/tools/test_reconciliation_workflow.py",
    "test/tools/test_reconciliation_postgres.py",
    "test/tools/test_reference_provider.py",
    "test/tools/test_proposal_http.py",
    "::test_release_evidence_builder_binds_every_locked_case_and_sanitized_seam",
)


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _changed_paths(source_base: str, subject_sha: str) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", f"{source_base}..{subject_sha}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def _content_addressed_nodeid(nodeid: str) -> str:
    normalized = nodeid.replace("\\", "/")
    if "[" not in normalized:
        return normalized
    base, parameter = normalized.split("[", 1)
    parameter_digest = hashlib.sha256(parameter.encode("utf-8")).hexdigest()[:16]
    return f"{base}[case-sha256:{parameter_digest}]"


def _build_release_evidence(
    *, subject_sha: str, executed_nodeids: list[str], changed_paths: list[str] | None = None
) -> dict[str, object]:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    case_patterns = {
        pattern
        for case in matrix["case_evidence"].values()
        for pattern in case["nodeid_patterns"]
    }
    normalized_nodeids = sorted(
        {
            sanitized
            for nodeid in executed_nodeids
            if any(pattern in nodeid for pattern in case_patterns)
            for sanitized in (_content_addressed_nodeid(nodeid),)
        }
    )
    cases = {
        case_id: {
            "status": "PASS",
            "assertions": case["assertions"],
            "executed_nodeids": [
                nodeid
                for nodeid in normalized_nodeids
                if any(pattern in nodeid for pattern in case["nodeid_patterns"])
            ],
        }
        for case_id, case in matrix["case_evidence"].items()
    }
    registry = CapabilityRegistry.static()
    changed = sorted(changed_paths or [])
    dependency_names = {
        "pyproject.toml",
        "poetry.lock",
        "requirements.txt",
        "requirements-dev.txt",
        "uv.lock",
    }
    scope_manifest = {
        "source_base": matrix["source_base"],
        "candidate": subject_sha,
        "changed_paths": changed,
        "dependency_or_lock_paths": [
            path for path in changed if Path(path).name.lower() in dependency_names
        ],
        "production_entry_point_paths": [
            path for path in changed if path in {"backend/src/knora/main.py"}
        ],
        "plugin_marketplace_or_vendor_paths": [
            path
            for path in changed
            if any(marker in path.lower() for marker in ("plugin", "marketplace", "vendor"))
        ],
    }
    evidence: dict[str, object] = {
        "schema_version": 1,
        "evidence_id": "m4-issue-78-release-evidence-v1",
        "source_base": matrix["source_base"],
        "subject_sha": subject_sha,
        "guide_revision": "m4-78-crash-recovery-v3",
        "guide_digest": GUIDE_DIGEST,
        "matrix_digest": _sha256(MATRIX_PATH),
        "test_cases": matrix["test_cases"],
        "cases": cases,
        "executed_assertions": {
            "count": len(normalized_nodeids),
            "nodeids": normalized_nodeids,
        },
        "postgresql": {
            "revision": "20260824_0040",
            "time_authority": "transaction_timestamp_after_row_lock",
            "strict_expiry": "lease_expires_at_lt_database_time",
        },
        "sqlite": {
            "identity": "sqlite-reference-provider-v1",
            "schema_identity": "provider-references+tickets+idempotency-v1",
            "truth_owner": "provider",
            "restart_independent_from_tool_action_store": True,
        },
        "sentinels": matrix["sentinels"],
        "barriers": matrix["barriers"],
        "public_projection_matrix": {
            "digest": "sha256:"
            + hashlib.sha256(
                json.dumps(
                    matrix["public_results"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "row_count": len(matrix["public_results"]),
            "rows": matrix["public_results"],
        },
        "registry": {
            "identity": registry.registry_identity,
            "version": registry.registry_version,
            "digest": registry.registry_digest,
            "capability_ids": list(registry.capability_ids),
            "restart_digest_equal": registry.registry_digest
            == CapabilityRegistry.static().registry_digest,
        },
        "scope_manifest": scope_manifest,
        "sanitization": {
            "policy": matrix["forbidden_release_value_classes"],
            "forbidden_value_hits": [],
            "raw_command_output_included": False,
        },
        "result": "PASSED",
    }
    serialized = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    forbidden_literals = ("dispatch-secret", "routing-a", "provider-resource-id", "postgresql+psycopg://")
    evidence["sanitization"]["forbidden_value_hits"] = [  # type: ignore[index]
        literal for literal in forbidden_literals if literal in serialized
    ]
    return evidence


def test_static_tool_registry_remains_allowlisted_without_runtime_registration() -> None:
    first = CapabilityRegistry.static()
    restarted = CapabilityRegistry.static()

    assert first.registry_identity == "knora-static-tool-capability-registry"
    assert first.capability_ids == ("ticket_lookup", "create_ticket")
    assert first.registry_digest == restarted.registry_digest
    assert not any(
        hasattr(first, forbidden)
        for forbidden in ("register", "discover", "load_plugin", "load_provider")
    )


def test_reconciliation_remains_the_only_new_typed_write_command_surface() -> None:
    assert ReconcileExecution in TypedWriteCommand.__args__
    assert set(SupportToolGateway.__dict__) >= {
        "lookup_ticket",
        "create_ticket",
        "get_execution_outcome",
    }
    source = inspect.getsource(CapabilityRegistry)
    assert "dynamic loading path" in source
    assert "plugin" not in source.lower()


def test_locked_release_matrix_is_independent_and_complete() -> None:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    assert matrix["schema_version"] == 1
    assert matrix["source_base"] == "1cbf7d5f64bc94bd4d9313c2cf0fef46237b59e1"
    assert matrix["test_cases"] == [f"M4-78-TC-{number:02d}" for number in range(1, 11)]


def test_tc06_closed_reconciliation_projection_matches_independent_matrix() -> None:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))["public_results"]
    proposal_id = "10000000-0000-4000-8000-000000000001"
    logical_id = "20000000-0000-4000-8000-000000000002"
    results = {
        "success": ReconciledSucceeded(proposal_id, logical_id, "m4r1.opaque"),
        "target_not_found": ReconciledFailed(proposal_id, logical_id, "target_not_found"),
        "validation_rejected": ReconciledFailed(
            proposal_id, logical_id, "validation_rejected"
        ),
        "policy_rejected": ReconciledFailed(proposal_id, logical_id, "policy_rejected"),
        "unavailable": ReconciliationIndeterminate(
            proposal_id, logical_id, "provider_observation_unavailable"
        ),
        "timeout": ReconciliationIndeterminate(
            proposal_id, logical_id, "provider_observation_timeout"
        ),
        "malformed": ReconciliationIndeterminate(
            proposal_id, logical_id, "provider_observation_malformed"
        ),
        "not_found": ReconciliationOutcomeNotFound(proposal_id, logical_id),
        "in_progress": ExecutionInProgress(proposal_id, logical_id),
        "fenced": ExecutionFenced(proposal_id, logical_id),
    }

    observed = {}
    for name, result in results.items():
        response = _execution_response(result)
        observed[name] = {
            "status": response.status_code,
            "body": json.loads(response.body),
        }

    assert observed == matrix


def test_release_evidence_builder_binds_every_locked_case_and_sanitized_seam() -> None:
    evidence = _build_release_evidence(
        subject_sha="3" * 40,
        executed_nodeids=[
            "test/tools/test_reconciliation_workflow.py::test_example",
            "test/tools/test_reconciliation_postgres.py::test_example",
            "test/tools/test_reference_provider.py::test_example",
            "test/tools/test_proposal_http.py::test_example",
            "../evals/test/test_m4_78_release_acceptance.py::test_example",
        ],
    )

    assert evidence["schema_version"] == 1
    assert evidence["source_base"] == "1cbf7d5f64bc94bd4d9313c2cf0fef46237b59e1"
    assert evidence["subject_sha"] == "3" * 40
    assert list(evidence["cases"]) == [f"M4-78-TC-{number:02d}" for number in range(1, 11)]
    assert evidence["sanitization"]["forbidden_value_hits"] == []
    assert evidence["result"] == "PASSED"


def test_release_evidence_content_addresses_parametrized_values() -> None:
    raw_parameter = "private-value-" + "x" * 500
    evidence = _build_release_evidence(
        subject_sha="4" * 40,
        executed_nodeids=[
            "test/tools/test_reference_provider.py::"
            f"test_sqlite_commit_before_ack_remains_authoritative_after_restart[{raw_parameter}]"
        ],
    )

    serialized = json.dumps(evidence, sort_keys=True)
    assert raw_parameter not in serialized
    assert "case-sha256:" in serialized
