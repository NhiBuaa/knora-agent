from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
ROOT = Path(__file__).resolve().parents[3]


def _run_script(
    tmp_path: Path, script_content: str, args: list[str]
) -> subprocess.CompletedProcess:
    wrapper = tmp_path / "run.ps1"
    wrapper.write_text(script_content, encoding="utf-8")
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(wrapper), *args],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_rejects_foreign_target_and_port(tmp_path: Path) -> None:
    script = str(ROOT / "scripts/configure-keycloak-session-policy.ps1")
    # Wrong base url / port
    res = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            script,
            "-BaseUrl",
            "http://127.0.0.1:8080",
            "-Realm",
            "knora-dev",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    assert "KEYCLOAK_EXACT_TARGET_REQUIRED" in res.stderr

    # Wrong realm
    res = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            script,
            "-BaseUrl",
            "http://127.0.0.1:8180",
            "-Realm",
            "master",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    assert "KEYCLOAK_EXACT_TARGET_REQUIRED" in res.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_missing_provider_fails(tmp_path: Path) -> None:
    wrapper_text = """
param($ScriptPath)
function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body)
    if ($Method -eq 'Post') { return @{ access_token = 'test-token' } }
    if ($Uri.EndsWith('/serverinfo')) {
        return [pscustomobject]@{
            protocolMapperTypes = [pscustomobject]@{
                'openid-connect' = @(
                    [pscustomobject]@{ id = 'oidc-usermodel-attribute-mapper' }
                )
            }
        }
    }
    return [pscustomobject]@{ realm = 'knora-dev' }
}
$credentials = @{AdminUsername='admin'; AdminPassword='password'}
& $ScriptPath -Mode Inspect @credentials
"""
    res = _run_script(
        tmp_path, wrapper_text, [str(ROOT / "scripts/configure-keycloak-session-policy.ps1")]
    )
    assert res.returncode != 0
    assert "KEYCLOAK_SESSION_POLICY_PROVIDER_REQUIRED" in res.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_mapper_conflict_fails(tmp_path: Path) -> None:
    wrapper_text = """
param($ScriptPath)
function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body)
    if ($Method -eq 'Post') { return @{ access_token = 'test-token' } }
    if ($Uri.EndsWith('/serverinfo')) {
        return [pscustomobject]@{
            protocolMapperTypes = [pscustomobject]@{
                'openid-connect' = @(
                    [pscustomobject]@{ id = 'knora-session-policy' }
                )
            }
        }
    }
    if ($Uri.Contains('/clients?clientId=knora-web')) {
        return @([pscustomobject]@{ id = 'client-uuid-1'; clientId = 'knora-web' })
    }
    if ($Uri.EndsWith('/protocol-mappers/models')) {
        return @(
            [pscustomobject]@{
                id = 'mapper-conflict'
                name = 'knora-session-policy'
                protocol = 'openid-connect'
                protocolMapper = 'different-provider'
                consentRequired = $false
                config = @{}
            }
        )
    }
    if ($Uri.EndsWith('/default-client-scopes') -or $Uri.EndsWith('/optional-client-scopes')) {
        return @()
    }
    return [pscustomobject]@{ realm = 'knora-dev' }
}
$credentials = @{AdminUsername='admin'; AdminPassword='password'}
& $ScriptPath -Mode Diff @credentials
"""
    res = _run_script(
        tmp_path, wrapper_text, [str(ROOT / "scripts/configure-keycloak-session-policy.ps1")]
    )
    assert res.returncode != 0
    assert "KEYCLOAK_SESSION_POLICY_MAPPER_CONFLICT" in res.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_apply_repeat_noop_and_rollback_flow(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.json"
    wrapper_text = """
param($ScriptPath, $SnapshotPath)

$global:realm = [pscustomobject]@{
    realm = 'knora-dev'
    rememberMe = $false
    ssoSessionIdleTimeout = 1800
    ssoSessionMaxLifespan = 36000
    ssoSessionIdleTimeoutRememberMe = 0
    ssoSessionMaxLifespanRememberMe = 0
    clientSessionIdleTimeout = 0
    clientSessionMaxLifespan = 0
    accessTokenLifespan = 300
}

$global:client = [pscustomobject]@{
    id = 'client-uuid-1'
    clientId = 'knora-web'
    attributes = [pscustomobject]@{
        'post.logout.redirect.uris' = 'http://127.0.0.1:3000/'
        'client.session.idle.timeout' = '1800'
        'custom.attribute' = 'retained'
    }
}

$global:mappers = [System.Collections.ArrayList]@()
$global:putRealmCount = 0
$global:putClientCount = 0
$global:postMapperCount = 0

function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') { return 'fixture-container' }
    return '[{"NetworkSettings":{"Ports":{"8080/tcp":[{"HostIp":"127.0.0.1","HostPort":"8180"}]}}}]'
}

function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body)
    if ($Method -eq 'Post') {
        if ($Uri.EndsWith('/protocol/openid-connect/token')) {
            return @{ access_token = 'test-token' }
        }
        if ($Uri.EndsWith('/protocol-mappers/models')) {
            $global:postMapperCount++
            $m = $Body | ConvertFrom-Json
            $global:mappers.Add($m) | Out-Null
            return $m
        }
    }
    if ($Method -eq 'Delete') {
        if ($Uri.Contains('/protocol-mappers/models/')) {
            $id = $Uri.Substring($Uri.LastIndexOf('/') + 1)
            $toRemove = $null
            foreach ($m in $global:mappers) { if ($m.id -eq $id) { $toRemove = $m } }
            if ($toRemove) { $global:mappers.Remove($toRemove) }
            return
        }
    }
    if ($Method -eq 'Put') {
        if ($Uri.EndsWith('/admin/realms/knora-dev')) {
            $global:putRealmCount++
            $b = $Body | ConvertFrom-Json
            foreach ($p in $b.PSObject.Properties) {
                $global:realm.($p.Name) = $p.Value
            }
            return
        }
        if ($Uri.Contains('/clients/client-uuid-1')) {
            $global:putClientCount++
            $b = $Body | ConvertFrom-Json
            $global:client.attributes = $b.attributes
            return
        }
    }
    if ($Uri.EndsWith('/serverinfo')) {
        return [pscustomobject]@{
            protocolMapperTypes = [pscustomobject]@{
                'openid-connect' = @(
                    [pscustomobject]@{ id = 'knora-session-policy' }
                )
            }
        }
    }
    if ($Uri.Contains('/clients?clientId=knora-web')) {
        return @($global:client)
    }
    if ($Uri.EndsWith('/clients/client-uuid-1')) {
        return $global:client
    }
    if ($Uri.EndsWith('/protocol-mappers/models')) {
        return @($global:mappers)
    }
    if ($Uri.EndsWith('/default-client-scopes') -or $Uri.EndsWith('/optional-client-scopes')) {
        return @()
    }
    if ($Uri.EndsWith('/admin/realms/knora-dev')) {
        return $global:realm
    }
    throw "Unexpected URI: $Uri"
}

$credentials = @{AdminUsername='admin'; AdminPassword='password'}

# 1. Apply
& $ScriptPath -Mode Apply @credentials -SnapshotPath $SnapshotPath
if ($global:realm.rememberMe -ne $true -or $global:realm.ssoSessionMaxLifespan -ne 28800) {
    throw "Realm was not updated"
}
if ($global:client.attributes.'access.token.lifespan' -ne '300') {
    throw "Client access.token.lifespan was not set"
}
if ($global:client.attributes.'client.session.idle.timeout' -ne $null) {
    throw "client.session.idle.timeout was not removed"
}
if ($global:client.attributes.'custom.attribute' -ne 'retained') {
    throw "Unrelated attribute was not preserved"
}
if ($global:mappers.Count -ne 1) {
    throw "Mapper was not created"
}

# 2. Repeat Apply is No-op
& $ScriptPath -Mode Apply @credentials -SnapshotPath $SnapshotPath | Out-Null
$countsMatch = (
    $global:putRealmCount -eq 1 -and
    $global:putClientCount -eq 1 -and
    $global:postMapperCount -eq 1
)
if (-not $countsMatch) {
    throw "Repeat Apply was not a no-op"
}

# 3. Rollback
& $ScriptPath -Mode Rollback @credentials -SnapshotPath $SnapshotPath
if ($global:realm.rememberMe -ne $false -or $global:realm.ssoSessionMaxLifespan -ne 36000) {
    throw "Realm was not restored: rememberMe=$($global:realm.rememberMe)"
}
if ($global:client.attributes.'client.session.idle.timeout' -ne '1800') {
    throw "Client attribute client.session.idle.timeout was not restored"
}
if ($global:client.attributes.'access.token.lifespan' -ne $null) {
    throw "Client attribute access.token.lifespan was not removed"
}
if ($global:client.attributes.'custom.attribute' -ne 'retained') {
    throw "Unrelated attribute lost on rollback"
}
if ($global:mappers.Count -ne 0) {
    throw "Mapper was not removed on rollback"
}

Write-Output 'KEYCLOAK_SESSION_POLICY_FLOW_PASSED'
"""
    res = _run_script(
        tmp_path,
        wrapper_text,
        [str(ROOT / "scripts/configure-keycloak-session-policy.ps1"), str(snapshot)],
    )
    assert res.returncode == 0, res.stderr
    assert "KEYCLOAK_SESSION_POLICY_FLOW_PASSED" in res.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_existing_snapshot_refusal(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text("existing", encoding="utf-8")
    wrapper_text = """
param($ScriptPath, $SnapshotPath)
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') { return 'fixture-container' }
    return '[{"NetworkSettings":{"Ports":{"8080/tcp":[{"HostIp":"127.0.0.1","HostPort":"8180"}]}}}]'
}
function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body)
    if ($Method -eq 'Post') { return @{ access_token = 'test-token' } }
    if ($Uri.EndsWith('/serverinfo')) {
        return [pscustomobject]@{
            protocolMapperTypes = [pscustomobject]@{
                'openid-connect' = @([pscustomobject]@{ id = 'knora-session-policy' })
            }
        }
    }
    if ($Uri.Contains('/clients?clientId=knora-web')) {
        return @([pscustomobject]@{
            id = 'client-uuid-1'
            clientId = 'knora-web'
            attributes = @{}
        })
    }
    if ($Uri.EndsWith('/protocol-mappers/models')) { return @() }
    if ($Uri.EndsWith('/default-client-scopes')) { return @() }
    if ($Uri.EndsWith('/optional-client-scopes')) { return @() }
    return [pscustomobject]@{
        realm = 'knora-dev'
        rememberMe = $false
        ssoSessionIdleTimeout = 1800
        ssoSessionMaxLifespan = 36000
        ssoSessionIdleTimeoutRememberMe = 0
        ssoSessionMaxLifespanRememberMe = 0
        clientSessionIdleTimeout = 0
        clientSessionMaxLifespan = 0
        accessTokenLifespan = 300
    }
}
$credentials = @{AdminUsername='admin'; AdminPassword='password'}
& $ScriptPath -Mode Apply @credentials -SnapshotPath $SnapshotPath
"""
    res = _run_script(
        tmp_path,
        wrapper_text,
        [str(ROOT / "scripts/configure-keycloak-session-policy.ps1"), str(snapshot)],
    )
    assert res.returncode != 0
    assert "KEYCLOAK_SNAPSHOT_ALREADY_EXISTS" in res.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_readback_mismatch_fails(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.json"
    wrapper_text = """
param($ScriptPath, $SnapshotPath)
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') { return 'fixture-container' }
    return '[{"NetworkSettings":{"Ports":{"8080/tcp":[{"HostIp":"127.0.0.1","HostPort":"8180"}]}}}]'
}
function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body)
    if ($Method -eq 'Post') {
        if ($Uri.EndsWith('/protocol/openid-connect/token')) {
            return @{ access_token = 'test-token' }
        }
        if ($Uri.EndsWith('/protocol-mappers/models')) { return $Body | ConvertFrom-Json }
    }
    if ($Uri.EndsWith('/serverinfo')) {
        return [pscustomobject]@{
            protocolMapperTypes = [pscustomobject]@{
                'openid-connect' = @([pscustomobject]@{ id = 'knora-session-policy' })
            }
        }
    }
    if ($Uri.Contains('/clients?clientId=knora-web') -or $Uri.EndsWith('/clients/client-uuid-1')) {
        # Return client whose attributes never update (simulating readback mismatch)
        return [pscustomobject]@{
            id = 'client-uuid-1'
            clientId = 'knora-web'
            attributes = [pscustomobject]@{}
        }
    }
    if ($Uri.EndsWith('/protocol-mappers/models')) {
        # Return mapper matching desired
        return @([pscustomobject]@{
            id = 'mapper-id-1'
            name = 'knora-session-policy'
            protocol = 'openid-connect'
            protocolMapper = 'knora-session-policy'
            consentRequired = $false
            config = @{}
        })
    }
    if ($Uri.EndsWith('/default-client-scopes')) { return @() }
    if ($Uri.EndsWith('/optional-client-scopes')) { return @() }
    if ($Method -eq 'Put') { return }
    return [pscustomobject]@{
        realm = 'knora-dev'
        rememberMe = $false
        ssoSessionIdleTimeout = 1800
        ssoSessionMaxLifespan = 36000
        ssoSessionIdleTimeoutRememberMe = 0
        ssoSessionMaxLifespanRememberMe = 0
        clientSessionIdleTimeout = 0
        clientSessionMaxLifespan = 0
        accessTokenLifespan = 300
    }
}
$credentials = @{AdminUsername='admin'; AdminPassword='password'}
& $ScriptPath -Mode Apply @credentials -SnapshotPath $SnapshotPath
"""
    res = _run_script(
        tmp_path,
        wrapper_text,
        [str(ROOT / "scripts/configure-keycloak-session-policy.ps1"), str(snapshot)],
    )
    assert res.returncode != 0
    assert "KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED" in res.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_client_drift_before_rollback_rejected(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.json"
    wrapper_text = """
param($ScriptPath, $SnapshotPath)
$global:realm = [pscustomobject]@{
    realm = 'knora-dev'
    rememberMe = $false
    ssoSessionIdleTimeout = 1800
    ssoSessionMaxLifespan = 36000
    ssoSessionIdleTimeoutRememberMe = 0
    ssoSessionMaxLifespanRememberMe = 0
    clientSessionIdleTimeout = 0
    clientSessionMaxLifespan = 0
    accessTokenLifespan = 300
}
$global:client = [pscustomobject]@{
    id = 'client-uuid-1'
    clientId = 'knora-web'
    attributes = [pscustomobject]@{
        'post.logout.redirect.uris' = 'http://127.0.0.1:3000/'
    }
}
$global:mappers = [System.Collections.ArrayList]@()
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') { return 'fixture-container' }
    return '[{"NetworkSettings":{"Ports":{"8080/tcp":[{"HostIp":"127.0.0.1","HostPort":"8180"}]}}}]'
}
function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body)
    if ($Method -eq 'Post') {
        if ($Uri.EndsWith('/protocol/openid-connect/token')) {
            return @{ access_token = 'test-token' }
        }
        if ($Uri.EndsWith('/protocol-mappers/models')) {
            $m = $Body | ConvertFrom-Json
            $global:mappers.Add($m) | Out-Null
            return $m
        }
    }
    if ($Method -eq 'Put') {
        if ($Uri.EndsWith('/admin/realms/knora-dev')) {
            $b = $Body | ConvertFrom-Json
            foreach ($p in $b.PSObject.Properties) { $global:realm.($p.Name) = $p.Value }
            return
        }
        if ($Uri.Contains('/clients/client-uuid-1')) {
            $b = $Body | ConvertFrom-Json
            $global:client.attributes = $b.attributes
            return
        }
    }
    if ($Uri.EndsWith('/serverinfo')) {
        return [pscustomobject]@{
            protocolMapperTypes = [pscustomobject]@{
                'openid-connect' = @([pscustomobject]@{ id = 'knora-session-policy' })
            }
        }
    }
    if ($Uri.Contains('/clients?clientId=knora-web') -or $Uri.EndsWith('/clients/client-uuid-1')) {
        return $global:client
    }
    if ($Uri.EndsWith('/protocol-mappers/models')) { return @($global:mappers) }
    if ($Uri.EndsWith('/default-client-scopes') -or
        $Uri.EndsWith('/optional-client-scopes')) { return @() }
    if ($Uri.EndsWith('/admin/realms/knora-dev')) { return $global:realm }
}
$credentials = @{AdminUsername='admin'; AdminPassword='password'}
& $ScriptPath -Mode Apply @credentials -SnapshotPath $SnapshotPath | Out-Null
# Simulate drift in managed client attribute
$global:client.attributes.'access.token.lifespan' = '777'
& $ScriptPath -Mode Rollback @credentials -SnapshotPath $SnapshotPath
"""
    res = _run_script(
        tmp_path,
        wrapper_text,
        [str(ROOT / "scripts/configure-keycloak-session-policy.ps1"), str(snapshot)],
    )
    assert res.returncode != 0
    assert "KEYCLOAK_SESSION_POLICY_CONCURRENT_CHANGE" in res.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_repeated_rollback_is_noop(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.json"
    wrapper_text = """
param($ScriptPath, $SnapshotPath)
$global:realm = [pscustomobject]@{
    realm = 'knora-dev'
    rememberMe = $false
    ssoSessionIdleTimeout = 1800
    ssoSessionMaxLifespan = 36000
    ssoSessionIdleTimeoutRememberMe = 0
    ssoSessionMaxLifespanRememberMe = 0
    clientSessionIdleTimeout = 0
    clientSessionMaxLifespan = 0
    accessTokenLifespan = 300
}
$global:client = [pscustomobject]@{
    id = 'client-uuid-1'
    clientId = 'knora-web'
    attributes = [pscustomobject]@{
        'post.logout.redirect.uris' = 'http://127.0.0.1:3000/'
    }
}
$global:mappers = [System.Collections.ArrayList]@()
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') { return 'fixture-container' }
    return '[{"NetworkSettings":{"Ports":{"8080/tcp":[{"HostIp":"127.0.0.1","HostPort":"8180"}]}}}]'
}
function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body)
    if ($Method -eq 'Post') {
        if ($Uri.EndsWith('/protocol/openid-connect/token')) {
            return @{ access_token = 'test-token' }
        }
        if ($Uri.EndsWith('/protocol-mappers/models')) {
            $m = $Body | ConvertFrom-Json
            $global:mappers.Add($m) | Out-Null
            return $m
        }
    }
    if ($Method -eq 'Delete') {
        if ($Uri.Contains('/protocol-mappers/models/')) {
            $id = $Uri.Substring($Uri.LastIndexOf('/') + 1)
            $toRemove = $null
            foreach ($m in $global:mappers) { if ($m.id -eq $id) { $toRemove = $m } }
            if ($toRemove) { $global:mappers.Remove($toRemove) }
            return
        }
    }
    if ($Method -eq 'Put') {
        if ($Uri.EndsWith('/admin/realms/knora-dev')) {
            $b = $Body | ConvertFrom-Json
            foreach ($p in $b.PSObject.Properties) { $global:realm.($p.Name) = $p.Value }
            return
        }
        if ($Uri.Contains('/clients/client-uuid-1')) {
            $b = $Body | ConvertFrom-Json
            $global:client.attributes = $b.attributes
            return
        }
    }
    if ($Uri.EndsWith('/serverinfo')) {
        return [pscustomobject]@{
            protocolMapperTypes = [pscustomobject]@{
                'openid-connect' = @([pscustomobject]@{ id = 'knora-session-policy' })
            }
        }
    }
    if ($Uri.Contains('/clients?clientId=knora-web') -or $Uri.EndsWith('/clients/client-uuid-1')) {
        return $global:client
    }
    if ($Uri.EndsWith('/protocol-mappers/models')) { return @($global:mappers) }
    if ($Uri.EndsWith('/default-client-scopes') -or
        $Uri.EndsWith('/optional-client-scopes')) { return @() }
    if ($Uri.EndsWith('/admin/realms/knora-dev')) { return $global:realm }
}
$credentials = @{AdminUsername='admin'; AdminPassword='password'}
& $ScriptPath -Mode Apply @credentials -SnapshotPath $SnapshotPath | Out-Null
& $ScriptPath -Mode Rollback @credentials -SnapshotPath $SnapshotPath | Out-Null
# Second rollback should succeed as no-op verified
& $ScriptPath -Mode Rollback @credentials -SnapshotPath $SnapshotPath
"""
    res = _run_script(
        tmp_path,
        wrapper_text,
        [str(ROOT / "scripts/configure-keycloak-session-policy.ps1"), str(snapshot)],
    )
    assert res.returncode == 0
    assert "KEYCLOAK_SESSION_POLICY_ROLLBACK_VERIFIED" in res.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_conflicting_claim_mapper_rejected(tmp_path: Path) -> None:
    wrapper_text = """
param($ScriptPath)
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') { return 'fixture-container' }
    return '[{"NetworkSettings":{"Ports":{"8080/tcp":[{"HostIp":"127.0.0.1","HostPort":"8180"}]}}}]'
}
function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body)
    if ($Method -eq 'Post') { return @{ access_token = 'test-token' } }
    if ($Uri.EndsWith('/serverinfo')) {
        return [pscustomobject]@{
            protocolMapperTypes = [pscustomobject]@{
                'openid-connect' = @([pscustomobject]@{ id = 'knora-session-policy' })
            }
        }
    }
    if ($Uri.Contains('/clients?clientId=knora-web') -or $Uri.EndsWith('/clients/client-uuid-1')) {
        return [pscustomobject]@{ id = 'client-uuid-1'; clientId = 'knora-web'; attributes = @{} }
    }
    if ($Uri.EndsWith('/protocol-mappers/models')) {
        return @([pscustomobject]@{
            id = 'other-claim-mapper'
            name = 'other-claim-mapper'
            protocol = 'openid-connect'
            protocolMapper = 'oidc-hardcoded-claim-mapper'
            consentRequired = $false
            config = [pscustomobject]@{
                'claim.name' = 'knora_remember_me'
                'claim.value' = 'true'
            }
        })
    }
    if ($Uri.EndsWith('/default-client-scopes') -or
        $Uri.EndsWith('/optional-client-scopes')) { return @() }
    return [pscustomobject]@{ realm = 'knora-dev' }
}
$credentials = @{AdminUsername='admin'; AdminPassword='password'}
& $ScriptPath -Mode Inspect @credentials
"""
    res = _run_script(
        tmp_path,
        wrapper_text,
        [str(ROOT / "scripts/configure-keycloak-session-policy.ps1")],
    )
    assert res.returncode != 0
    assert "KEYCLOAK_SESSION_POLICY_MAPPER_CONFLICT" in res.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_scope_inspection_failure_rejected(tmp_path: Path) -> None:
    wrapper_text = """
param($ScriptPath)
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') { return 'fixture-container' }
    return '[{"NetworkSettings":{"Ports":{"8080/tcp":[{"HostIp":"127.0.0.1","HostPort":"8180"}]}}}]'
}
function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body)
    if ($Method -eq 'Post') { return @{ access_token = 'test-token' } }
    if ($Uri.EndsWith('/serverinfo')) {
        return [pscustomobject]@{
            protocolMapperTypes = [pscustomobject]@{
                'openid-connect' = @([pscustomobject]@{ id = 'knora-session-policy' })
            }
        }
    }
    if ($Uri.Contains('/clients?clientId=knora-web') -or $Uri.EndsWith('/clients/client-uuid-1')) {
        return [pscustomobject]@{ id = 'client-uuid-1'; clientId = 'knora-web'; attributes = @{} }
    }
    if ($Uri.EndsWith('/protocol-mappers/models')) { return @() }
    if ($Uri.EndsWith('/default-client-scopes')) {
        throw [System.Net.WebException]::new("Scope API connection refused")
    }
    return [pscustomobject]@{ realm = 'knora-dev' }
}
$credentials = @{AdminUsername='admin'; AdminPassword='password'}
& $ScriptPath -Mode Inspect @credentials
"""
    res = _run_script(
        tmp_path,
        wrapper_text,
        [str(ROOT / "scripts/configure-keycloak-session-policy.ps1")],
    )
    assert res.returncode != 0
    assert "KEYCLOAK_INSPECTION_FAILED" in res.stderr


def _get_apply_prefix() -> str:
    import ast

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    fn = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "test_apply_repeat_noop_and_rollback_flow"
    )
    wrapper = next(
        ast.literal_eval(n.value)
        for n in fn.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "wrapper_text" for t in n.targets)
    )
    return wrapper.split("# 1. Apply")[0]


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_apply_rejects_client_drift(tmp_path: Path) -> None:
    prefix = _get_apply_prefix()
    get_client = """    if ($Uri.EndsWith('/clients/client-uuid-1')) {
        return $global:client
    }"""
    drift_client = """    if ($Uri.EndsWith('/clients/client-uuid-1')) {
        if (-not $global:driftInjected) {
            $global:driftInjected = $true
            $global:client.attributes |
                Add-Member -NotePropertyName 'access.token.lifespan' `
                -NotePropertyValue '777' -Force
        }
        return $global:client
    }"""
    wrapper_text = (
        prefix.replace(get_client, drift_client)
        + "\n& $ScriptPath -Mode Apply @credentials -SnapshotPath $SnapshotPath\n"
    )
    res = _run_script(
        tmp_path,
        wrapper_text,
        [str(ROOT / "scripts/configure-keycloak-session-policy.ps1"), str(tmp_path / "snap.json")],
    )
    assert res.returncode != 0
    assert "KEYCLOAK_SESSION_POLICY_CONCURRENT_CHANGE" in res.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_apply_rejects_unexpected_mapper_id(tmp_path: Path) -> None:
    prefix = _get_apply_prefix()
    wrong_mapper = "$m = $Body | ConvertFrom-Json; $m.id = 'unexpected-server-id'"
    wrapper_text = (
        prefix.replace("$m = $Body | ConvertFrom-Json", wrong_mapper)
        + "\n& $ScriptPath -Mode Apply @credentials -SnapshotPath $SnapshotPath\n"
    )
    res = _run_script(
        tmp_path,
        wrapper_text,
        [str(ROOT / "scripts/configure-keycloak-session-policy.ps1"), str(tmp_path / "snap.json")],
    )
    assert res.returncode != 0
    assert "KEYCLOAK_SESSION_POLICY_UPDATE_OR_VERIFICATION_FAILED" in res.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_partial_client_readback_failure_rolls_back_cleanly(tmp_path: Path) -> None:
    prefix = _get_apply_prefix()
    get_client = """    if ($Uri.EndsWith('/clients/client-uuid-1')) {
        return $global:client
    }"""
    readback_fault_client = """    if ($Uri.EndsWith('/clients/client-uuid-1')) {
        if ($global:putClientCount -eq 1 -and -not $global:readbackFault) {
            $global:readbackFault = $true
            throw 'INJECTED_READBACK_FAILURE_AFTER_SUCCESSFUL_CLIENT_PUT'
        }
        return $global:client
    }"""
    wrapper_text = (
        prefix.replace(get_client, readback_fault_client)
        + "\ntry { & $ScriptPath -Mode Apply @credentials "
        + "-SnapshotPath $SnapshotPath | Out-Null } catch {}\n"
        + "& $ScriptPath -Mode Rollback @credentials -SnapshotPath $SnapshotPath\n"
        + "Write-Output 'PARTIAL_ROLLBACK_COMPLETED'\n"
    )
    res = _run_script(
        tmp_path,
        wrapper_text,
        [str(ROOT / "scripts/configure-keycloak-session-policy.ps1"), str(tmp_path / "snap.json")],
    )
    assert res.returncode == 0
    assert "KEYCLOAK_SESSION_POLICY_ROLLBACK_VERIFIED" in res.stdout
    assert "PARTIAL_ROLLBACK_COMPLETED" in res.stdout
