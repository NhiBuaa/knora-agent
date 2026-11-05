from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
WIN_POWERSHELL = shutil.which("powershell") or POWERSHELL
ROOT = Path(__file__).resolve().parents[3]
SUPERVISOR_SCRIPT = ROOT / "scripts/supervise-task8.ps1"


def _is_process_running(pid: int) -> bool:
    res = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    return str(pid) in res.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_stub_success(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    cutoff = (now + timedelta(minutes=50)).isoformat()
    hard_deadline = (now + timedelta(minutes=55)).isoformat()
    proj = f"knora-figma-e2e-session-stub-success-{uuid.uuid4().hex[:8]}"

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
            "-AllowDirty",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert res.returncode == 0
    assert "SUPERVISION_RECEIPT=" in res.stdout

    receipt_path = ROOT / f"frontend/test-results/{proj}/task8-supervision-receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    assert receipt["schemaVersion"] == 1
    assert receipt["project"] == proj
    assert receipt["workerFinishedCleanly"] is True
    assert receipt["cleanupVerified"] is True
    assert receipt["reservationReleased"] is True
    assert receipt["status"] == "SUCCESS"
    assert not Path(receipt["reservationPath"]).exists()

    mig_receipt_path = ROOT / f"frontend/test-results/{proj}/migration-cycle-receipt.json"
    assert mig_receipt_path.exists()
    mig_receipt = json.loads(mig_receipt_path.read_text(encoding="utf-8-sig"))
    assert mig_receipt["cycleCompleted"] is True
    assert len(mig_receipt["steps"]) == 5

    shutil.rmtree(ROOT / f"frontend/test-results/{proj}", ignore_errors=True)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_real_cutoff_terminates_child_and_grandchild_tree(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    cutoff = (now + timedelta(seconds=2)).isoformat()
    hard_deadline = (now + timedelta(seconds=10)).isoformat()
    proj = f"knora-figma-e2e-session-stub-timeout-{uuid.uuid4().hex[:8]}"

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
            "-AllowDirty",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert res.returncode != 0
    assert "WHOLE_PACKAGE_TIMEOUT_CUTOFF" in res.stderr or "TIMEOUT" in res.stdout

    receipt_path = ROOT / f"frontend/test-results/{proj}/task8-supervision-receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    assert receipt["schemaVersion"] == 1
    assert receipt["project"] == proj
    assert receipt["childProcessesKilled"] is True
    assert receipt["cleanupVerified"] is True
    assert receipt["reservationReleased"] is True
    assert receipt["withinHardDeadline"] is True
    assert receipt["status"] == "TIMEOUT_CLEANUP_VERIFIED"
    assert not Path(receipt["reservationPath"]).exists()

    # Postcondition: Assert ALL tracked PIDs (worker, child, grandchild) are completely dead
    tracked_pids = receipt["trackedPids"]
    assert len(tracked_pids) >= 2
    for pid in tracked_pids:
        assert not _is_process_running(pid), f"PID {pid} still running in OS process table"

    shutil.rmtree(ROOT / f"frontend/test-results/{proj}", ignore_errors=True)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_cleanup_failure_retains_reservation(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    cutoff = (now + timedelta(seconds=2)).isoformat()
    # 5 seconds hard deadline allows 3 seconds for bounded cleanup timeout
    hard_deadline = (now + timedelta(seconds=5)).isoformat()
    proj = f"knora-figma-e2e-session-cleanup-fail-{uuid.uuid4().hex[:8]}"

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
            "HangCleanup",
            "-AllowDirty",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert res.returncode != 0

    receipt_path = ROOT / f"frontend/test-results/{proj}/task8-supervision-receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    assert receipt["schemaVersion"] == 1
    assert receipt["status"] == "CLEANUP_FAILED_OR_INCOMPLETE"
    assert receipt["cleanupVerified"] is False
    assert receipt["reservationReleased"] is False
    assert "TIMEOUT" in (receipt["failureReason"] or "")

    # Postcondition: Reservation lock file MUST BE RETAINED on disk for inspection
    reservation_path = Path(receipt["reservationPath"])
    assert reservation_path.exists(), "Reservation lock must be retained when cleanup fails"
    reservation_content = json.loads(reservation_path.read_text(encoding="utf-8"))
    assert reservation_content["status"] == "RESERVED_CLEANUP_FAILED"

    # Cleanup retained test artifact
    reservation_path.unlink(missing_ok=True)
    shutil.rmtree(ROOT / f"frontend/test-results/{proj}", ignore_errors=True)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_fail_cleanup_exitcode_fails_cleanly(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    cutoff = (now + timedelta(seconds=2)).isoformat()
    hard_deadline = (now + timedelta(seconds=6)).isoformat()
    proj = f"knora-figma-e2e-session-fail-cleanup-{uuid.uuid4().hex[:8]}"

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
            "FailCleanup",
            "-AllowDirty",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert res.returncode != 0

    receipt_path = ROOT / f"frontend/test-results/{proj}/task8-supervision-receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    assert receipt["status"] == "CLEANUP_FAILED_OR_INCOMPLETE"
    assert receipt["cleanupVerified"] is False
    assert receipt["reservationReleased"] is False

    # Postcondition: Reservation lock file MUST BE RETAINED on disk
    reservation_path = Path(receipt["reservationPath"])
    assert reservation_path.exists()

    # Cleanup retained test artifact
    reservation_path.unlink(missing_ok=True)
    shutil.rmtree(ROOT / f"frontend/test-results/{proj}", ignore_errors=True)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_preserves_foreign_canonical_reservation_and_skips_teardown(
    tmp_path: Path,
) -> None:
    proj = f"knora-figma-e2e-session-foreign-{uuid.uuid4().hex[:8]}"
    foreign_lock = Path(tempfile.gettempdir(), f"knora-figma-reservation-{proj}.lock")
    foreign_bytes = b'{"owner": "foreign-process", "locked": true}'
    foreign_lock.write_bytes(foreign_bytes)

    now = datetime.now(UTC)
    cutoff = (now + timedelta(minutes=50)).isoformat()
    hard_deadline = (now + timedelta(minutes=55)).isoformat()

    try:
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
                "-AllowDirty",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert res.returncode != 0
        assert "CANONICAL_HARNESS_PROJECT_RESERVED" in res.stderr

        # Postcondition: The foreign lock MUST BE COMPLETELY UNTOUCHED AND PRESERVED!
        assert foreign_lock.exists()
        assert foreign_lock.read_bytes() == foreign_bytes
    finally:
        foreign_lock.unlink(missing_ok=True)
        shutil.rmtree(ROOT / f"frontend/test-results/{proj}", ignore_errors=True)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_preserves_foreign_supervisor_reservation(tmp_path: Path) -> None:
    proj = f"knora-figma-e2e-session-foreign-sup-{uuid.uuid4().hex[:8]}"
    foreign_sup_lock = Path(tempfile.gettempdir(), f"knora-session-supervisor-{proj}.lock")
    foreign_bytes = b'{"owner": "another-supervisor", "status": "ACTIVE"}'
    foreign_sup_lock.write_bytes(foreign_bytes)

    now = datetime.now(UTC)
    cutoff = (now + timedelta(minutes=50)).isoformat()
    hard_deadline = (now + timedelta(minutes=55)).isoformat()

    try:
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
                "-AllowDirty",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert res.returncode != 0
        assert "FIGMA_SUPERVISOR_PROJECT_RESERVED" in res.stderr

        # Postcondition: The foreign supervisor lock MUST BE UNTOUCHED
        assert foreign_sup_lock.exists()
        assert foreign_sup_lock.read_bytes() == foreign_bytes
    finally:
        foreign_sup_lock.unlink(missing_ok=True)
        shutil.rmtree(ROOT / f"frontend/test-results/{proj}", ignore_errors=True)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_remaining_time_guard_rejects_insufficient_time(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    cutoff = (now + timedelta(minutes=30)).isoformat()
    hard_deadline = (now + timedelta(minutes=35)).isoformat()
    proj = f"knora-figma-e2e-session-insufficient-{uuid.uuid4().hex[:8]}"

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
        timeout=30,
    )
    assert res.returncode != 0
    assert "INSUFFICIENT_TIME_FOR_WHOLE_PACKAGE" in res.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_rejects_invalid_deadlines(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    cutoff = (now + timedelta(minutes=50)).isoformat()
    hard_deadline = (now + timedelta(minutes=40)).isoformat()
    proj = f"knora-figma-e2e-session-invalid-deadlines-{uuid.uuid4().hex[:8]}"

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
        timeout=30,
    )
    assert res.returncode != 0
    assert "INVALID_DEADLINES" in res.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_hang_startup_cleans_up_partial_startup(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    cutoff = (now + timedelta(seconds=2)).isoformat()
    hard_deadline = (now + timedelta(seconds=10)).isoformat()
    proj = f"knora-figma-e2e-session-hang-startup-{uuid.uuid4().hex[:8]}"

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
            "HangStartup",
            "-AllowDirty",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert res.returncode != 0

    receipt_path = ROOT / f"frontend/test-results/{proj}/task8-supervision-receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    assert receipt["status"] == "TIMEOUT_CLEANUP_VERIFIED"
    assert receipt["cleanupVerified"] is True
    assert receipt["reservationReleased"] is True

    # Verify ownership receipt recorded startupAttempted is True
    owner_path = ROOT / f"frontend/test-results/{proj}/worker-ownership.json"
    assert owner_path.exists()
    owner_data = json.loads(owner_path.read_text(encoding="utf-8-sig"))
    assert owner_data["startupAttempted"] is True

    shutil.rmtree(ROOT / f"frontend/test-results/{proj}", ignore_errors=True)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_supervisor_fail_preflight_skips_teardown(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    cutoff = (now + timedelta(minutes=50)).isoformat()
    hard_deadline = (now + timedelta(minutes=55)).isoformat()
    proj = f"knora-figma-e2e-session-fail-preflight-{uuid.uuid4().hex[:8]}"

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
            "FailPreflight",
            "-AllowDirty",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert res.returncode != 0
    assert "skipping compose teardown to protect foreign resources" in res.stdout

    receipt_path = ROOT / f"frontend/test-results/{proj}/task8-supervision-receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    assert receipt["cleanupVerified"] is False
    assert receipt["reservationReleased"] is False

    # Verify ownership recorded startupAttempted is False
    owner_path = ROOT / f"frontend/test-results/{proj}/worker-ownership.json"
    assert owner_path.exists()
    owner_data = json.loads(owner_path.read_text(encoding="utf-8-sig"))
    assert owner_data["startupAttempted"] is False

    # Cleanup retained test artifact
    Path(receipt["reservationPath"]).unlink(missing_ok=True)
    shutil.rmtree(ROOT / f"frontend/test-results/{proj}", ignore_errors=True)


@pytest.mark.skipif(WIN_POWERSHELL is None, reason="Windows PowerShell runner unavailable")
def test_supervisor_real_baseline_projection_path_regression(tmp_path: Path) -> None:
    runner_ps1 = tmp_path / "test_baseline_regression.ps1"
    runner_code = r"""
$ErrorActionPreference = 'Stop'
$scriptPath = '__SUPERVISOR_SCRIPT__'
$tokens = $null; $parseErrors = $null
$parser = [System.Management.Automation.Language.Parser]
$ast = $parser::ParseFile($scriptPath, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw $parseErrors[0] }
$isFunc = {
    param($n)
    $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $n.Name -eq 'Unwrap-Items'
}
$func = $ast.FindAll($isFunc, $true)[0]
. ([scriptblock]::Create($func.Extent.Text))

$source = [IO.File]::ReadAllText($scriptPath)
$start = $source.IndexOf('        # Setup baseline projection')
$end = $source.IndexOf('        # Set baseline realm', $start)
$block = [scriptblock]::Create($source.Substring($start, $end - $start))

$results = [ordered]@{}

# Case 1: Nested multi-mapper selects only policy ID, successful delete + absent readback passes
$script:deleteCalls = [System.Collections.Generic.List[string]]::new()
$script:callCount = 0
function Invoke-RestMethod {
    param($Uri, $Headers, $Method, $ErrorAction)
    if ($Method -eq 'Delete') {
        $script:deleteCalls.Add($Uri)
        return $null
    }
    if ($Uri -like '*clients?clientId=*') {
        return ,@(@([pscustomobject]@{id='client-123'}))
    }
    if ($Uri -like '*protocol-mappers/models') {
        $script:callCount++
        if ($script:callCount -eq 1) {
            return ,@(@(
                [pscustomobject]@{id='mapper-other';name='other-mapper'},
                [pscustomobject]@{id='mapper-target';name='knora-session-policy'}
            ))
        } else {
            return ,@(@([pscustomobject]@{id='mapper-other';name='other-mapper'}))
        }
    }
    throw "Unexpected URI: $Uri"
}
$kcHeaders = @{ Authorization = 'Bearer token' }
. $block
$results['case1_clientUuid'] = $clientUuid
$results['case1_deleteCalls'] = @($script:deleteCalls)

# Case 2: Failed delete 403 aborts
$script:attemptedDeleteUri = $null
function Invoke-RestMethod {
    param($Uri, $Headers, $Method, $ErrorAction)
    if ($Method -eq 'Delete') {
        $script:attemptedDeleteUri = $Uri
        throw 'SIMULATED_HTTP_403_DELETE_DENIED'
    }
    if ($Uri -like '*clients?clientId=*') { return ,@([pscustomobject]@{id='client-123'}) }
    return ,@(@([pscustomobject]@{id='mapper-target';name='knora-session-policy'}))
}
$continued2 = $false
try {
    . $block
    $continued2 = $true
} catch {
    $results['case2_caught'] = $_.Exception.Message
}
$results['case2_continued'] = $continued2
$results['case2_deleteUri'] = $script:attemptedDeleteUri

# Case 3: Failed delete 500 aborts
function Invoke-RestMethod {
    param($Uri, $Headers, $Method, $ErrorAction)
    if ($Method -eq 'Delete') { throw 'SIMULATED_HTTP_500_SERVER_ERROR' }
    if ($Uri -like '*clients?clientId=*') { return ,@([pscustomobject]@{id='client-123'}) }
    return ,@(@([pscustomobject]@{id='mapper-target';name='knora-session-policy'}))
}
$continued3 = $false
try {
    . $block
    $continued3 = $true
} catch {
    $results['case3_caught'] = $_.Exception.Message
}
$results['case3_continued'] = $continued3

# Case 4: Preexisting no-policy case works
$script:deleteCalled4 = $false
function Invoke-RestMethod {
    param($Uri, $Headers, $Method, $ErrorAction)
    if ($Method -eq 'Delete') {
        $script:deleteCalled4 = $true
        throw 'DELETE_SHOULD_NOT_BE_CALLED'
    }
    if ($Uri -like '*clients?clientId=*') { return ,@([pscustomobject]@{id='client-123'}) }
    return ,@(@([pscustomobject]@{id='mapper-other';name='other-mapper'}))
}
. $block
$results['case4_deleteCalled'] = $script:deleteCalled4
$results['case4_clientUuid'] = $clientUuid

# Case 5: Ambiguous client (2 clients) aborts
function Invoke-RestMethod {
    param($Uri, $Headers, $Method, $ErrorAction)
    if ($Uri -like '*clients?clientId=*') {
        return @([pscustomobject]@{id='c1'}, [pscustomobject]@{id='c2'})
    }
    return @()
}
$continued5 = $false
try {
    . $block
    $continued5 = $true
} catch {
    $results['case5_caught'] = $_.Exception.Message
}
$results['case5_continued'] = $continued5

# Case 6: Residual mapper on readback aborts
function Invoke-RestMethod {
    param($Uri, $Headers, $Method, $ErrorAction)
    if ($Method -eq 'Delete') { return $null }
    if ($Uri -like '*clients?clientId=*') { return ,@([pscustomobject]@{id='client-123'}) }
    return ,@(@([pscustomobject]@{id='mapper-target';name='knora-session-policy'}))
}
$continued6 = $false
try {
    . $block
    $continued6 = $true
} catch {
    $results['case6_caught'] = $_.Exception.Message
}
$results['case6_continued'] = $continued6

$results | ConvertTo-Json -Depth 5
""".replace("__SUPERVISOR_SCRIPT__", SUPERVISOR_SCRIPT.as_posix())

    runner_ps1.write_text(runner_code, encoding="utf-8")

    res = subprocess.run(
        [
            WIN_POWERSHELL,
            "-NoProfile",
            "-File",
            str(runner_ps1),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert res.returncode == 0, f"Runner failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    data = json.loads(res.stdout)

    assert data["case1_clientUuid"] == "client-123"
    assert len(data["case1_deleteCalls"]) == 1
    assert "mapper-target" in data["case1_deleteCalls"][0]
    assert "mapper-other" not in data["case1_deleteCalls"][0]

    assert data["case2_continued"] is False
    assert "SIMULATED_HTTP_403_DELETE_DENIED" in data["case2_caught"]
    assert "mapper-target" in data["case2_deleteUri"]

    assert data["case3_continued"] is False
    assert "SIMULATED_HTTP_500_SERVER_ERROR" in data["case3_caught"]

    assert data["case4_deleteCalled"] is False
    assert data["case4_clientUuid"] == "client-123"

    assert data["case5_continued"] is False
    assert "BASELINE_CLIENT_AMBIGUOUS_OR_MISSING" in data["case5_caught"]

    assert data["case6_continued"] is False
    assert "BASELINE_MAPPER_RESIDUAL" in data["case6_caught"]
