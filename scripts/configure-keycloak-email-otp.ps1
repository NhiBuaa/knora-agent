param(
    [ValidateSet('Inspect', 'Diff', 'Prepare', 'Bind', 'Restore')][string]$Mode = 'Inspect',
    [string]$BaseUrl = 'http://127.0.0.1:8380',
    [string]$Realm = 'knora-dev',
    [string]$Project = 'knora-figma-e2e',
    [string]$AdminUsername,
    [string]$AdminPassword,
    [switch]$EnableIsolatedOtp,
    [switch]$EnablePrimaryOtp,
    [switch]$ConfigurePrimarySmtp,
    [string]$TestPrimarySmtpRecipient,
    [string]$SnapshotPath
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$alias = 'knora-email-otp-reset'
$description = 'Knora isolated email OTP recovery v1'
$providers = @('knora-reset-email-otp', 'reset-password')
$primaryTarget = $EnablePrimaryOtp.IsPresent
$expectedPort = if ($primaryTarget) { '8180' } else { '8380' }
$expectedService = if ($primaryTarget) { 'keycloak-dev' } else { 'figma-keycloak' }

function Import-PrimaryDotEnv {
    if (-not $primaryTarget -or -not $ConfigurePrimarySmtp) { return }
    $path = Join-Path $repositoryRoot '.env'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return }
    foreach ($rawLine in Get-Content -LiteralPath $path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith('#')) { continue }
        $separator = $line.IndexOf('=')
        if ($separator -le 0) {
            if ($line -match '^KC_SMTP_') { throw 'OTP_DOTENV_ENTRY_INVALID' }
            continue
        }
        $name = $line.Substring(0, $separator).Trim()
        if ($name -notmatch '^KC_SMTP_(HOST|PORT|FROM|USER|PASSWORD|STARTTLS|AUTH)$') { continue }
        if ($null -ne [Environment]::GetEnvironmentVariable($name, [EnvironmentVariableTarget]::Process)) {
            continue
        }
        $value = $line.Substring($separator + 1).Trim()
        if ($value.Length -ge 2 -and
            (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($name, $value, [EnvironmentVariableTarget]::Process)
    }
}

function Convert-KeycloakBoolean {
    param($Value)
    if ($Value -is [bool]) { return $Value }
    if ($null -eq $Value) { return $false }
    return ([string]$Value).Trim().ToLowerInvariant() -eq 'true'
}

function Get-SmtpMetadata {
    param($RealmRepresentation)
    $smtp = $RealmRepresentation.smtpServer
    if ($null -eq $smtp) {
        return @{ configured = $false; host = ''; port = ''; from = ''; user = ''
            auth = $false; starttls = $false; passwordConfigured = $false }
    }
    $starttls = if ($null -ne $smtp.starttls) { $smtp.starttls } else { $smtp.startTls }
    return @{ configured = [bool]($smtp.host -or $smtp.port -or $smtp.from -or $smtp.user -or $smtp.password)
        host = if ($null -eq $smtp.host) { '' } else { [string]$smtp.host }
        port = if ($null -eq $smtp.port) { '' } else { [string]$smtp.port }
        from = if ($null -eq $smtp.from) { '' } else { [string]$smtp.from }
        user = if ($null -eq $smtp.user) { '' } else { [string]$smtp.user }
        auth = Convert-KeycloakBoolean $smtp.auth
        starttls = Convert-KeycloakBoolean $starttls
        passwordConfigured = ($null -ne $smtp.password -and [string]$smtp.password -ne '') }
}

function Convert-SmtpRestoreValue {
    param($Metadata)
    if ($null -eq $Metadata -or -not $Metadata.configured) { return @{} }
    $value = @{ host = $Metadata.host; port = $Metadata.port; from = $Metadata.from; user = $Metadata.user
        auth = if (Convert-KeycloakBoolean $Metadata.auth) { 'true' } else { 'false' }
        starttls = if (Convert-KeycloakBoolean $Metadata.starttls) { 'true' } else { 'false' } }
    if (Convert-KeycloakBoolean $Metadata.passwordConfigured) {
        $password = [Environment]::GetEnvironmentVariable('KC_SMTP_RESTORE_PASSWORD')
        if ($null -eq $password -or [string]::IsNullOrWhiteSpace($password)) {
            throw 'OTP_SMTP_RESTORE_SECRET_REQUIRED'
        }
        $value.password = $password
    }
    return $value
}

function Get-PrimarySmtpContract {
    if (-not $primaryTarget -or -not $ConfigurePrimarySmtp) { return $null }
    $required = @('KC_SMTP_HOST', 'KC_SMTP_PORT', 'KC_SMTP_FROM', 'KC_SMTP_USER',
        'KC_SMTP_PASSWORD', 'KC_SMTP_STARTTLS', 'KC_SMTP_AUTH')
    foreach ($name in $required) {
        $item = [Environment]::GetEnvironmentVariable($name)
        if ($null -eq $item -or [string]::IsNullOrWhiteSpace($item)) {
            throw 'OTP_SMTP_CONFIGURATION_REQUIRED'
        }
    }
    if ($env:KC_SMTP_HOST -cne 'smtp.gmail.com' -or $env:KC_SMTP_PORT -cne '587' -or
        $env:KC_SMTP_STARTTLS -notmatch '^(?i:true)$' -or $env:KC_SMTP_AUTH -notmatch '^(?i:true)$') {
        throw 'OTP_SMTP_CONFIGURATION_INVALID'
    }
    return @{ host = 'smtp.gmail.com'; port = '587'; from = [string]$env:KC_SMTP_FROM
        user = [string]$env:KC_SMTP_USER; password = [string]$env:KC_SMTP_PASSWORD
        starttls = 'true'; auth = 'true' }
}

function Invoke-OtpAdmin {
    param([string]$Method = 'Get', [string]$Uri, $Payload)
    try {
        $parameters = @{ Method = $Method; Uri = $Uri; Headers = $headers; TimeoutSec = 10 }
        if ($null -ne $Payload) {
            $parameters.ContentType = 'application/json'
            $parameters.Body = $Payload | ConvertTo-Json -Depth 20
        }
        Invoke-RestMethod @parameters | ForEach-Object { $_ }
    } catch { throw 'OTP_ADMIN_REQUEST_FAILED' }
}

function Get-OtpClient {
    $matches = @(Invoke-OtpAdmin -Uri "$realmUri/clients?clientId=knora-web")
    if ($matches.Count -ne 1 -or $matches[0].clientId -ne 'knora-web' -or -not $matches[0].id) {
        throw 'OTP_CLIENT_REPRESENTATION_REJECTED'
    }
    return $matches[0]
}

function Test-OtpClientOrigin {
    param($Actual, $Expected)
    if ($null -eq $Expected -or $Expected -ceq '') {
        return ($null -eq $Actual -or ($Actual -is [string] -and $Actual -ceq ''))
    }
    return ($Actual -is [string] -and $Actual -ceq $Expected)
}

function Set-OtpClientOrigins {
    param($ExpectedId, $Origins)
    $before = Get-OtpClient
    if ($before.id -ne $ExpectedId) { throw 'OTP_CLIENT_REPRESENTATION_REJECTED' }
    $redirects = ConvertTo-Json -InputObject @($before.redirectUris) -Compress
    $webOrigins = ConvertTo-Json -InputObject @($before.webOrigins) -Compress
    # Pinned Keycloak ignores JSON null URL updates. Empty string explicitly clears.
    $payload = @{
        baseUrl = if ($null -eq $Origins.baseUrl) { '' } else { $Origins.baseUrl }
        rootUrl = if ($null -eq $Origins.rootUrl) { '' } else { $Origins.rootUrl }
    }
    $null = Invoke-OtpAdmin -Method Put -Uri "$realmUri/clients/$ExpectedId" -Payload $payload
    $after = Get-OtpClient
    if ($after.id -ne $ExpectedId -or -not (Test-OtpClientOrigin $after.baseUrl $Origins.baseUrl) -or
        -not (Test-OtpClientOrigin $after.rootUrl $Origins.rootUrl) -or
        (ConvertTo-Json -InputObject @($after.redirectUris) -Compress) -cne $redirects -or
        (ConvertTo-Json -InputObject @($after.webOrigins) -Compress) -cne $webOrigins) {
        throw 'OTP_CLIENT_ORIGIN_VERIFICATION_FAILED'
    }
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
    $expectedFiles = @('docker-compose.dev.yml')
    if ($configFiles.Count -ne 1) { throw 'OTP_NATIVE_RUNTIME_REQUIRED' }
    for ($index = 0; $index -lt 1; $index++) {
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

function Assert-OtpPrimaryContainer {
    param($Container)
    $expectedCommand = @('start-dev', '--import-realm', '--vault=file', '--vault-dir=/opt/keycloak/vault')
    $command = @($Container.Config.Cmd) -join '|'
    if ((@($Container.Config.Entrypoint) -join '|') -ne '/opt/keycloak/bin/kc.sh' -or
        $command -ne ($expectedCommand -join '|') -or
        'KC_DB=postgres' -notin @($Container.Config.Env) -or
        'KC_DB_URL=jdbc:postgresql://keycloak-dev-db:5432/keycloak' -notin @($Container.Config.Env) -or
        'KC_HOSTNAME=http://127.0.0.1:8180' -notin @($Container.Config.Env)) {
        throw 'OTP_PRIMARY_RUNTIME_REQUIRED'
    }
    $vault = @($Container.Mounts | Where-Object Destination -eq '/opt/keycloak/vault')
    if ($vault.Count -ne 1 -or $vault[0].Type -ne 'bind' -or $vault[0].RW -ne $false) {
        throw 'OTP_PRIMARY_RUNTIME_REQUIRED'
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
        $isNamedTarget = $container.Name -eq '/knora-figma-e2e-figma-keycloak-1'
        if ($RequireNativeRuntime -and -not $primaryTarget -and
            ($labels.'com.docker.compose.project' -eq $Project -or
            $container.Name -like '/knora-figma-e2e-*')) {
            if ($labels.'com.docker.compose.project' -ne $Project -or
                -not $labels.'com.docker.compose.project.working_dir' -or
                [IO.Path]::GetFullPath($labels.'com.docker.compose.project.working_dir') -ne $repositoryRoot) {
                throw 'OTP_RESOURCE_OWNERSHIP_REJECTED'
            }
            $service = $labels.'com.docker.compose.service'
            if ($service -in 'figma-keycloak-proof', 'figma-keycloak-proof-main', 'otp-commit-proxy', 'keycloak-proof') {
                if ($container.State.Running -ne $false) { throw 'OTP_ACTIVE_PROOF_REJECTED' }
            } elseif ($service -in 'postgres', 'keycloak-db', 'keycloak', 'mail', 'minio', 'minio-init', 'api') {
                if ($container.State.Running -ne $false) { throw 'OTP_NATIVE_RUNTIME_REQUIRED' }
            } elseif ($service -notin 'figma-postgres', 'figma-keycloak-db', 'figma-keycloak', 'figma-mail', 'figma-minio', 'figma-minio-init', 'figma-api') {
                throw 'OTP_NATIVE_RUNTIME_REQUIRED'
            }
        }
        foreach ($port in $container.NetworkSettings.Ports.PSObject.Properties) {
            foreach ($mapping in @($port.Value)) {
                if ($null -eq $mapping -or $mapping.HostPort -ne $expectedPort) { continue }
                if ($labels.'com.docker.compose.project' -ne $Project -or
                    $labels.'com.docker.compose.service' -ne $expectedService -or
                    -not $labels.'com.docker.compose.project.working_dir' -or
                    [IO.Path]::GetFullPath($labels.'com.docker.compose.project.working_dir') -ne $repositoryRoot) {
                    throw 'OTP_RESOURCE_OWNERSHIP_REJECTED'
                }
                if ($mapping.HostIp -ne '127.0.0.1' -or $port.Name -ne '8080/tcp') {
                    throw 'OTP_PORT_OWNERSHIP_REJECTED'
                }
                if (-not $container.State.Running) { throw 'OTP_RUNNING_KEYCLOAK_REQUIRED' }
                if ($RequireNativeRuntime) {
                    if ($primaryTarget) { Assert-OtpPrimaryContainer $container }
                    else { Assert-OtpNativeContainer $container }
                }
                $owned++
            }
        }
        if ($isNamedTarget -and ($labels.'com.docker.compose.project' -ne $Project -or
            $labels.'com.docker.compose.service' -ne $expectedService -or
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
    Import-PrimaryDotEnv
    if ($primaryTarget) {
        if ($BaseUrl -ne 'http://127.0.0.1:8180' -or $Realm -ne 'knora-dev' -or $Project -ne 'knora-dev') {
            throw 'OTP_PRIMARY_TARGET_REQUIRED'
        }
    } elseif ($BaseUrl -ne 'http://127.0.0.1:8380' -or $Realm -ne 'knora-dev' -or
        $Project -ne 'knora-figma-e2e') { throw 'OTP_EXACT_TARGET_REQUIRED' }
    if (-not $primaryTarget) {
        foreach ($item in Get-ChildItem Env:) {
            if ($item.Name -match '^(COMPOSE_|FIGMA_E2E_|M5_E2E_|KEYCLOAK_|KNORA_|DOCKER_|SESSION_SECRET$)' -and $item.Value.Trim()) {
                throw 'OTP_AMBIENT_OVERRIDE_REJECTED'
            }
        }
    }
    if ($Mode -eq 'Bind' -and -not $EnableIsolatedOtp -and -not $EnablePrimaryOtp) { throw 'OTP_BIND_OPT_IN_REQUIRED' }
    if ($ConfigurePrimarySmtp -and -not $primaryTarget) { throw 'OTP_PRIMARY_SMTP_OPT_IN_REQUIRED' }
    if ($primaryTarget -and $EnableIsolatedOtp) { throw 'OTP_TARGET_MODE_CONFLICT' }
    $smtpContract = Get-PrimarySmtpContract
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
    $smtpMetadata = Get-SmtpMetadata $current
    if ($TestPrimarySmtpRecipient) {
        if ($Mode -ne 'Inspect' -or $null -eq $smtpContract) {
            throw 'OTP_SMTP_TEST_CONTRACT_REQUIRED'
        }
        try {
            $recipient = [Net.Mail.MailAddress]::new($TestPrimarySmtpRecipient)
            $sender = [Net.Mail.MailAddress]::new([string]$smtpContract.from)
            $message = [Net.Mail.MailMessage]::new($sender, $recipient)
            $message.Subject = 'Knora synthetic SMTP connection check'
            $message.Body = 'Synthetic operator-owned delivery check. No user data.'
            $client = [Net.Mail.SmtpClient]::new([string]$smtpContract.host, [int]$smtpContract.port)
            $client.EnableSsl = $true
            $client.Credentials = [Net.NetworkCredential]::new(
                [string]$smtpContract.user, [string]$smtpContract.password)
            try { $client.Send($message) }
            finally { $message.Dispose(); $client.Dispose() }
        } catch { throw 'OTP_SMTP_CONNECTION_FAILED' }
        Write-Output 'OTP_SMTP_CONNECTION_VERIFIED'
        return
    }
    $desiredClient = $null
    if ($Mode -eq 'Bind') {
        $client = Get-OtpClient
        $clientId = $client.id
        $clientSettings = @{ baseUrl = $client.baseUrl; rootUrl = $client.rootUrl }
        $clientPort = if ($primaryTarget) { '3000' } else { '3300' }
        $desiredClient = @{ baseUrl = "http://127.0.0.1:$clientPort"; rootUrl = "http://127.0.0.1:$clientPort" }
    }
    $settings = @{
        resetCredentialsFlow = $current.resetCredentialsFlow
        emailTheme = $current.emailTheme
        resetPasswordAllowed = $current.resetPasswordAllowed
    }
    $desired = @{ resetCredentialsFlow = $alias; emailTheme = 'knora'; resetPasswordAllowed = $true }
    if ($null -ne $smtpContract -and $Mode -eq 'Bind') {
        $desired.smtpServer = $smtpContract
    }
    if ($Mode -ne 'Restore') {
        $installed = @(Invoke-OtpAdmin -Uri "$realmUri/authentication/authenticator-providers")
        foreach ($provider in $providers) {
            if (@($installed | Where-Object { $_.id -eq $provider }).Count -ne 1) { throw 'OTP_AUTHENTICATOR_REQUIRED' }
        }
        $actions = @(Invoke-OtpAdmin -Uri "$realmUri/authentication/required-actions")
        if (@($actions | Where-Object { $_.alias -eq 'UPDATE_PASSWORD' -and
            $_.providerId -eq 'UPDATE_PASSWORD' -and $_.enabled -eq $true }).Count -ne 1) {
            throw 'OTP_NATIVE_UPDATE_PASSWORD_REQUIRED'
        }
        $flows = @(Invoke-OtpAdmin -Uri "$realmUri/authentication/flows" | Where-Object { $_.alias -eq $alias })
        if ($flows.Count -gt 1) { throw 'OTP_FLOW_CONFLICT' }
        $executions = @()
        if ($flows.Count -eq 1) {
            $executions = @(Invoke-OtpAdmin -Uri "$realmUri/authentication/flows/$alias/executions")
            Assert-OtpFlow $flows[0] $executions
        }
        if ($Mode -in 'Inspect', 'Diff') {
            # Only approved settings and execution metadata leave the process.
            $inspection = @{ target = "$BaseUrl/realms/$Realm"; realmId = $realmId; project = $Project
                flowPresent = ($flows.Count -eq 1); settings = $settings; desired = $desired }
            if ($primaryTarget) { $inspection.smtp = $smtpMetadata }
            $inspection | ConvertTo-Json -Depth 10
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
            $flows = @(Invoke-OtpAdmin -Uri "$realmUri/authentication/flows" | Where-Object { $_.alias -eq $alias })
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
        $smtpAlreadySet = $true
        if ($null -ne $smtpContract) {
            $smtpAlreadySet = ((Get-SmtpMetadata $current | ConvertTo-Json -Compress) -ceq
                (Get-SmtpMetadata @{ smtpServer = $smtpContract } | ConvertTo-Json -Compress))
        }
        if ($current.resetCredentialsFlow -eq $alias -and $current.emailTheme -eq 'knora' -and
            $current.resetPasswordAllowed -eq $true -and
            $client.baseUrl -ceq $desiredClient.baseUrl -and $client.rootUrl -ceq $desiredClient.rootUrl -and
            $smtpAlreadySet) {
            Write-Output 'OTP_BIND_ALREADY_SET'; return
        }
        if ($null -ne $smtpContract -and $smtpMetadata.passwordConfigured -and
            [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('KC_SMTP_RESTORE_PASSWORD'))) {
            throw 'OTP_SMTP_RESTORE_SECRET_REQUIRED'
        }
        if ($current.resetCredentialsFlow -eq $alias -and $null -eq $smtpContract) {
            throw 'OTP_BOUND_SETTINGS_CONFLICT'
        }
        if (-not $SnapshotPath) {
            $folderName = if ($primaryTarget) {
                '.superpowers/sdd/2026-10-10-main-runtime-email-otp-gmail-smtp/snapshots'
            } else { '.superpowers/sdd/2026-10-08-figma-otp-native-runtime/snapshots' }
            $folder = Join-Path $repositoryRoot $folderName
            $null = New-Item -ItemType Directory -Force -Path $folder
            $SnapshotPath = Join-Path $folder "binding-$([DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fffffff')).json"
        }
        $saved = @{ baseUrl = $BaseUrl; realm = $Realm; realmId = $realmId; project = $Project
            workingDirectory = $repositoryRoot; settings = $settings; clientId = $clientId; clientSettings = $clientSettings }
        if ($primaryTarget) { $saved.smtp = $smtpMetadata }
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
        if ($primaryTarget) {
            if (-not ($saved.PSObject.Properties.Name -contains 'smtp') -or
                (@($saved.smtp.PSObject.Properties.Name | Sort-Object) -join ',') -ne
                'auth,configured,from,host,passwordConfigured,port,starttls,user' -or
                $saved.smtp.passwordConfigured -isnot [bool] -or $saved.smtp.configured -isnot [bool]) {
                throw 'OTP_SNAPSHOT_TARGET_REJECTED'
            }
        }
        $hasClientId = $saved.PSObject.Properties.Name -contains 'clientId'
        $hasClientSettings = $saved.PSObject.Properties.Name -contains 'clientSettings'
        if ($hasClientId -ne $hasClientSettings) { throw 'OTP_SNAPSHOT_TARGET_REJECTED' }
        if ($hasClientId) {
            $client = Get-OtpClient
            if ($saved.clientId -cne $client.id -or
                (@($saved.clientSettings.PSObject.Properties.Name | Sort-Object) -join ',') -ne 'baseUrl,rootUrl') {
                throw 'OTP_SNAPSHOT_TARGET_REJECTED'
            }
            foreach ($name in 'baseUrl', 'rootUrl') {
                if ($null -ne $saved.clientSettings.$name -and $saved.clientSettings.$name -isnot [string]) {
                    throw 'OTP_SNAPSHOT_TARGET_REJECTED'
                }
            }
            $clientId = $client.id
            $desiredClient = @{ baseUrl = $saved.clientSettings.baseUrl; rootUrl = $saved.clientSettings.rootUrl }
        }
        $desired = @{
            resetCredentialsFlow = $saved.settings.resetCredentialsFlow
            emailTheme = if ($null -eq $saved.settings.emailTheme) { '' } else { $saved.settings.emailTheme }
            resetPasswordAllowed = $saved.settings.resetPasswordAllowed
        }
        if ($primaryTarget -and $saved.PSObject.Properties.Name -contains 'smtp') {
            if ($saved.smtp.configured) {
                $desired.smtpServer = Convert-SmtpRestoreValue $saved.smtp
            } else {
                # Keycloak 26.3.3 ignores null here; an empty map clears SMTP configuration.
                $desired.smtpServer = @{}
            }
        }
    }
    try {
        $beforeWrite = Invoke-OtpAdmin -Uri $realmUri
        if ($beforeWrite.id -ne $realmId) { throw 'id' }
        Assert-OtpOwnership -RequireNativeRuntime:($Mode -eq 'Bind' -and -not $primaryTarget)
        if ($Mode -eq 'Bind') {
            Set-OtpClientOrigins $clientId $desiredClient
            $beforeWrite = Invoke-OtpAdmin -Uri $realmUri
            if ($beforeWrite.id -ne $realmId -or $beforeWrite.resetCredentialsFlow -ne $settings.resetCredentialsFlow) { throw 'id' }
            if (-not $primaryTarget) { Assert-OtpOwnership -RequireNativeRuntime }
        }
        $null = Invoke-OtpAdmin -Method Put -Uri $realmUri -Payload $desired
        $verified = Invoke-OtpAdmin -Uri $realmUri
        if ($verified.id -ne $realmId) { throw 'id' }
        foreach ($name in $desired.Keys) {
            if ($name -eq 'smtpServer' -and $primaryTarget) {
                $actualSmtp = Get-SmtpMetadata $verified
                $expectedSmtp = Get-SmtpMetadata @{ smtpServer = $desired[$name] }
                if (($actualSmtp | ConvertTo-Json -Compress) -cne
                    ($expectedSmtp | ConvertTo-Json -Compress)) { throw 'setting' }
                continue
            }
            if ($verified.$name -ne $desired[$name] -and -not
                ($name -eq 'emailTheme' -and -not $verified.$name -and -not $desired[$name])) { throw 'setting' }
        }
        if ($Mode -eq 'Restore' -and $null -ne $desiredClient) {
            Set-OtpClientOrigins $clientId $desiredClient
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
