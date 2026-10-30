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


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_dry_run_success(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    cutoff = (now + timedelta(minutes=50)).isoformat()
    hard_deadline = (now + timedelta(minutes=55)).isoformat()
    proj = "knora-figma-e2e-session-dryrun-success"

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
            "-DryRunFaultTest",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "DRY_RUN_FAULT_RECEIPT=" in res.stdout

    receipt_path = ROOT / f"frontend/test-results/{proj}/task8-supervision-receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    assert receipt["schemaVersion"] == 1
    assert receipt["mode"] == "dry-run-fault-test"
    assert receipt["project"] == proj
    assert receipt["status"] == "SUCCESS"

    # Cleanup test output
    shutil.rmtree(ROOT / f"frontend/test-results/{proj}", ignore_errors=True)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_simulated_timeout_terminates_cleanly(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    cutoff = (now + timedelta(minutes=50)).isoformat()
    hard_deadline = (now + timedelta(minutes=55)).isoformat()
    proj = "knora-figma-e2e-session-dryrun-timeout"

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
            "-DryRunFaultTest",
            "-SimulateTimeout",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    assert "TIMEOUT_STOP_SIMULATED" in res.stderr

    receipt_path = ROOT / f"frontend/test-results/{proj}/task8-supervision-receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    assert receipt["schemaVersion"] == 1
    assert receipt["mode"] == "dry-run-fault-test"
    assert receipt["project"] == proj
    assert receipt["childProcessKilled"] is True
    assert receipt["status"] == "TIMEOUT_CLEANUP_VERIFIED"

    # Cleanup test output
    shutil.rmtree(ROOT / f"frontend/test-results/{proj}", ignore_errors=True)
