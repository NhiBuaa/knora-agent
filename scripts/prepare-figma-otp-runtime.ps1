param(
    [switch]$CheckConfigurationOnly,
    [Parameter(Mandatory)][string]$VaultPath,
    [string]$AdminUsername,
    [string]$AdminPassword
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$project = 'knora-figma-e2e'
$baseUrl = 'http://127.0.0.1:8380'
$realm = 'knora-dev'
$issuer = "$baseUrl/realms/$realm"

function Get-OtpCompose {
    param([array]$Arguments)
    $text = (& docker compose @Arguments config --format json) -join "`n"
    if ($LASTEXITCODE -ne 0) { throw 'OTP_COMPOSE_CONFIG_FAILED' }
    $text | ConvertFrom-Json
}

function Assert-OtpRuntimeOwnership {
    param([array]$Services)
    $owned = 0
    $ids = @(& docker ps -a --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0) { throw 'OTP_DOCKER_INSPECTION_FAILED' }
    foreach ($id in $ids) {
        $items = @((& docker inspect $id) | ConvertFrom-Json)
        if ($LASTEXITCODE -ne 0 -or $items.Count -ne 1) { throw 'OTP_DOCKER_INSPECTION_FAILED' }
        $container = $items[0]
        $labels = $container.Config.Labels
        $belongs = $labels.'com.docker.compose.project' -eq $project
        if ($belongs -or $container.Name -like '/knora-figma-e2e-*') {
            # Stopped, correctly owned historical proof containers are retained evidence.
            $retainedProof = $labels.'com.docker.compose.service' -in 'keycloak-proof', 'otp-commit-proxy' -and
                -not $container.State.Running
            if (-not $belongs -or ($labels.'com.docker.compose.service' -notin $Services -and -not $retainedProof) -or
                -not $labels.'com.docker.compose.project.working_dir' -or
                [IO.Path]::GetFullPath($labels.'com.docker.compose.project.working_dir') -ne $repositoryRoot) {
                throw 'OTP_RESOURCE_OWNERSHIP_REJECTED'
            }
        }
        if (-not $container.State.Running) { continue }
        foreach ($port in $container.NetworkSettings.Ports.PSObject.Properties) {
            foreach ($mapping in @($port.Value)) {
                if ($null -eq $mapping -or $mapping.HostPort -ne '8380') { continue }
                if (-not $belongs -or $labels.'com.docker.compose.service' -ne 'keycloak' -or
                    -not $labels.'com.docker.compose.project.working_dir' -or
                    [IO.Path]::GetFullPath($labels.'com.docker.compose.project.working_dir') -ne $repositoryRoot) {
                    throw 'OTP_RESOURCE_OWNERSHIP_REJECTED'
                }
                if ($port.Name -ne '8080/tcp' -or $mapping.HostIp -ne '127.0.0.1') {
                    throw 'OTP_PORT_OWNERSHIP_REJECTED'
                }
                $owned++
            }
        }
    }
    if ($owned -ne 1) { throw 'OTP_RUNNING_KEYCLOAK_REQUIRED' }
}

function Assert-OtpVaultBoundary {
    param([string]$Directory, [string]$EntryPath)
    # Follow neither directory junctions nor file links before secret access.
    $node = Get-Item -Force -LiteralPath $EntryPath
    while ($null -ne $node) {
        if ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'OTP_VAULT_ACCESS_REJECTED' }
        $node = if ($node -is [IO.FileInfo]) { $node.Directory } else { $node.Parent }
    }
    $gitRoot = @(& git -C $Directory rev-parse --show-toplevel 2>$null)
    $gitExit = $LASTEXITCODE
    if ($gitExit -eq 0) {
        if ($gitRoot.Count -ne 1) { throw 'OTP_VAULT_GIT_BOUNDARY_REJECTED' }
        $tracked = @(& git -C $gitRoot[0] ls-files -- $EntryPath 2>$null)
        if ($LASTEXITCODE -ne 0 -or $tracked.Count -gt 0) { throw 'OTP_VAULT_GIT_BOUNDARY_REJECTED' }
        # Check each path separately: check-ignore succeeds if just one input matches.
        foreach ($path in $Directory, $EntryPath) {
            & git -C $gitRoot[0] check-ignore --quiet --no-index -- $path 2>$null
            if ($LASTEXITCODE -ne 0) { throw 'OTP_VAULT_GIT_BOUNDARY_REJECTED' }
        }
    } elseif ($gitExit -eq 128) {
        # Exit 128 also means unsafe/corrupt Git: independently prove no enclosing .git.
        $ancestor = Get-Item -Force -LiteralPath $Directory
        while ($null -ne $ancestor) {
            if (Test-Path -LiteralPath (Join-Path $ancestor.FullName '.git')) {
                throw 'OTP_VAULT_GIT_BOUNDARY_REJECTED'
            }
            $ancestor = $ancestor.Parent
        }
    } else { throw 'OTP_VAULT_GIT_BOUNDARY_REJECTED' }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $allowed = @($identity, 'S-1-5-18', 'S-1-5-32-544')
    foreach ($path in $Directory, $EntryPath) {
        $acl = Get-Acl -LiteralPath $path
        if (-not $acl.AreAccessRulesProtected) { throw 'OTP_VAULT_ACCESS_REJECTED' }
        $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
        $canRead = $false
        foreach ($rule in $rules) {
            if ($rule.AccessControlType -eq 'Allow') {
                if ($rule.IdentityReference.Value -notin $allowed) { throw 'OTP_VAULT_ACCESS_REJECTED' }
                if ($rule.IdentityReference.Value -eq $identity -and
                    ([int]$rule.FileSystemRights -band [int][Security.AccessControl.FileSystemRights]::ReadData)) {
                    $canRead = $true
                }
            }
        }
        if (-not $canRead) { throw 'OTP_VAULT_ACCESS_REJECTED' }
    }
}

