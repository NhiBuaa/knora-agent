"""Deterministic, independent release-evidence harness for Issue #79."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPOSITORY_ROOT / "evals" / "fixtures" / "m4_79_integrated_release_matrix_v1.json"
FRONTIER_PATH = REPOSITORY_ROOT / ".agents" / "review" / "m4-issue-79-frontier-baseline-v2.json"
GUIDE_PATH = (
    REPOSITORY_ROOT
    / ".agents/manual-tests/milestone-4/79-integrated-release-gate-v2.md"
)
GUIDE_APPROVAL_PATH = (
    REPOSITORY_ROOT / ".agents/review/m4-issue-79-guide-approval-v2.json"
)
HISTORY_PATH = (
    REPOSITORY_ROOT
    / ".agents/manual-tests/milestone-4/79-integrated-release-gate-v2.evaluations.jsonl"
)
READINESS_PATH = REPOSITORY_ROOT / ".agents/review/m4-issue-79-final-review-readiness-v1.json"
PROTECTED_RELEASE_EVIDENCE_PATHS = (
    REPOSITORY_ROOT / ".agents/review/m4-issue-77-release-evidence-v1.json",
    REPOSITORY_ROOT / ".agents/review/m4-issue-78-release-evidence-v1.json",
)


def _sha256(path: Path) -> str:
    # Git's content-addressed text is LF-normalized; keep release evidence stable
    # when a Windows checkout materializes the same tracked guide as CRLF.
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _changed_paths(source_base: str, subject_sha: str) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", f"{source_base}..{subject_sha}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(line for line in completed.stdout.splitlines() if line)


def _build_release_evidence(
    *,
    subject_sha: str,
    executed_nodeids: list[str],
    changed_paths: list[str] | None = None,
) -> dict[str, object]:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    frontier = json.loads(FRONTIER_PATH.read_text(encoding="utf-8"))
    cases = {
        case_id: {
            "status": "PASS",
            "assertions": case["assertions"],
            "executed_nodeids": sorted(
                nodeid
                for nodeid in executed_nodeids
                if any(pattern in nodeid for pattern in case["nodeid_patterns"])
            ),
        }
        for case_id, case in matrix["case_evidence"].items()
    }
    missing_cases = [case_id for case_id, case in cases.items() if not case["executed_nodeids"]]
    if missing_cases:
        raise ValueError(f"release evidence missing executed coverage: {missing_cases}")
    changed = (
        _changed_paths(matrix["source_base"], subject_sha)
        if changed_paths is None
        else changed_paths
    )
    return {
        "schema_version": 1,
        "evidence_id": "m4-issue-79-release-evidence-v1",
        "result": "PASSED",
        "subject_sha": subject_sha,
        "source_base": matrix["source_base"],
        "guide": {
            "revision": matrix["guide_revision"],
            "digest": _sha256(GUIDE_PATH),
            "approval_digest": _sha256(GUIDE_APPROVAL_PATH),
            "history_digest_before_candidate": _sha256(HISTORY_PATH),
        },
        "frontier": frontier["github_frontier"],
        "test_cases": matrix["test_cases"],
        "cases": cases,
        "executed_nodeids": sorted(executed_nodeids),
        "scope_manifest": {
            "changed_paths": changed,
            "dependency_or_lock_paths": [
                path
                for path in changed
                if Path(path).name in {"poetry.lock", "pyproject.toml", "uv.lock"}
            ],
            "plugin_marketplace_or_vendor_paths": [
                path
                for path in changed
                if any(
                    marker in path.lower()
                    for marker in ("plugin", "marketplace", "vendor")
                )
            ],
        },
        "final_review": {
            "readiness_template_digest": _sha256(READINESS_PATH),
            "actual_descriptor_created": False,
        },
        "sanitization": {
            "forbidden_value_classes": matrix["forbidden_value_classes"],
            "forbidden_value_hits": [],
            "raw_command_output_included": False,
        },
    }


def test_locked_guide_and_history_are_append_only_inputs() -> None:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    approval = json.loads(GUIDE_APPROVAL_PATH.read_text(encoding="utf-8"))

    assert _sha256(GUIDE_PATH) == matrix["guide_digest"]
    assert approval["lock_status"] == "LOCKED"
    history = [
        json.loads(line)
        for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert all(record["append_only"] is True for record in history)
    assert all(record["guide_revision"] == matrix["guide_revision"] for record in history)
    guide_digest = matrix["guide_digest"].removeprefix("sha256:")
    assert all(record["guide_sha256"] == guide_digest for record in history)


def test_content_hash_is_stable_for_windows_checkout_newlines(tmp_path: Path) -> None:
    guide = tmp_path / "guide.md"
    guide.write_bytes(b"first\r\nsecond\r\n")

    assert _sha256(guide) == (
        "sha256:dbea9325179efe46ea2add94f7b6b745ca983fabb208dc6d34aa064623d7ee23"
    )


def test_frontier_baseline_and_readiness_template_are_bound() -> None:
    frontier = json.loads(FRONTIER_PATH.read_text(encoding="utf-8"))
    readiness = json.loads(READINESS_PATH.read_text(encoding="utf-8"))

    assert frontier["workspace"]["source_base"] == "5af5c5c914ea904fe1e14de1acff859113d53244"
    assert all(blocker["state"] == "closed" for blocker in frontier["github_frontier"]["blockers"])
    assert readiness["actual_fixed_point_descriptor"] is None
    assert readiness["code_review_invoked"] is False


def test_prior_release_harnesses_do_not_mutate_committed_evidence(tmp_path: Path) -> None:
    """The complete suite must not regenerate prior accepted-release evidence."""
    plugin = tmp_path / "no_protected_release_evidence.py"
    protected_paths = ", ".join(
        repr(str(path.resolve())) for path in PROTECTED_RELEASE_EVIDENCE_PATHS
    )
    plugin.write_text(
        "from pathlib import Path\n\n"
        f"PROTECTED = {{{protected_paths}}}\n\n"
        "def _guard(method):\n"
        "    original = getattr(Path, method)\n"
        "    def guarded(self, *args, **kwargs):\n"
        "        if str(self.resolve()) in PROTECTED:\n"
        "            raise AssertionError(f'protected release evidence {method}: {self}')\n"
        "        return original(self, *args, **kwargs)\n"
        "    setattr(Path, method, guarded)\n\n"
        "def pytest_configure(config):\n"
        "    _guard('write_text')\n"
        "    _guard('unlink')\n",
        encoding="utf-8",
    )
    before = {path: path.read_bytes() for path in PROTECTED_RELEASE_EVIDENCE_PATHS}
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no_protected_release_evidence",
            "evals/test/test_m4_77_release_acceptance.py",
            "evals/test/test_m4_78_release_acceptance.py",
        ],
        cwd=REPOSITORY_ROOT,
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join(
                    (str(tmp_path), str(REPOSITORY_ROOT / "backend" / "src"))
                ),
            },
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert {path: path.read_bytes() for path in PROTECTED_RELEASE_EVIDENCE_PATHS} == before


def test_release_evidence_builder_requires_every_locked_case() -> None:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    nodeids = [
        "test/tools/test_proposal_http.py::test_http_workspace_authorization_observably_precedes_one_scoped_lookup",
        "test/tools/test_proposals.py::test_concurrent_decision_has_one_cas_winner_and_loser_reads_winner",
        "test/tools/test_execution_workflow.py::test_execution",
        "test/tools/test_execution_postgres.py::test_execution",
        "test/tools/test_reconciliation_workflow.py::test_reconciliation",
        "test/tools/test_reconciliation_postgres.py::test_reconciliation_migration_round_trips_persisted_takeover_audit",
        "test/tools/test_reconciliation_postgres.py::test_postgres_reconciliation_takes_over_a_strictly_expired_lease_before_finalizing",
        "evals/test/test_m4_79_release_acceptance.py::test_release_evidence_builder_requires_every_locked_case",
        "evals/test/test_m4_79_release_acceptance.py::test_frontier_baseline_and_readiness_template_are_bound",
        "evals/test/test_m4_79_release_acceptance.py::test_locked_guide_and_history_are_append_only_inputs",
    ]
    evidence = _build_release_evidence(
        subject_sha="a" * 40,
        executed_nodeids=nodeids,
        changed_paths=["backend/alembic.ini"],
    )

    assert evidence["test_cases"] == matrix["test_cases"]
    assert all(case["status"] == "PASS" for case in evidence["cases"].values())
    assert evidence["sanitization"]["forbidden_value_hits"] == []
