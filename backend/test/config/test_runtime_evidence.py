"""Release evidence must be complete and bound to one tested commit."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from runtime_evidence import create_evidence, validate_release  # noqa: E402

SHA = "a" * 40
WORKFLOW_SHA = "b" * 40


def _powershell() -> str:
    return shutil.which("pwsh") or shutil.which("powershell") or "pwsh"


@pytest.mark.parametrize("profile", ["application", "otp"])
def test_runtime_prepare_failure_keeps_diagnostic_and_rollback(
    tmp_path: Path, profile: str
) -> None:
    root = Path(__file__).resolve().parents[3]
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(root / "scripts/run-runtime-verification.ps1", scripts)
    (scripts / "prepare-figma-e2e.ps1").write_text(
        """'KEYCLOAK_ROLLBACK_SNAPSHOT=owned-snapshot.json'
try {
    & python -c "import sys; print('COMPOSE_START_DIAGNOSTIC', file=sys.stderr); sys.exit(1)"
} catch { Write-Host $_ }
throw 'FIGMA_START_FAILED'
""",
        encoding="utf-8",
    )
    (scripts / "configure-keycloak-auth-flow.ps1").write_text(
        "param($Mode,$BaseUrl,$Project,$AdminUsername,$AdminPassword,$SnapshotPath)\n"
        'Write-Host "ROLLBACK=$Mode/$SnapshotPath"\n',
        encoding="utf-8",
    )
    harness = tmp_path / "failure.ps1"
    harness.write_text(
        """param($Script,$Profile)