function Invoke-OtpRuntimeAdmin {
    param([string]$Uri)
    try { Invoke-RestMethod -Uri $Uri -Headers $headers -TimeoutSec 10 }
    catch { throw 'OTP_RUNTIME_ADMIN_REQUEST_FAILED' }
}

function New-OtpRuntimeHeaders {
    try {
        $token = Invoke-RestMethod -Method Post -Uri "$baseUrl/realms/master/protocol/openid-connect/token" -TimeoutSec 10 -ContentType 'application/x-www-form-urlencoded' -Body @{
            client_id = 'admin-cli'; grant_type = 'password'; username = $AdminUsername; password = $AdminPassword
        }
        if (-not $token.access_token) { throw 'token' }
        return @{ Authorization = "Bearer $($token.access_token)" }
    } catch { throw 'OTP_ADMIN_AUTHENTICATION_FAILED' }
}

try {
    # The ordinary harness remains authoritative and executes only its configuration path.
    & (Join-Path $PSScriptRoot 'prepare-figma-e2e.ps1') -CheckConfigurationOnly
    if ($LASTEXITCODE -ne 0) { throw 'OTP_BASE_CONFIGURATION_FAILED' }
    if (-not (Test-Path -LiteralPath $VaultPath -PathType Container)) { throw 'OTP_VAULT_PATH_REQUIRED' }
    $vaultDirectory = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $VaultPath).Path)
    if (-not $AdminUsername -or -not $AdminPassword) { throw 'OTP_ADMIN_CREDENTIALS_REQUIRED' }
    $baseArguments = @('--project-name', $project, '--project-directory', $repositoryRoot,
        '-f', (Join-Path $repositoryRoot 'docker-compose.figma-e2e.yml'))
    $base = Get-OtpCompose $baseArguments
    $services = @($base.services.PSObject.Properties.Name)
    Assert-OtpRuntimeOwnership $services
    $headers = New-OtpRuntimeHeaders
    $realmUri = "$baseUrl/admin/realms/$realm"
    $current = Invoke-OtpRuntimeAdmin $realmUri
    if ($current.realm -ne $realm -or -not $current.id -or -not $current.resetCredentialsFlow) {
        throw 'OTP_REALM_REPRESENTATION_REJECTED'
    }
    $realmId = $current.id
    $binding = $current.resetCredentialsFlow
    $hash = [Security.Cryptography.SHA256]::Create()
    try { $digest = [BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($realmId))).Replace('-', '').ToLowerInvariant() }
    finally { $hash.Dispose() }
    $entry = "knora-email-otp-hmac-$digest"
    $filename = $realm.Replace('_', '__') + '_' + $entry.Replace('_', '__')
    $entryPath = Join-Path $vaultDirectory $filename
    if (-not (Test-Path -LiteralPath $entryPath -PathType Leaf)) { throw 'OTP_VAULT_ENTRY_REQUIRED' }
    Assert-OtpVaultBoundary $vaultDirectory $entryPath
    if ((Get-Item -LiteralPath $entryPath).Length -gt 4096) { throw 'OTP_VAULT_KEY_INVALID' }
    $decoded = $null
    try {
        $encoded = [IO.File]::ReadAllText($entryPath).Trim()
        if ($encoded -cnotmatch '^[A-Za-z0-9+/]+={0,2}$') { throw 'format' }
        $decoded = [Convert]::FromBase64String($encoded)
        if ($decoded.Length -lt 32 -or [Convert]::ToBase64String($decoded) -cne $encoded) { throw 'length' }
    } catch { throw 'OTP_VAULT_KEY_INVALID' }
    finally {
        if ($null -ne $decoded) { [Array]::Clear($decoded, 0, $decoded.Length) }
        $encoded = $null
    }
    # Only the directory path enters Compose; no secret value is an environment variable.
    $previousVaultPath = $env:KNORA_FIGMA_OTP_VAULT_PATH
    $env:KNORA_FIGMA_OTP_VAULT_PATH = $vaultDirectory
    try {
        $compose = $baseArguments + @('-f', (Join-Path $repositoryRoot 'docker-compose.figma-otp-runtime.yml'))
        $config = Get-OtpCompose $compose
        if ($config.name -ne $project -or
            (@($config.services.PSObject.Properties.Name | Sort-Object) -join ',') -ne (@($services | Sort-Object) -join ',') -or
            ($config.volumes | ConvertTo-Json -Depth 30 -Compress) -ne ($base.volumes | ConvertTo-Json -Depth 30 -Compress) -or
            ($config | ConvertTo-Json -Depth 100 -Compress) -match 'storage-probe|KNORA_STORAGE_PROOF|otp-commit-proxy|keycloak-proof') {
            throw 'OTP_RUNTIME_GRAPH_REJECTED'
        }
        foreach ($service in $services) {
            if ($service -ne 'keycloak' -and
                ($config.services.$service | ConvertTo-Json -Depth 50 -Compress) -ne
                ($base.services.$service | ConvertTo-Json -Depth 50 -Compress)) { throw 'OTP_RUNTIME_GRAPH_REJECTED' }
        }
        $node = $config.services.keycloak
        foreach ($property in 'ports', 'environment', 'depends_on') {
            if (($node.$property | ConvertTo-Json -Depth 30 -Compress) -ne
                ($base.services.keycloak.$property | ConvertTo-Json -Depth 30 -Compress)) { throw 'OTP_RUNTIME_GRAPH_REJECTED' }
        }
        $expectedCommand = @('start-dev', '--vault=file', '--vault-dir=/opt/keycloak/vault',
            '--spi-theme--cache-themes=false', '--spi-theme--cache-templates=false', '--spi-theme--static-max-age=-1')
        if ($node.image -ne 'knora-figma-otp-runtime:26.3.3' -or
            [IO.Path]::GetFullPath($node.build.context) -ne $repositoryRoot -or
            $node.build.dockerfile -ne 'infra/keycloak/Dockerfile' -or
            (@($node.command) -join '|') -ne ($expectedCommand -join '|')) { throw 'OTP_RUNTIME_GRAPH_REJECTED' }
        $vaultMount = @($node.volumes | Where-Object target -eq '/opt/keycloak/vault')
        if ($vaultMount.Count -ne 1 -or $vaultMount[0].type -ne 'bind' -or
            -not $vaultMount[0].read_only -or $vaultMount[0].bind.create_host_path -ne $false -or
            [IO.Path]::GetFullPath($vaultMount[0].source) -ne $vaultDirectory) { throw 'OTP_VAULT_MOUNT_REJECTED' }
        $otherMounts = @($node.volumes | Where-Object target -ne '/opt/keycloak/vault')
        if (($otherMounts | ConvertTo-Json -Depth 30 -Compress) -ne
            (@($base.services.keycloak.volumes) | ConvertTo-Json -Depth 30 -Compress)) { throw 'OTP_RUNTIME_GRAPH_REJECTED' }
        if ($CheckConfigurationOnly) { Write-Output 'OTP_RUNTIME_CONFIG_OK'; return }
        Assert-OtpRuntimeOwnership $services
        $beforeStart = Invoke-OtpRuntimeAdmin $realmUri
        if ($beforeStart.id -ne $realmId -or $beforeStart.resetCredentialsFlow -ne $binding) {
            throw 'OTP_RUNTIME_REALM_CHANGED'
        }
        # No dependencies, migrations, flow preparation or reset binding changes.
        $null = & docker compose @compose up -d --build --no-deps keycloak 2>$null
        if ($LASTEXITCODE -ne 0) { throw 'OTP_RUNTIME_START_FAILED' }
        $ready = $false
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            try {
                $discovery = Invoke-RestMethod -Uri "$issuer/.well-known/openid-configuration" -TimeoutSec 3
                if ($discovery.issuer -eq $issuer) { $ready = $true; break }
            } catch { }
            Start-Sleep -Seconds 2
        }
        if (-not $ready) { throw 'OTP_RUNTIME_READINESS_FAILED' }
        Assert-OtpRuntimeOwnership $services
        # Image build/readiness may outlast the preflight token lifetime.
        $headers = New-OtpRuntimeHeaders
        $available = @(Invoke-OtpRuntimeAdmin "$realmUri/authentication/authenticator-providers")
        foreach ($provider in 'knora-reset-email-otp', 'reset-password') {
            if (@($available | Where-Object { $_.id -eq $provider }).Count -ne 1) { throw 'OTP_AUTHENTICATOR_REQUIRED' }
        }
        $verified = Invoke-OtpRuntimeAdmin $realmUri
        if ($verified.id -ne $realmId -or $verified.resetCredentialsFlow -ne $binding) {
            throw 'OTP_RUNTIME_REALM_CHANGED'
        }
        Write-Output 'OTP_RUNTIME_PREPARED_BINDING_PRESERVED'
    } finally { $env:KNORA_FIGMA_OTP_VAULT_PATH = $previousVaultPath }
} catch {
    $code = if ($_.Exception.Message -match '^(OTP_|FIGMA_)[A-Z_]+$') {
        $_.Exception.Message
    } else { 'OTP_RUNTIME_PREPARATION_FAILED' }
    throw $code
}
