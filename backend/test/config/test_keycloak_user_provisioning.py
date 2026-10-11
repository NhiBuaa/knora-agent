import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[3] / "scripts" / "provision-keycloak-user.ps1"
SCRIPT = SCRIPT_PATH.read_text(encoding="utf-8")
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def test_local_user_provisioning_is_guarded_and_preserves_existing_attributes() -> None:
    assert "http://127.0.0.1:8180" in SCRIPT
    assert "KEYCLOAK_PROJECT_OWNERSHIP_REQUIRED" in SCRIPT
    assert "KEYCLOAK_USER_UNIQUE_MATCH_REQUIRED" in SCRIPT
    assert "documents:read" in SCRIPT
    assert "documents:write" in SCRIPT
    assert "questions:ask" in SCRIPT
    assert "attributes.capabilities" in SCRIPT
    assert "KEYCLOAK_USER_PROVISIONED" in SCRIPT
    assert "password" not in SCRIPT.lower().split("write-output", 1)[-1]


def test_provisioning_requires_explicit_username_and_does_not_accept_capabilities() -> None:
    assert "[Parameter(Mandatory = $true)]" in SCRIPT
    assert "[string]$Username" in SCRIPT
    assert "[string]$Capabilities" not in SCRIPT


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_provisioning_preserves_attributes_and_sets_only_baseline(tmp_path: Path) -> None:
    wrapper = tmp_path / "provision.ps1"
    wrapper.write_text(
        """
param([string]$ScriptPath)
$global:user = [pscustomobject]@{
    id = 'user-1'; username = 'alice';
    attributes = [pscustomobject]@{ department = @('research'); capabilities = @('operator') }
}
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') { return 'fixture-container' }
    return '[{"NetworkSettings":{"Ports":{"8080/tcp":[{"HostIp":"127.0.0.1","HostPort":"8180"}]}}}]'
}
function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body)
    if ($Method -eq 'Post') { return @{ access_token = 'test-only' } }
    if ($Uri -like '*users?username=*') { return @($global:user) }
    if ($Method -eq 'Put') {
        $global:user.attributes = ($Body | ConvertFrom-Json).attributes
        return
    }
    if ($Uri -like '*users/user-1') { return $global:user }
    throw "unexpected uri: $Uri"
}
& $ScriptPath -Username 'alice' -AdminUsername 'admin' -AdminPassword 'secret' | Out-Null
$attributes = $global:user.attributes
if ($attributes.department[0] -ne 'research') { throw 'existing attribute was lost' }
if ((@($attributes.capabilities) -join '|') -ne
    'documents:read|documents:write|questions:ask') { throw 'baseline mismatch' }
Write-Output 'PROVISIONING_CONTRACT_VERIFIED'
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(wrapper), str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "PROVISIONING_CONTRACT_VERIFIED" in result.stdout