function global:git { $global:LASTEXITCODE = 0; 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' }
function global:docker { $global:LASTEXITCODE = 0 }
& $Script -SubjectSha ('a' * 40) -WorkflowSha ('b' * 40) -Profile $Profile -RunId 'test'
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-File",
            str(harness),
            str(scripts / "run-runtime-verification.ps1"),
            profile,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "FIGMA_START_FAILED" in output
    assert "COMPOSE_START_DIAGNOSTIC" in output
    assert "ROLLBACK=Rollback/owned-snapshot.json" in output
    assert not (tmp_path / f".verification/runtime/{profile}/evidence.json").exists()


@pytest.mark.parametrize(
    "names", [["first", "second"], ["first"], ["first", "first"], ["first", "other"]]
)
def test_runtime_storage_report_requires_every_selected_case(
    tmp_path: Path, names: list[str]
) -> None:
    root = Path(__file__).resolve().parents[3]
    report = tmp_path / "storage.xml"
    report.write_text(
        "<testsuite>" + "".join(f'<testcase name="{name}"/>' for name in names) + "</testsuite>"
    )
    harness = tmp_path / "cases.ps1"
    harness.write_text(
        r"""param($Source,$Report)
$ErrorActionPreference = 'Stop'
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$null,[ref]$null)
$function = $ast.Find({param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq 'Assert-StorageCases'
},$true)
Invoke-Expression $function.Extent.Text
Assert-StorageCases $Report @('first','second')
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-File",
            str(harness),
            str(root / "scripts/run-runtime-verification.ps1"),
            str(report),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if names == ["first", "second"]:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0
        assert "RUNTIME_STORAGE_CASES_MISMATCH" in result.stderr


def test_runtime_storage_selection_names_existing_java_cases() -> None:
    root = Path(__file__).resolve().parents[3]
    runner = (root / "scripts/run-runtime-verification.ps1").read_text()
    java = (
        root
        / "infra/keycloak/providers/email-otp-reset/src/test/java/com/knora/keycloak/reset"
        / "OtpChallengeConcurrencyIT.java"
    ).read_text()
    selected = set(re.findall(r"(?:probe|relational|independentJpa)[A-Z]\w+", runner))
    declared = set(re.findall(r"\bvoid\s+(\w+)\s*\(", java))
    assert len(selected) == 8
    assert selected <= declared, selected - declared


@pytest.mark.parametrize("ready_after", [3, 0])
def test_runtime_cleanup_waits_for_native_issuer(tmp_path: Path, ready_after: int) -> None:
    root = Path(__file__).resolve().parents[3]
    (tmp_path / "otp-binding.json").write_text("{}")
    (tmp_path / "configure-keycloak-email-otp.ps1").write_text(
        "param($Mode,[switch]$EnableIsolatedOtp,$AdminUsername,$AdminPassword,$SnapshotPath)\n"
        "if (-not $global:ready) { throw 'RESTORE_BEFORE_READY' }\n"
        "$global:restored = $true\n",
        encoding="utf-8",
    )
    harness = tmp_path / "cleanup.ps1"
    harness.write_text(
        r"""param($Source,[int]$ReadyAfter)
$ErrorActionPreference = 'Stop'
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$null,[ref]$null)
$cleanup = $ast.Find({param($node)
    $node -is [System.Management.Automation.Language.TryStatementAst] -and
    $node.Finally -and $node.Finally.Extent.Text.Contains('$cleanupFailed = $false')
},$true).Finally
$Profile='otp'; $profileDir=$PSScriptRoot; $VaultPath=$PSScriptRoot
$AdminUsername='test'; $AdminPassword='test'; $runtimePreparation=@(); $compose=@()
$snapshots=@(); $ownedVault=$null; $global:ready=$false; $global:restored=$false
$global:probeCalls=0
function Invoke-Checked {
    param($File,$Arguments)
    if (($File -eq 'sudo' -or $File -like '*prepare-figma-otp-runtime.ps1') -and
        -not $global:ready) { throw 'OTP_ADMIN_AUTHENTICATION_FAILED' }
}
function Invoke-RestMethod {
    $global:probeCalls++
    if ($ReadyAfter -gt 0 -and $global:probeCalls -ge $ReadyAfter) {
        $global:ready=$true
        return @{ issuer='http://127.0.0.1:8380/realms/knora-dev' }
    }
    throw 'not ready'
}
function Start-Sleep { }
$cleanupPath = Join-Path $PSScriptRoot 'cleanup-body.ps1'
$body = $cleanup.Extent.Text
$body.Substring(1,$body.Length-2) | Set-Content $cleanupPath
try { & $cleanupPath }
catch {
    if ($ReadyAfter -eq 0 -and $global:probeCalls -eq 60 -and
        $_.Exception.Message -eq 'RUNTIME_CLEANUP_FAILED' -and -not $global:restored) { exit 0 }
    throw
}
if ($ReadyAfter -eq 0 -or -not $global:restored -or $global:probeCalls -lt 3) {
    throw 'cleanup did not wait for readiness'
}
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-File",
            str(harness),
            str(root / "scripts/run-runtime-verification.ps1"),
            str(ready_after),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_runtime_otp_action_outlives_the_resend_cooldown() -> None:
    root = Path(__file__).resolve().parents[3]
    realm = json.loads((root / "test/fixtures/keycloak/figma-realm.json").read_text())
    # Keycloak resets recovery when the user action expires; OTP resend waits 300 seconds.
    assert realm.get("accessCodeLifespanUserAction", 300) > 300


def test_runtime_powershell_arguments_bind_by_name(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    target = tmp_path / "target.ps1"
    target.write_text(
        "param([ValidateSet('Prepare')][string]$Mode,[switch]$EnableIsolatedOtp,[string]$SnapshotPath)\n"
        "if ($Mode -ne 'Prepare' -or -not $EnableIsolatedOtp -or "
        "$SnapshotPath -ne 'owned path.json') { throw 'binding failed' }\n"
        "'script stdout' | Out-Host\n$global:LASTEXITCODE = 0\n",
        encoding="utf-8",
    )
    harness = tmp_path / "named.ps1"
    harness.write_text(
        """param($Source,$Target)
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$null,[ref]$null)
$function = $ast.Find({param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq 'Invoke-Checked-Named'
},$true)
Invoke-Expression $function.Extent.Text
$result = @(Invoke-Checked-Named $Target @{
    Mode='Prepare'; EnableIsolatedOtp=$true; SnapshotPath='owned path.json'
})
if ($result.Count -ne 0) { throw 'stdout returned as data' }
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-File",
            str(harness),
            str(root / "scripts/run-runtime-verification.ps1"),
            str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_runtime_command_output_does_not_replace_report_path(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    harness = tmp_path / "output.ps1"
    harness.write_text(
        """param([string]$Source, [string]$Root, [string]$Output)
$ErrorActionPreference = 'Stop'
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Source, [ref]$null, [ref]$null)
foreach ($name in 'Invoke-Checked', 'Invoke-Playwright') {
    $function = $ast.Find({param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq $name
    }, $true)
    Invoke-Expression $function.Extent.Text
}
function global:Test-Runner { 'browser stdout'; $global:LASTEXITCODE = 0 }
if (@(Invoke-Checked 'Test-Runner' @()).Count -ne 0) { throw 'stdout returned as data' }
function Invoke-Checked {
    'browser stdout' | Out-Host
    '<testsuite tests="1"><testcase name="case"/></testsuite>' |
        Set-Content $env:PLAYWRIGHT_JUNIT_OUTPUT_NAME
}
$repositoryRoot = $Root
$profileDir = $Output
$report = Invoke-Playwright 'identity' 'config.ts' 'identity.spec.ts' '' ''
if ($report -isnot [string] -or $report -ne (Join-Path $Output 'identity.xml')) {
    throw 'report path is not scalar'
}
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-File",
            str(harness),
            str(root / "scripts/run-runtime-verification.ps1"),
            str(root),
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


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


@pytest.mark.parametrize("field", ["scenario_counts", "excluded_scenarios"])
def test_release_rejects_incomplete_scenario_accounting(tmp_path: Path, field: str) -> None:
    path = _evidence(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop(field)
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
            "<system-out>private@example.test</system-out></testcase>",
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
        '<testsuite tests="2"><testcase classname="x" name="y"/></testsuite>',
        '<testsuites tests="1"><testsuite tests="1" skipped="1">'
        '<testcase classname="x" name="y"/></testsuite></testsuites>',
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


def test_retrieval_v3_profile_evidence_lifecycle(tmp_path: Path) -> None:
    reports = {}
    for scenario in ("dense_hybrid", "reranking", "query_understanding", "recovery"):
        path = tmp_path / f"{scenario}.xml"
        _report(path)
        reports[scenario] = path
    output = tmp_path / "output"
    evidence_path = create_evidence(
        subject_sha=SHA,
        actual_sha=SHA,
        workflow_sha=WORKFLOW_SHA,
        run_id="retrieval-1",
        run_attempt="1",
        profile="retrieval-v3",
        reports=reports,
        output_dir=output,
        started_at="2026-10-22T00:00:00Z",
        tool_identities={"python": "3.13.15"},
        image_identities={},
    )
    assert evidence_path.exists()
    validate_release(SHA, [evidence_path], ["retrieval-v3"])
