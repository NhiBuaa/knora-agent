$ErrorActionPreference = 'Stop'
$prepare = Join-Path $PSScriptRoot 'prepare-password-reset-regression.ps1'
$global:resetGuardCase = 'checkout'
$global:resetGuardMutated = $false
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') { return 'synthetic-container' }
    if ($args[0] -eq 'inspect') {
        return (@{
            Config = @{ Labels = @{
                'com.docker.compose.project' = $(if ($global:resetGuardCase -eq 'checkout') { 'knora-issue162' } else { 'another-session' })
                'com.docker.compose.project.working_dir' = 'C:/another-checkout'
                'com.docker.compose.project.config_files' = 'C:/another-checkout/docker-compose.yml'
            }}
            State = @{ Running = $true }
            NetworkSettings = @{ Ports = @{ '8080/tcp' = @(@{HostIp='127.0.0.1'; HostPort='8480'}) } }
        } | ConvertTo-Json -Depth 10)
    }
    $global:resetGuardMutated = $true
    throw 'UNEXPECTED_DOCKER_MUTATION'
}
foreach ($script:case in 'checkout', 'port', 'ambient') {
    $global:resetGuardCase = $script:case
    $expected = switch ($script:case) {
        checkout { 'RESET_TEST_CHECKOUT_OWNERSHIP_REQUIRED' }
        port { 'RESET_TEST_PORT_OWNERSHIP_REQUIRED' }
        ambient { 'RESET_TEST_AMBIENT_SELECTOR_REJECTED' }
    }
    if ($script:case -eq 'ambient') { $env:DOCKER_RESET_TEST_GUARD = 'synthetic' }
    try {
        $caught = ''
        try { & $prepare | Out-Null } catch { $caught = $_.Exception.Message }
        if ($caught -ne $expected -or $global:resetGuardMutated) { throw "RESET_TEST_GUARD_FAILED_$script:case" }
    } finally { Remove-Item Env:DOCKER_RESET_TEST_GUARD -ErrorAction SilentlyContinue }
}
Write-Output 'RESET_TEST_GUARDS_PASSED_3'
