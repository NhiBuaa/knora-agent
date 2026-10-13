$ErrorActionPreference = 'Stop'
# Run the real preparation script in disposable fixture copies with service boundaries mocked.
$root = Split-Path $PSScriptRoot -Parent
$scratch = Join-Path $root ".verification/password-reset/selfchecks/$([guid]::NewGuid())"
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') { return }
    $global:resetPrepState.starts++
}
function Start-Sleep {}
function Get-Item {
    param($LiteralPath, [switch]$Force)
    # File symlinks require elevation on this machine; simulate their metadata only.
    if ($global:resetPrepState.fileLink -and [IO.Path]::GetFullPath($LiteralPath) -eq [IO.Path]::GetFullPath($global:resetPrepState.fileLink)) { return @{Attributes=[IO.FileAttributes]::ReparsePoint} }
    Microsoft.PowerShell.Management\Get-Item @PSBoundParameters
}
function Invoke-RestMethod {
    param($Uri, $Method = 'Get', $Headers, $TimeoutSec, $ContentType, $Body)
    if ($Uri -like '*:8900/health') {
        $global:resetPrepState.healthCalls++
        if ($global:resetPrepState.healthUnavailable) { return @{status='ok'; service='unexpected'} }
        if ($global:resetPrepState.healthCalls -lt 3) { throw 'synthetic startup delay' }
        return @{status='ok'; service='knora-agent'}
    }
    if ($Uri -like '*/token') { return @{access_token='synthetic'} }
    if ($Uri -like '*/executions/execution') {
        $provider = ($Body | ConvertFrom-Json).provider
        $global:resetPrepState.executions += [pscustomobject]@{id=$provider; providerId=$provider; requirement='DISABLED'}
        return
    }
    if ($Uri -like '*/executions') {
        if ($Method -eq 'Put') {
            if (($Body | ConvertFrom-Json).requirement -ne 'REQUIRED') { throw 'requirement' }
            $global:resetPrepState.required++
            return
        }
        return ,$global:resetPrepState.executions
    }
    if ($Uri -like '*/authentication/flows') { return ,@([pscustomobject]@{alias='issue162-reset'}) }
    if ($Method -eq 'Put') { $global:resetPrepState.bound = $true; return }
    return @{id='knora-reset-regression'}
}
$failed = @()
foreach ($case in 'parent-link', 'runtime-link', 'vault-link', 'realm-link', 'key-link', 'health', 'health-unavailable', 'partial-empty', 'partial-otp', 'invalid-key', 'empty-key', 'short-key', 'whitespace-key', 'valid-key', 'long-valid-key', 'unexpected-flow') {
    $copy = Join-Path $scratch $case
    $null = New-Item -ItemType Directory -Force "$copy/scripts", "$copy/test/fixtures/keycloak", "$copy/test/fixtures/password-reset"
    Copy-Item -LiteralPath "$PSScriptRoot/prepare-password-reset-regression.ps1" -Destination "$copy/scripts/prepare-password-reset-regression.ps1"
    Copy-Item -LiteralPath "$root/test/fixtures/keycloak/figma-realm.json" -Destination "$copy/test/fixtures/keycloak/figma-realm.json"
    $runtime = "$copy/.verification/password-reset"
    $outside = "$copy/outside"
    $null = New-Item -ItemType Directory -Force $outside
    Set-Content -LiteralPath "$outside/realm.json" -Value 'sentinel'
    $global:resetPrepState = @{starts=0; healthCalls=0; required=0; bound=$false; executions=@()}
    $global:resetPrepState.healthUnavailable = $case -eq 'health-unavailable'
    if ($case -notin 'partial-empty', 'partial-otp') {
        $global:resetPrepState.executions = @(
            [pscustomobject]@{id='otp'; providerId='knora-reset-email-otp'; requirement='DISABLED'},
            [pscustomobject]@{id='password'; providerId='reset-password'; requirement='DISABLED'}
        )
    } elseif ($case -eq 'partial-otp') {
        $global:resetPrepState.executions = @([pscustomobject]@{id='otp'; providerId='knora-reset-email-otp'; requirement='DISABLED'})
    }
    if ($case -eq 'unexpected-flow') { $global:resetPrepState.executions[0].providerId = 'unexpected' }
    switch ($case) {
        parent-link { $null = New-Item -ItemType Junction -Path "$copy/.verification" -Target $outside }
        runtime-link {
            $null = New-Item -ItemType Directory "$copy/.verification"
            $null = New-Item -ItemType Junction -Path $runtime -Target $outside
        }
        vault-link {
            $null = New-Item -ItemType Directory -Force $runtime
            $null = New-Item -ItemType Junction -Path "$runtime/vault" -Target $outside
        }
        default { $null = New-Item -ItemType Directory -Force "$runtime/vault" }
    }
    $digest = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes('knora-reset-regression'))).ToLowerInvariant()
    $entry = "$runtime/vault/knora-dev_knora-email-otp-hmac-$digest"
    $validKey = [Convert]::ToBase64String([byte[]](1..32))
    if ($case -eq 'long-valid-key') { $validKey = [Convert]::ToBase64String([byte[]](1..64)) }
    if ($case -in 'realm-link', 'key-link') {
        $global:resetPrepState.fileLink = $(if ($case -eq 'realm-link') { "$runtime/realm.json" } else { $entry })
        Set-Content -LiteralPath $global:resetPrepState.fileLink -Value 'sentinel'
    }
    if ($case -eq 'invalid-key') { [IO.File]::WriteAllText($entry, 'truncated') }
    if ($case -eq 'empty-key') { [IO.File]::WriteAllText($entry, '') }
    if ($case -eq 'short-key') { [IO.File]::WriteAllText($entry, [Convert]::ToBase64String([byte[]](1..16))) }
    if ($case -eq 'whitespace-key') { [IO.File]::WriteAllText($entry, $validKey.Insert(8, ' ')) }
    if ($case -in 'valid-key', 'long-valid-key') { [IO.File]::WriteAllText($entry, $validKey) }
    $caught = ''
    try { & "$copy/scripts/prepare-password-reset-regression.ps1" | Out-Null } catch { $caught = $_.Exception.Message }
    $ok = if ($case -like '*-link') {
        $caught -eq 'RESET_TEST_PATH_REJECTED' -and $global:resetPrepState.starts -eq 0 -and (Get-Content -Raw "$outside/realm.json").Trim() -eq 'sentinel'
    } elseif ($case -eq 'unexpected-flow') {
        $caught -like 'RESET_TEST_PREPARATION_FAILED_REQUIRE_EXECUTIONS_*' -and -not $global:resetPrepState.bound
    } elseif ($case -eq 'health-unavailable') {
        $caught -like 'RESET_TEST_PREPARATION_FAILED_API_HEALTH_*' -and $global:resetPrepState.healthCalls -eq 60
    } else {
        $key = [IO.File]::ReadAllText($entry)
        $keyValid = $false
        try { $keyValid = $key -cnotmatch '\s' -and [Convert]::FromBase64String($key).Length -ge 32 } catch {}
        -not $caught -and $global:resetPrepState.healthCalls -ge 3 -and $global:resetPrepState.required -eq 2 -and $global:resetPrepState.bound -and
            $keyValid -and ($case -notin 'valid-key', 'long-valid-key' -or $key -eq $validKey)
    }
    if (-not $ok) { $failed += $case }
}
if ($failed) { throw "RESET_TEST_PREPARATION_SELFCHECK_FAILED_$($failed -join ',')" }
Write-Output 'RESET_TEST_PREPARATION_SELFCHECK_PASSED_16'
