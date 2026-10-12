[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$SubjectSha,
    [Parameter(Mandatory)][ValidateSet('application', 'otp')][string]$Profile,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$WorkflowSha,
    [string]$RunId = $env:GITHUB_RUN_ID,
    [string]$RunAttempt = $env:GITHUB_RUN_ATTEMPT,
    [string]$OutputDir = (Join-Path (Split-Path $PSScriptRoot -Parent) '.verification/runtime'),
    [string]$VaultPath,
    [string]$AdminUsername = 'figma-test-admin',
    [string]$AdminPassword = 'figma-test-admin-password'
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$actualSha = (& git -C $repositoryRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualSha -cne $SubjectSha) {
    throw 'RUNTIME_SUBJECT_SHA_MISMATCH'
}
if (-not $RunId) { throw 'RUNTIME_RUN_ID_REQUIRED' }
if (-not $RunAttempt) { $RunAttempt = '1' }
$startedAt = [DateTime]::UtcNow.ToString('o')
$profileDir = Join-Path $OutputDir $Profile
if (Test-Path -LiteralPath $profileDir) { throw 'RUNTIME_OUTPUT_MUST_BE_FRESH' }
$existing = @(& docker ps -a --filter 'label=com.docker.compose.project=knora-figma-e2e' --format '{{.ID}}')
if ($LASTEXITCODE -ne 0 -or $existing.Count -gt 0) { throw 'RUNTIME_PROJECT_MUST_BE_FRESH' }
foreach ($resource in 'volume', 'network') {
    $existing = @(& docker $resource ls --filter 'name=knora-figma-e2e' --format '{{.Name}}')
    if ($LASTEXITCODE -ne 0 -or $existing.Count -gt 0) { throw 'RUNTIME_PROJECT_MUST_BE_FRESH' }
}
$null = New-Item -ItemType Directory -Path $profileDir
$snapshots = @()
$images = @{}
$ownedVault = $null
$compose = @('--project-name', 'knora-figma-e2e', '--project-directory', $repositoryRoot,
    '-f', (Join-Path $repositoryRoot 'docker-compose.dev.yml'), '--profile', 'figma',
    '--profile', 'otp-proof')

function Invoke-Checked {
    param([string]$File, [string[]]$Arguments)
    & $File @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "RUNTIME_COMMAND_FAILED: $File" }
}

function Invoke-Checked-Named {
    param([string]$File, [hashtable]$Arguments)
    & $File @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "RUNTIME_COMMAND_FAILED: $File" }
}

function Add-ImageIdentity {
    param([string]$Service)
    $id = (& docker compose @compose ps -q $Service).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $id) { throw "RUNTIME_IMAGE_MISSING: $Service" }
    $identity = (& docker inspect --format '{{.Image}}' $id).Trim()
    if ($LASTEXITCODE -ne 0 -or $identity -notmatch '^sha256:[0-9a-f]{64}$') {
        throw "RUNTIME_IMAGE_ID_INVALID: $Service"
    }
    $images[$Service] = $identity
}

function Invoke-Playwright {
    param([string]$Name, [string]$Config, [string]$Spec, [string]$Match, [string]$Mode)
    $report = Join-Path $profileDir "$Name.xml"
    $env:FIGMA_TEST_MODE = $Mode
    $env:PLAYWRIGHT_JUNIT_OUTPUT_NAME = $report
    Push-Location (Join-Path $repositoryRoot 'frontend')
    try {
        $args = @('test', $Spec, "--config=$Config", '--reporter=list,junit')
        if ($Match) { $args += "--grep=$Match" }
        Invoke-Checked 'node' (@((Join-Path (Get-Location) 'node_modules/@playwright/test/cli.js')) + $args)
    } finally { Pop-Location }
    if (-not (Test-Path -LiteralPath $report -PathType Leaf)) { throw "RUNTIME_REPORT_MISSING: $Name" }
    return $report
}

function Invoke-Evidence {
    param([hashtable]$Reports)
    $arguments = @('create', '--subject-sha', $SubjectSha, '--actual-sha', $actualSha,
        '--workflow-sha', $WorkflowSha, '--run-id', $RunId, '--run-attempt', $RunAttempt,
        '--profile', $Profile, '--output-dir', $profileDir, '--started-at', $startedAt)
    foreach ($entry in $Reports.GetEnumerator()) { $arguments += @('--report', "$($entry.Key)=$($entry.Value)") }
    $arguments += @('--tool', "powershell=$($PSVersionTable.PSVersion)", '--tool', "node=$((& node --version).Trim())",
        '--tool', "python=$((& python --version).Trim())", '--tool', "maven=$((& mvn --version | Select-Object -First 1).Trim())")
    foreach ($entry in $images.GetEnumerator()) { $arguments += @('--image', "$($entry.Key)=$($entry.Value)") }
    Invoke-Checked 'python' (@((Join-Path $repositoryRoot 'scripts/runtime_evidence.py')) + $arguments)
    $evidence = Join-Path $profileDir 'evidence.json'
    if (-not (Test-Path -LiteralPath $evidence -PathType Leaf)) { throw 'RUNTIME_EVIDENCE_MISSING' }
    return $evidence
}

