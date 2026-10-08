param(
    [ValidateSet('Inspect', 'Diff', 'Prepare', 'Bind', 'Restore')][string]$Mode = 'Inspect',
    [string]$BaseUrl = 'http://127.0.0.1:8380',
    [string]$Realm = 'knora-dev',
    [string]$Project = 'knora-figma-e2e',
    [string]$AdminUsername,
    [string]$AdminPassword,
    [switch]$EnableIsolatedOtp,
    [string]$SnapshotPath
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$alias = 'knora-email-otp-reset'
$description = 'Knora isolated email OTP recovery v1'
$providers = @('knora-reset-email-otp', 'reset-password')

function Invoke-OtpAdmin {
    param([string]$Method = 'Get', [string]$Uri, $Payload)
    try {
        $parameters = @{ Method = $Method; Uri = $Uri; Headers = $headers; TimeoutSec = 10 }
        if ($null -ne $Payload) {
            $parameters.ContentType = 'application/json'
            $parameters.Body = $Payload | ConvertTo-Json -Depth 20
        }
        Invoke-RestMethod @parameters
    } catch { throw 'OTP_ADMIN_REQUEST_FAILED' }
}

function Assert-OtpNativeContainer {
    param($Container)
    $expectedCommand = @('start-dev', '--vault=file', '--vault-dir=/opt/keycloak/vault',
        '--spi-theme--cache-themes=false', '--spi-theme--cache-templates=false', '--spi-theme--static-max-age=-1')
    if ($Container.Config.Image -ne 'knora-figma-otp-runtime:26.3.3' -or
        (@($Container.Config.Entrypoint) -join '|') -ne '/opt/keycloak/bin/kc.sh' -or
        (@($Container.Config.Cmd) -join '|') -ne ($expectedCommand -join '|')) {
        throw 'OTP_NATIVE_RUNTIME_REQUIRED'
    }
    $configFiles = @($Container.Config.Labels.'com.docker.compose.project.config_files' -split ',')
    $expectedFiles = @('docker-compose.figma-e2e.yml', 'docker-compose.figma-otp-runtime.yml')
    if ($configFiles.Count -ne 2) { throw 'OTP_NATIVE_RUNTIME_REQUIRED' }
    for ($index = 0; $index -lt 2; $index++) {
        if (-not $configFiles[$index] -or
            [IO.Path]::GetFullPath($configFiles[$index]) -ne (Join-Path $repositoryRoot $expectedFiles[$index])) {
            throw 'OTP_NATIVE_RUNTIME_REQUIRED'
        }
    }
    # Inspect metadata stays in process; environment values and mount payloads are never emitted.
    foreach ($entry in @($Container.Config.Env)) {
        if ($entry -match '^KNORA_STORAGE_PROOF[^=]*=') { throw 'OTP_NATIVE_RUNTIME_REQUIRED' }
    }
    $mounts = @($Container.Mounts)
    if ($mounts.Count -ne 3) { throw 'OTP_NATIVE_RUNTIME_REQUIRED' }
    $expectedSources = @{
        '/opt/keycloak/data/import/knora-dev-realm.json' = Join-Path $repositoryRoot 'test/fixtures/keycloak/figma-realm.json'
        '/opt/keycloak/themes/knora' = Join-Path $repositoryRoot 'themes/knora'
    }
    foreach ($target in '/opt/keycloak/data/import/knora-dev-realm.json', '/opt/keycloak/themes/knora', '/opt/keycloak/vault') {
        $matching = @($mounts | Where-Object Destination -eq $target)
        if ($matching.Count -ne 1 -or $matching[0].Type -ne 'bind' -or
            $matching[0].RW -ne $false -or -not $matching[0].Source) { throw 'OTP_NATIVE_RUNTIME_REQUIRED' }
        if ($target -ne '/opt/keycloak/vault' -and
            [IO.Path]::GetFullPath($matching[0].Source) -ne $expectedSources[$target]) {
            throw 'OTP_NATIVE_RUNTIME_REQUIRED'
        }
    }
}

function Assert-OtpOwnership {
    param([switch]$RequireNativeRuntime)
    $owned = 0
    $ids = @(& docker ps -a --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0) { throw 'OTP_DOCKER_INSPECTION_FAILED' }
    foreach ($id in $ids) {
        $items = @((& docker inspect $id) | ConvertFrom-Json)
        if ($LASTEXITCODE -ne 0 -or $items.Count -ne 1) { throw 'OTP_DOCKER_INSPECTION_FAILED' }
        $container = $items[0]
        $labels = $container.Config.Labels
        $isNamedTarget = $container.Name -eq '/knora-figma-e2e-keycloak-1'
        if ($RequireNativeRuntime -and ($labels.'com.docker.compose.project' -eq $Project -or
            $container.Name -like '/knora-figma-e2e-*')) {
            if ($labels.'com.docker.compose.project' -ne $Project -or
                -not $labels.'com.docker.compose.project.working_dir' -or
                [IO.Path]::GetFullPath($labels.'com.docker.compose.project.working_dir') -ne $repositoryRoot) {
                throw 'OTP_RESOURCE_OWNERSHIP_REJECTED'
            }
            $service = $labels.'com.docker.compose.service'
            if ($service -in 'keycloak-proof', 'otp-commit-proxy') {
                if ($container.State.Running -ne $false) { throw 'OTP_ACTIVE_PROOF_REJECTED' }
            } elseif ($service -notin 'postgres', 'keycloak-db', 'keycloak', 'mail', 'minio', 'minio-init', 'api') {
                throw 'OTP_NATIVE_RUNTIME_REQUIRED'
            }
        }
        foreach ($port in $container.NetworkSettings.Ports.PSObject.Properties) {
            foreach ($mapping in @($port.Value)) {
                if ($null -eq $mapping -or $mapping.HostPort -ne '8380') { continue }
                if ($labels.'com.docker.compose.project' -ne $Project -or
                    $labels.'com.docker.compose.service' -ne 'keycloak' -or
                    -not $labels.'com.docker.compose.project.working_dir' -or
                    [IO.Path]::GetFullPath($labels.'com.docker.compose.project.working_dir') -ne $repositoryRoot) {
                    throw 'OTP_RESOURCE_OWNERSHIP_REJECTED'
                }
                if ($mapping.HostIp -ne '127.0.0.1' -or $port.Name -ne '8080/tcp') {
                    throw 'OTP_PORT_OWNERSHIP_REJECTED'
                }
                if (-not $container.State.Running) { throw 'OTP_RUNNING_KEYCLOAK_REQUIRED' }
                if ($RequireNativeRuntime) { Assert-OtpNativeContainer $container }
                $owned++
            }
        }
        if ($isNamedTarget -and ($labels.'com.docker.compose.project' -ne $Project -or
            $labels.'com.docker.compose.service' -ne 'keycloak' -or
            -not $labels.'com.docker.compose.project.working_dir' -or
            [IO.Path]::GetFullPath($labels.'com.docker.compose.project.working_dir') -ne $repositoryRoot)) {
            throw 'OTP_RESOURCE_OWNERSHIP_REJECTED'
        }
    }
    if ($owned -ne 1) { throw 'OTP_RUNNING_KEYCLOAK_REQUIRED' }
}

function Assert-OtpFlow {
    param($Flow, [array]$Executions)
    if ($Flow.description -ne $description -or $Flow.providerId -ne 'basic-flow' -or
        $Flow.builtIn -ne $false -or $Flow.topLevel -ne $true -or -not $Flow.id -or
        $Executions.Count -ne 2) { throw 'OTP_FLOW_CONFLICT' }
    for ($index = 0; $index -lt 2; $index++) {
        $execution = $Executions[$index]
        if (-not $execution.id -or $execution.providerId -ne $providers[$index] -or
            $execution.requirement -ne 'REQUIRED' -or
            ($null -ne $execution.authenticationFlow -and $execution.authenticationFlow -ne $false) -or
            $execution.level -ne 0 -or $execution.index -ne $index -or
            $execution.priority -ne (10 * ($index + 1))) { throw 'OTP_FLOW_CONFLICT' }
    }
    if ($Executions[0].id -eq $Executions[1].id) { throw 'OTP_FLOW_CONFLICT' }
}

try {
    if ($BaseUrl -ne 'http://127.0.0.1:8380' -or $Realm -ne 'knora-dev' -or
        $Project -ne 'knora-figma-e2e') {
        throw 'OTP_EXACT_TARGET_REQUIRED'
    }
    foreach ($item in Get-ChildItem Env:) {
        if ($item.Name -match '^(COMPOSE_|FIGMA_E2E_|M5_E2E_|KEYCLOAK_|KNORA_|DOCKER_|SESSION_SECRET$)' -and $item.Value.Trim()) {
            throw 'OTP_AMBIENT_OVERRIDE_REJECTED'
        }
    }
    if ($Mode -eq 'Bind' -and -not $EnableIsolatedOtp) { throw 'OTP_BIND_OPT_IN_REQUIRED' }
    if (-not $AdminUsername -or -not $AdminPassword) { throw 'OTP_ADMIN_CREDENTIALS_REQUIRED' }
    Assert-OtpOwnership
    try {
        $token = Invoke-RestMethod -Method Post -Uri "$BaseUrl/realms/master/protocol/openid-connect/token" -TimeoutSec 10 -ContentType 'application/x-www-form-urlencoded' -Body @{
            client_id = 'admin-cli'; grant_type = 'password'; username = $AdminUsername; password = $AdminPassword
        }
        if (-not $token.access_token) { throw 'token' }
    } catch { throw 'OTP_ADMIN_AUTHENTICATION_FAILED' }
    $headers = @{ Authorization = "Bearer $($token.access_token)" }
    $realmUri = "$BaseUrl/admin/realms/$Realm"
    $current = Invoke-OtpAdmin -Uri $realmUri
    if ($current.realm -ne $Realm -or -not $current.id -or -not $current.resetCredentialsFlow) {
        throw 'OTP_REALM_REPRESENTATION_REJECTED'
    }
    $realmId = $current.id
    $settings = @{
        resetCredentialsFlow = $current.resetCredentialsFlow
        emailTheme = $current.emailTheme
        resetPasswordAllowed = $current.resetPasswordAllowed
    }
    $desired = @{ resetCredentialsFlow = $alias; emailTheme = 'knora'; resetPasswordAllowed = $true }
    if ($Mode -ne 'Restore') {
        $installed = @(Invoke-OtpAdmin -Uri "$realmUri/authentication/authenticator-providers")
        foreach ($provider in $providers) {
            if (@($installed | Where-Object id -eq $provider).Count -ne 1) { throw 'OTP_AUTHENTICATOR_REQUIRED' }
        }
        $actions = @(Invoke-OtpAdmin -Uri "$realmUri/authentication/required-actions")
        if (@($actions | Where-Object { $_.alias -eq 'UPDATE_PASSWORD' -and
            $_.providerId -eq 'UPDATE_PASSWORD' -and $_.enabled -eq $true }).Count -ne 1) {
            throw 'OTP_NATIVE_UPDATE_PASSWORD_REQUIRED'
        }
        $flows = @(Invoke-OtpAdmin -Uri "$realmUri/authentication/flows" | Where-Object alias -eq $alias)
        if ($flows.Count -gt 1) { throw 'OTP_FLOW_CONFLICT' }
        $executions = @()
        if ($flows.Count -eq 1) {
            $executions = @(Invoke-OtpAdmin -Uri "$realmUri/authentication/flows/$alias/executions")
            Assert-OtpFlow $flows[0] $executions
        }
        if ($Mode -in 'Inspect', 'Diff') {
            # Only approved settings and execution metadata leave the process.
            @{ target = "$BaseUrl/realms/$Realm"; realmId = $realmId; project = $Project
                flowPresent = ($flows.Count -eq 1); settings = $settings; desired = $desired } | ConvertTo-Json -Depth 10
            return
        }
        if ($Mode -eq 'Prepare') {
            if ($flows.Count -eq 1) { Write-Output 'OTP_FLOW_ALREADY_PREPARED'; return }
            if ($current.resetCredentialsFlow -eq $alias) { throw 'OTP_FLOW_CONFLICT' }
            $null = Invoke-OtpAdmin -Method Post -Uri "$realmUri/authentication/flows" -Payload @{
                alias = $alias; description = $description; providerId = 'basic-flow'; topLevel = $true; builtIn = $false
            }
            for ($index = 0; $index -lt 2; $index++) {
                $null = Invoke-OtpAdmin -Method Post -Uri "$realmUri/authentication/flows/$alias/executions/execution" -Payload @{
                    provider = $providers[$index]; priority = (10 * ($index + 1))
                }
            }
            $executions = @(Invoke-OtpAdmin -Uri "$realmUri/authentication/flows/$alias/executions")
            if ($executions.Count -ne 2) { throw 'OTP_FLOW_CONFLICT' }
            for ($index = 0; $index -lt 2; $index++) {
                if (-not $executions[$index].id -or $executions[$index].providerId -ne $providers[$index] -or
                    ($null -ne $executions[$index].authenticationFlow -and $executions[$index].authenticationFlow -ne $false) -or
                    $executions[$index].level -ne 0) {
                    throw 'OTP_FLOW_CONFLICT'
                }
                $null = Invoke-OtpAdmin -Method Put -Uri "$realmUri/authentication/flows/$alias/executions" -Payload @{
                    id = $executions[$index].id; requirement = 'REQUIRED'; priority = (10 * ($index + 1))
                }
            }
            $flows = @(Invoke-OtpAdmin -Uri "$realmUri/authentication/flows" | Where-Object alias -eq $alias)
            if ($flows.Count -ne 1) { throw 'OTP_FLOW_CONFLICT' }
            Assert-OtpFlow $flows[0] @(Invoke-OtpAdmin -Uri "$realmUri/authentication/flows/$alias/executions")
            $verified = Invoke-OtpAdmin -Uri $realmUri
            if ($verified.id -ne $realmId -or $verified.resetCredentialsFlow -ne $settings.resetCredentialsFlow) {
                throw 'OTP_PREPARE_BINDING_CHANGED'
            }
            Write-Output 'OTP_FLOW_PREPARED_UNBOUND'
            return
        }
        if ($flows.Count -ne 1) { throw 'OTP_PREPARED_FLOW_REQUIRED' }
        # Standalone Bind must enforce the native activation contract itself, including no-op Bind.
        Assert-OtpOwnership -RequireNativeRuntime
        if ($current.resetCredentialsFlow -eq $alias -and $current.emailTheme -eq 'knora' -and
            $current.resetPasswordAllowed -eq $true) { Write-Output 'OTP_BIND_ALREADY_SET'; return }
        if ($current.resetCredentialsFlow -eq $alias) { throw 'OTP_BOUND_SETTINGS_CONFLICT' }
        if (-not $SnapshotPath) {
            $folder = Join-Path $repositoryRoot '.superpowers/sdd/2026-10-08-figma-otp-native-runtime/snapshots'
            $null = New-Item -ItemType Directory -Force -Path $folder
            $SnapshotPath = Join-Path $folder "binding-$([DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fffffff')).json"
        }
        $saved = @{ baseUrl = $BaseUrl; realm = $Realm; realmId = $realmId; project = $Project
            workingDirectory = $repositoryRoot; settings = $settings }
        if (Test-Path -LiteralPath $SnapshotPath) { throw 'OTP_SNAPSHOT_ALREADY_EXISTS' }
        $stream = [IO.File]::Open($SnapshotPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try {
            $bytes = [Text.Encoding]::UTF8.GetBytes(($saved | ConvertTo-Json -Depth 10))
            $stream.Write($bytes, 0, $bytes.Length)
        } finally { $stream.Dispose() }
        Write-Output "OTP_RESTORE_SNAPSHOT=$SnapshotPath"
    } else {
        if (-not $SnapshotPath) { throw 'OTP_SNAPSHOT_REQUIRED' }
        $saved = Get-Content -Raw -LiteralPath $SnapshotPath | ConvertFrom-Json
        if ($saved.baseUrl -ne $BaseUrl -or $saved.realm -ne $Realm -or $saved.realmId -ne $realmId -or
            $saved.project -ne $Project -or $saved.workingDirectory -ne $repositoryRoot -or
            (@($saved.settings.PSObject.Properties.Name | Sort-Object) -join ',') -ne 'emailTheme,resetCredentialsFlow,resetPasswordAllowed' -or
            -not $saved.settings.resetCredentialsFlow -or $saved.settings.resetCredentialsFlow -eq $alias -or
            $saved.settings.resetPasswordAllowed -isnot [bool]) { throw 'OTP_SNAPSHOT_TARGET_REJECTED' }
        $desired = @{
            resetCredentialsFlow = $saved.settings.resetCredentialsFlow
            emailTheme = if ($null -eq $saved.settings.emailTheme) { '' } else { $saved.settings.emailTheme }
            resetPasswordAllowed = $saved.settings.resetPasswordAllowed
        }
    }
    try {
        $beforeWrite = Invoke-OtpAdmin -Uri $realmUri
        if ($beforeWrite.id -ne $realmId) { throw 'id' }
        Assert-OtpOwnership -RequireNativeRuntime:($Mode -eq 'Bind')
        $null = Invoke-OtpAdmin -Method Put -Uri $realmUri -Payload $desired
        $verified = Invoke-OtpAdmin -Uri $realmUri
        if ($verified.id -ne $realmId) { throw 'id' }
        foreach ($name in $desired.Keys) {
            if ($verified.$name -ne $desired[$name] -and -not
                ($name -eq 'emailTheme' -and -not $verified.$name -and -not $desired[$name])) { throw 'setting' }
        }
    } catch { throw 'OTP_UPDATE_OR_VERIFICATION_FAILED; retain the saved snapshot' }
    Write-Output "OTP_$($Mode.ToUpperInvariant())_VERIFIED"
} catch {
    # Raw HTTP/Docker/file exceptions can contain response bodies or credentials.
    $code = if ($_.Exception.Message -match '^OTP_[A-Z_]+(?:; retain the saved snapshot)?$') {
        $_.Exception.Message
    } else { 'OTP_CONFIGURATION_FAILED' }
    throw $code
}
