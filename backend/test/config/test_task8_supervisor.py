from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
ROOT = Path(__file__).resolve().parents[3]
SUPERVISOR_SCRIPT = ROOT / "scripts/supervise-task8.ps1"


def _is_process_running(pid: int) -> bool:
    res = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    return str(pid) in res.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_stub_success(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    cutoff = (now + timedelta(minutes=50)).isoformat()
    hard_deadline = (now + timedelta(minutes=55)).isoformat()
    proj = "knora-figma-e2e-session-stub-success"

    res = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(SUPERVISOR_SCRIPT),
            "-AbsoluteCutoff",
            cutoff,
            "-HardDeadline",
            hard_deadline,
            "-ProjectName",
            proj,
            "-StubMode",
            "Success",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "SUPERVISION_RECEIPT=" in res.stdout

    receipt_path = ROOT / f"frontend/test-results/{proj}/task8-supervision-receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    assert receipt["schemaVersion"] == 1
    assert receipt["project"] == proj
    assert receipt["workerFinishedCleanly"] is True
    assert receipt["status"] == "SUCCESS"

    mig_receipt_path = ROOT / f"frontend/test-results/{proj}/migration-cycle-receipt.json"
    assert mig_receipt_path.exists()
    mig_receipt = json.loads(mig_receipt_path.read_text(encoding="utf-8-sig"))
    assert mig_receipt["cycleCompleted"] is True
    assert len(mig_receipt["steps"]) == 5

    shutil.rmtree(ROOT / f"frontend/test-results/{proj}", ignore_errors=True)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_real_cutoff_terminates_child_and_grandchild_tree(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    # Real short deadline: 3 seconds cutoff!
    cutoff = (now + timedelta(seconds=3)).isoformat()
    hard_deadline = (now + timedelta(minutes=5)).isoformat()
    proj = "knora-figma-e2e-session-stub-timeout"

    res = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(SUPERVISOR_SCRIPT),
            "-AbsoluteCutoff",
            cutoff,
            "-HardDeadline",
            hard_deadline,
            "-ProjectName",
            proj,
            "-StubMode",
            "HangRunner",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    assert "WHOLE_PACKAGE_TIMEOUT_CUTOFF" in res.stderr or "TIMEOUT" in res.stdout

    receipt_path = ROOT / f"frontend/test-results/{proj}/task8-supervision-receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    assert receipt["schemaVersion"] == 1
    assert receipt["project"] == proj
    assert receipt["childProcessesKilled"] is True
    assert receipt["status"] == "TIMEOUT_CLEANUP_VERIFIED"
    assert receipt["workerPid"] is not None

    # Postcondition: Assert the worker process is completely dead in the OS process table
    worker_pid = receipt["workerPid"]
    assert not _is_process_running(worker_pid)

    shutil.rmtree(ROOT / f"frontend/test-results/{proj}", ignore_errors=True)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_remaining_time_guard_rejects_insufficient_time(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    # 30 minutes = 1800s, less than required 2580s
    cutoff = (now + timedelta(minutes=30)).isoformat()
    hard_deadline = (now + timedelta(minutes=35)).isoformat()
    proj = "knora-figma-e2e-session-insufficient"

    res = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(SUPERVISOR_SCRIPT),
            "-AbsoluteCutoff",
            cutoff,
            "-HardDeadline",
            hard_deadline,
            "-ProjectName",
            proj,
            "-AllowDirty",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    assert "INSUFFICIENT_TIME_FOR_WHOLE_PACKAGE" in res.stderr
