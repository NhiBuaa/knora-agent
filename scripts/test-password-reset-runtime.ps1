param([switch]$IsolatedChild)
$ErrorActionPreference = 'Stop'
if (-not $IsolatedChild) {
    $sharedLock = Join-Path ([IO.Path]::GetTempPath()) 'knora-reset-reservation-knora-issue162.lock'
    $before = if (Test-Path -LiteralPath $sharedLock) { (Get-FileHash -LiteralPath $sharedLock).Hash } else { $null }
    $namespace = Join-Path ([IO.Path]::GetTempPath()) "knora-reset-selfcheck-$([guid]::NewGuid())"
    $null = New-Item -ItemType Directory -Path $namespace
    $start = [Diagnostics.ProcessStartInfo]::new((Get-Process -Id $PID).Path)
    foreach ($argument in @('-NoProfile','-File',$PSCommandPath,'-IsolatedChild')) { $start.ArgumentList.Add($argument) }
    $start.Environment['TEMP'] = $namespace
    $start.Environment['TMP'] = $namespace
    $start.Environment['KNORA_SELFCHECK_TEMP'] = $namespace
    $child = [Diagnostics.Process]::Start($start)
    $child.WaitForExit()
    $after = if (Test-Path -LiteralPath $sharedLock) { (Get-FileHash -LiteralPath $sharedLock).Hash } else { $null }
    if ($before -cne $after) { throw 'SELFCHECK_CHANGED_SHARED_RESERVATION' }
    if (-not [IO.Path]::GetFullPath($namespace).StartsWith([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) -or [IO.Path]::GetFullPath($namespace) -eq [IO.Path]::GetFullPath([IO.Path]::GetTempPath())) { throw 'SELFCHECK_TEMP_ESCAPE' }
    Remove-Item -LiteralPath $namespace -Recurse -Force
    if ($child.ExitCode -ne 0) { throw "SELFCHECK_CHILD_FAILED_$($child.ExitCode)" }
    return
}
if ([IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\','/') -ne [IO.Path]::GetFullPath($env:KNORA_SELFCHECK_TEMP).TrimEnd('\','/')) { throw 'SELFCHECK_TEMP_NOT_ISOLATED' }
$ErrorActionPreference = 'Stop'
$prepare = Join-Path $PSScriptRoot 'prepare-password-reset-regression.ps1'
$repositoryRoot = Split-Path $PSScriptRoot -Parent
$devCompose = Join-Path $repositoryRoot 'docker-compose.dev.yml'
$legacyCompose = Join-Path $repositoryRoot 'test/fixtures/password-reset/compose.yml'

$global:resetGuardCase = 'checkout'
$global:resetGuardMutated = $false

function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq '--host') { $args=@($args[2..($args.Count-1)]) }
    if ($args[0] -in 'volume','network' -and $args[1] -eq 'ls') { return }
    if ($args[0] -eq 'ps') {
        if ($global:resetGuardCase -eq 'inspect-fail') {
            $global:LASTEXITCODE = 1
            return
        }
        return 'c001'
    }
    if ($args[0] -eq 'inspect') {
        $workingDir = switch ($global:resetGuardCase) {
            'checkout' { 'C:/another-checkout' }
            'legacy-compose' { $repositoryRoot }
            default { $repositoryRoot }
        }
        $configFile = switch ($global:resetGuardCase) {
            'checkout' { 'C:/another-checkout/docker-compose.yml' }
            'legacy-compose' { $legacyCompose }
            default { $devCompose }
        }
        $project = switch ($global:resetGuardCase) {
            'port' { 'another-session' }
            'port-3400' { 'another-session' }
            default { 'knora-issue162' }
        }
        $hostPort = switch ($global:resetGuardCase) {
            'port-3400' { '3400' }
            default { '8480' }
        }
        return (@{
            Id = 'c001'
            Config = @{ Labels = @{
                'com.docker.compose.project' = $project
                'com.docker.compose.project.working_dir' = $workingDir
                'com.docker.compose.project.config_files' = $configFile
            }}
            State = @{ Running = $true }
            NetworkSettings = @{ Ports = @{ '8080/tcp' = @(@{HostIp='127.0.0.1'; HostPort=$hostPort}) } }
        } | ConvertTo-Json -Depth 10)
    }
    $global:resetGuardMutated = $true
    throw 'UNEXPECTED_DOCKER_MUTATION'
}

$cases = @('checkout', 'port', 'ambient', 'legacy-compose', 'port-3400', 'inspect-fail')
foreach ($script:case in $cases) {
    $global:resetGuardCase = $script:case
    $expected = switch ($script:case) {
        'checkout' { 'RESET_TEST_CHECKOUT_OWNERSHIP_REQUIRED' }
        'legacy-compose' { 'RESET_TEST_CHECKOUT_OWNERSHIP_REQUIRED' }
        'port' { 'RESET_TEST_PORT_OWNERSHIP_REQUIRED' }
        'port-3400' { 'RESET_TEST_PORT_OWNERSHIP_REQUIRED' }
        'ambient' { 'RESET_TEST_AMBIENT_SELECTOR_REJECTED' }
        'inspect-fail' { 'RESET_TEST_INSPECTION_FAILED' }
    }
    if ($script:case -eq 'ambient') { $env:DOCKER_RESET_TEST_GUARD = 'synthetic' }
    try {
        $caught = ''
        try { & $prepare | Out-Null } catch { $caught = $_.Exception.Message }
        if ($caught -ne $expected -or $global:resetGuardMutated) {
            throw "RESET_TEST_GUARD_FAILED_$script:case"
        }
    } finally {
        Remove-Item Env:DOCKER_RESET_TEST_GUARD -ErrorAction SilentlyContinue
    }
}
Write-Output "RESET_TEST_GUARDS_PASSED_$($cases.Count)"
