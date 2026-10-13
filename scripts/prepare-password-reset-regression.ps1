$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$project = 'knora-issue162'
$compose = Join-Path $repositoryRoot 'test/fixtures/password-reset/compose.yml'
$runtime = Join-Path $repositoryRoot '.verification/password-reset'
if (-not $IsWindows) { throw 'RESET_TEST_WINDOWS_REQUIRED' }
foreach ($item in Get-ChildItem Env:) {
    if ($item.Name -match '^(DOCKER_|COMPOSE_)' -and $item.Value.Trim()) {
        throw 'RESET_TEST_AMBIENT_SELECTOR_REJECTED'
    }
}
# Refuse existing resources from a different checkout before preparing or starting anything.
$ids = @(& docker ps -a --format '{{.ID}}')
if ($LASTEXITCODE -ne 0) { throw 'RESET_TEST_INSPECTION_FAILED' }
foreach ($id in $ids) {
    $container = (& docker inspect $id | ConvertFrom-Json)[0]
    $belongs = $container.Config.Labels.'com.docker.compose.project' -eq $project
    if ($belongs -and ([IO.Path]::GetFullPath($container.Config.Labels.'com.docker.compose.project.working_dir') -ne $repositoryRoot -or
        [IO.Path]::GetFullPath($container.Config.Labels.'com.docker.compose.project.config_files') -ne $compose)) {
        throw 'RESET_TEST_CHECKOUT_OWNERSHIP_REQUIRED'
    }
    if ($container.State.Running) {
        foreach ($port in $container.NetworkSettings.Ports.PSObject.Properties) {
            foreach ($mapping in @($port.Value)) {
                if ($mapping.HostPort -in '8480', '8900', '8125' -and -not $belongs) {
                    throw 'RESET_TEST_PORT_OWNERSHIP_REQUIRED'
                }
            }
        }
    }
}
$vault = Join-Path $runtime 'vault'
$null = New-Item -ItemType Directory -Force $vault
if ((Get-Item -LiteralPath $vault).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'RESET_TEST_VAULT_REJECTED' }
$ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls $vault /inheritance:r /grant:r "*${ownerSid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'RESET_TEST_VAULT_REJECTED' }
$allowed = @($ownerSid, 'S-1-5-18', 'S-1-5-32-544')
foreach ($path in @($vault) + @(Get-ChildItem -LiteralPath $vault -Force | ForEach-Object FullName)) {
    $acl = Get-Acl -LiteralPath $path
    foreach ($rule in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
        if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin $allowed) { throw 'RESET_TEST_VAULT_REJECTED' }
    }
}
$fixture = Get-Content -Raw (Join-Path $repositoryRoot 'test/fixtures/keycloak/figma-realm.json') | ConvertFrom-Json
$fixture | Add-Member -NotePropertyName id -NotePropertyValue 'knora-reset-regression' -Force
$client = @($fixture.clients | Where-Object clientId -eq 'knora-web')[0]
$client.rootUrl = 'http://127.0.0.1:3400'
$client.baseUrl = 'http://127.0.0.1:3400'
$client.redirectUris = @('http://127.0.0.1:3400/api/auth/callback')
$client.webOrigins = @('http://127.0.0.1:3400')
$client.attributes.'post.logout.redirect.uris' = 'http://127.0.0.1:3400/'
$fixture.smtpServer.host = 'mail'
$fixture | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath (Join-Path $runtime 'realm.json') -Encoding utf8
$digest = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($fixture.id))).ToLowerInvariant()
$entry = Join-Path $runtime "vault/knora-dev_knora-email-otp-hmac-$digest"
if (-not (Test-Path -LiteralPath $entry)) {
    $bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    [IO.File]::WriteAllText($entry, [Convert]::ToBase64String($bytes))
    [Array]::Clear($bytes, 0, $bytes.Length)
}
if ((Get-Item -LiteralPath $entry).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'RESET_TEST_VAULT_REJECTED' }
& docker compose --project-name $project --project-directory $repositoryRoot -f $compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'RESET_TEST_START_FAILED' }
try {
    $stage = 'ADMIN_LOGIN'
    $token = $null
    for ($attempt = 0; $attempt -lt 60 -and $null -eq $token; $attempt++) {
        try {
            $token = Invoke-RestMethod -TimeoutSec 5 -Method Post 'http://127.0.0.1:8480/realms/master/protocol/openid-connect/token' -ContentType 'application/x-www-form-urlencoded' -Body @{
                client_id = 'admin-cli'; grant_type = 'password'; username = 'figma-test-admin'; password = 'figma-test-admin-password'
            }
        } catch { Start-Sleep -Seconds 2 }
    }
    if ($null -eq $token) { throw 'unavailable' }
    $headers = @{ Authorization = "Bearer $($token.access_token)" }
    $uri = 'http://127.0.0.1:8480/admin/realms/knora-dev'
    $stage = 'REALM_IDENTITY'
    $realm = Invoke-RestMethod $uri -Headers $headers -TimeoutSec 10
    if ($realm.id -ne $fixture.id) { throw 'realm' }
    $stage = 'INSTALL_FLOW'
    $flows = Invoke-RestMethod "$uri/authentication/flows" -Headers $headers -TimeoutSec 10
    if (-not @($flows | Where-Object alias -eq 'issue162-reset')) {
        $stage = 'CREATE_FLOW'
        Invoke-RestMethod -Method Post "$uri/authentication/flows" -Headers $headers -TimeoutSec 10 -ContentType 'application/json' -Body '{"alias":"issue162-reset","providerId":"basic-flow","topLevel":true,"builtIn":false}' | Out-Null
        foreach ($provider in 'knora-reset-email-otp', 'reset-password') {
            $stage = "ADD_EXECUTION_$provider"
            Invoke-RestMethod -Method Post "$uri/authentication/flows/issue162-reset/executions/execution" -Headers $headers -TimeoutSec 10 -ContentType 'application/json' -Body (@{provider=$provider} | ConvertTo-Json) | Out-Null
        }
    }
    $stage = 'REQUIRE_EXECUTIONS'
    $executions = Invoke-RestMethod "$uri/authentication/flows/issue162-reset/executions" -Headers $headers -TimeoutSec 10
    if ($executions.Count -ne 2 -or $executions[0].providerId -ne 'knora-reset-email-otp' -or $executions[1].providerId -ne 'reset-password') { throw 'flow' }
    foreach ($execution in $executions) {
        $execution.requirement = 'REQUIRED'
        Invoke-RestMethod -Method Put "$uri/authentication/flows/issue162-reset/executions" -Headers $headers -TimeoutSec 10 -ContentType 'application/json' -Body ($execution | ConvertTo-Json -Depth 10) | Out-Null
    }
    $stage = 'BIND_FLOW'
    Invoke-RestMethod -Method Put $uri -Headers $headers -TimeoutSec 10 -ContentType 'application/json' -Body '{"resetCredentialsFlow":"issue162-reset","emailTheme":"knora"}' | Out-Null
} catch { throw "RESET_TEST_PREPARATION_FAILED_${stage}_$([int]$_.Exception.Response.StatusCode)" }
Write-Output 'RESET_TEST_READY'