try {
    # Stream diagnostics and retain rollback ownership even if preparation throws.
    & (Join-Path $PSScriptRoot 'prepare-figma-e2e.ps1') 2>&1 | ForEach-Object {
        if ([string]$_ -like 'KEYCLOAK_ROLLBACK_SNAPSHOT=*') {
            $snapshots += ([string]$_).Substring(27)
        }
        $_ | Out-Host
    }
    if ($LASTEXITCODE -ne 0) { throw 'RUNTIME_APPLICATION_PREPARE_FAILED' }
    foreach ($service in 'figma-postgres', 'figma-keycloak', 'figma-api') {
        Add-ImageIdentity $service
    }
    if ($Profile -eq 'application') {
        $reports = @{}
        $reports.identity = Invoke-Playwright 'identity' 'playwright.figma.config.ts' 'figma-identity.spec.ts' $null $null
        $reports.documents = Invoke-Playwright 'documents' 'playwright.figma.config.ts' 'figma-document-navigation.spec.ts' $null 'application'
        $reports.conversations = Invoke-Playwright 'conversations' 'playwright.figma.config.ts' 'figma-ui-interactions.spec.ts' 'owned Workspace restores from the Conversation bottom bar' 'application'
        $reports.operator = Invoke-Playwright 'operator' 'playwright.figma-operator.config.ts' 'figma-operator.spec.ts' $null 'application'
        $reports.workspace = Invoke-Playwright 'workspace' 'playwright.figma.config.ts' 'figma-ui-interactions.spec.ts' 'live account logout|owned document and workspace lifecycle' 'application'
    } else {
        if (-not $VaultPath) { $VaultPath = Join-Path ([IO.Path]::GetTempPath()) "knora-runtime-vault-$([guid]::NewGuid().ToString('N'))" }
        if (Test-Path -LiteralPath $VaultPath) { throw 'OTP_VAULT_MUST_BE_FRESH' }
        $null = New-Item -ItemType Directory -Path $VaultPath
        $ownedVault = (Get-Item -LiteralPath $VaultPath).FullName
        $token = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8380/realms/master/protocol/openid-connect/token' `
            -ContentType 'application/x-www-form-urlencoded' -Body @{
                client_id = 'admin-cli'; grant_type = 'password'; username = $AdminUsername; password = $AdminPassword
            }
        $realm = Invoke-RestMethod -Uri 'http://127.0.0.1:8380/admin/realms/knora-dev' -Headers @{ Authorization = "Bearer $($token.access_token)" }
        $digest = [BitConverter]::ToString(([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($realm.id)))).Replace('-', '').ToLowerInvariant()
        $vaultEntry = Join-Path $VaultPath "knora-dev_knora-email-otp-hmac-$digest"
        $bytes = New-Object byte[] 32
        [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
        [IO.File]::WriteAllText($vaultEntry, [Convert]::ToBase64String($bytes))
        [Array]::Clear($bytes, 0, $bytes.Length)
        if (-not $IsWindows) {
            Invoke-Checked 'chmod' @('700', '--', $VaultPath)
            Invoke-Checked 'chmod' @('600', '--', $vaultEntry)
            Invoke-Checked 'sudo' @('chown', '1000:0', '--', $VaultPath, $vaultEntry)
        }
        $runtimePreparation = @('-VaultPath', $VaultPath,
            '-AdminUsername', $AdminUsername, '-AdminPassword', $AdminPassword)
        if ($IsWindows) {
            Invoke-Checked (Join-Path $PSScriptRoot 'prepare-figma-otp-runtime.ps1') $runtimePreparation
        } else {
            # The vault is intentionally owned by Keycloak UID 1000; only this guarded read runs as root.
            Invoke-Checked 'sudo' (@('pwsh', '-NoProfile', '-File', (Join-Path $PSScriptRoot 'prepare-figma-otp-runtime.ps1')) + $runtimePreparation)
        }
        $otpSnapshot = Join-Path $profileDir 'otp-binding.json'
        Invoke-Checked-Named (Join-Path $PSScriptRoot 'configure-keycloak-email-otp.ps1') @{
            Mode = 'Bind'
            EnableIsolatedOtp = $true
            AdminUsername = $AdminUsername
            AdminPassword = $AdminPassword
            SnapshotPath = $otpSnapshot
        }
        $reports = @{}
        $reports.native = Invoke-Playwright 'native' 'playwright.figma-otp.config.ts' 'figma-otp-native.spec.ts' $null 'application'
        Add-ImageIdentity 'figma-keycloak'
        Invoke-Checked 'docker' @('compose', '--project-name', 'knora-figma-e2e', '--project-directory', $repositoryRoot,
            '-f', (Join-Path $repositoryRoot 'docker-compose.dev.yml'), '--profile', 'figma', 'stop', 'figma-keycloak')
        Push-Location (Join-Path $repositoryRoot 'infra/keycloak/providers/email-otp-reset')
        try { Invoke-Checked 'mvn' @('-B', '-Pstorage-proof', '-DskipTests', 'package') }
        finally { Pop-Location }
        & (Join-Path $PSScriptRoot 'prepare-figma-otp-proof.ps1') -WithProof {
            Push-Location (Join-Path $repositoryRoot 'infra/keycloak/providers/email-otp-reset')
            try {
                Invoke-Checked 'mvn' @('-B', '-Pstorage-proof', '-DproofDockerNetwork=false',
                    '-Dit.test=OtpChallengeConcurrencyIT#probeRejectsMissingHeaderBeforeStorage+probeRejectsAnotherRealmAndNonProofKey+independentJpaCommitRestoresOuterJtaAndSessionOnBothNodes+relationalAccountBudgetDoesNotResetAcrossSessionsOrCallerRollback+relationalParallelConsumeAndRotationNeverReviveConsumedOrOldGeneration+relationalHeldFirstRowRollbackFailsClosedThenAdmitsExactlyOnce+relationalCooldownSendCapAndFixedWindowSurviveNewSessionAndResend+relationalExpiryAndLateDeliveryFailureNeverReviveConsumedOrRotatedGeneration', 'verify')
            } finally { Pop-Location }
        }
        foreach ($service in 'figma-keycloak-proof-main', 'figma-keycloak-proof') {
            Add-ImageIdentity $service
        }
        $reports.storage = Join-Path $repositoryRoot 'infra/keycloak/providers/email-otp-reset/target/failsafe-reports/TEST-com.knora.keycloak.reset.OtpChallengeConcurrencyIT.xml'
        if (-not (Test-Path -LiteralPath $reports.storage -PathType Leaf)) { throw 'RUNTIME_STORAGE_REPORT_MISSING' }
    }
} finally {
    $cleanupFailed = $false
    if ($Profile -eq 'otp' -and (Test-Path -LiteralPath (Join-Path $profileDir 'otp-binding.json'))) {
        try {
            Invoke-Checked 'docker' (@('compose') + $compose + @('stop', 'figma-keycloak-proof-main', 'figma-keycloak-proof'))
            $env:KNORA_FIGMA_OTP_VAULT_PATH = $VaultPath
            $env:KNORA_FIGMA_KEYCLOAK_COMMAND = 'start-dev --vault=file --vault-dir=/opt/keycloak/vault --spi-theme--cache-themes=false --spi-theme--cache-templates=false --spi-theme--static-max-age=-1'
            try {
                Invoke-Checked 'docker' (@('compose') + $compose + @('up', '-d', '--no-deps', 'figma-keycloak'))
            } finally {
                Remove-Item Env:KNORA_FIGMA_OTP_VAULT_PATH -ErrorAction SilentlyContinue
                Remove-Item Env:KNORA_FIGMA_KEYCLOAK_COMMAND -ErrorAction SilentlyContinue
            }
            if ($IsWindows) {
                Invoke-Checked (Join-Path $PSScriptRoot 'prepare-figma-otp-runtime.ps1') $runtimePreparation
            } else {
                Invoke-Checked 'sudo' (@('pwsh', '-NoProfile', '-File', (Join-Path $PSScriptRoot 'prepare-figma-otp-runtime.ps1')) + $runtimePreparation)
            }
            & (Join-Path $PSScriptRoot 'configure-keycloak-email-otp.ps1') -Mode Restore -EnableIsolatedOtp -AdminUsername $AdminUsername -AdminPassword $AdminPassword -SnapshotPath (Join-Path $profileDir 'otp-binding.json') | Out-Null
        } catch { $cleanupFailed = $true }
    }
    foreach ($snapshot in $snapshots) {
        try {
            & (Join-Path $PSScriptRoot 'configure-keycloak-auth-flow.ps1') -Mode Rollback -BaseUrl 'http://127.0.0.1:8380' -Project 'knora-figma-e2e' -AdminUsername 'figma-test-admin' -AdminPassword 'figma-test-admin-password' -SnapshotPath $snapshot | Out-Null
        } catch { $cleanupFailed = $true }
    }
    try { Invoke-Checked 'docker' (@('compose') + $compose + @('down', '--volumes', '--remove-orphans')) }
    catch { $cleanupFailed = $true }
    if ($ownedVault) {
        try {
            if ($IsWindows) { Remove-Item -LiteralPath $ownedVault -Recurse -Force }
            else {
                $runnerOwner = "$((& id -u).Trim()):$((& id -g).Trim())"
                Invoke-Checked 'sudo' @('chown', $runnerOwner, '--', $ownedVault)
                Remove-Item -LiteralPath $ownedVault -Recurse -Force -ErrorAction Stop
            }
        } catch { $cleanupFailed = $true }
    }
    Remove-Item Env:FIGMA_TEST_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:PLAYWRIGHT_JUNIT_OUTPUT_NAME -ErrorAction SilentlyContinue
    Remove-Item Env:KNORA_STORAGE_PROOF_SECRET -ErrorAction SilentlyContinue
    if ($cleanupFailed) { throw 'RUNTIME_CLEANUP_FAILED' }
}
Invoke-Evidence $reports | Out-Null
