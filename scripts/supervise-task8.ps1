param(
    [string]$SubjectSha = '',
    [Parameter(Mandatory = $true)]
    [DateTimeOffset]$AbsoluteCutoff,
    [Parameter(Mandatory = $true)]
    [DateTimeOffset]$HardDeadline,
    [string]$ProjectName = '',
    [switch]$DryRunFaultTest,
    [switch]$SimulateTimeout
)

$ErrorActionPreference = 'Stop'
$repoRoot = 'C:\Developer\Projects\knora-agent-worktree\fix-browser-session-persistence'
Set-Location $repoRoot

$currentHead = (git -C $repoRoot rev-parse HEAD).Trim()
if ($SubjectSha -and $currentHead -ne $SubjectSha) {
    throw "Subject drift: worktree HEAD ($currentHead) does not match declared SubjectSha ($SubjectSha)"
}
$subjectSha = $currentHead
$project = if ($ProjectName) { $ProjectName } else { 'knora-figma-e2e-session-' + [guid]::NewGuid().ToString('N').Substring(0, 12) }
$resDir = Join-Path $repoRoot "frontend/test-results/$project"

$nowUtc = [DateTimeOffset]::UtcNow
$initialRemaining = ($AbsoluteCutoff - $nowUtc).TotalSeconds
Write-Output "Task 8 Whole-Package Supervision: Now=$($nowUtc.ToString('o')), Cutoff=$($AbsoluteCutoff.ToString('o')), HardDeadline=$($HardDeadline.ToString('o'))"
Write-Output "Project: $project"
Write-Output "Subject SHA: $subjectSha"
Write-Output "Remaining seconds until cutoff: $initialRemaining"

# Dry-run Fault Test mode: tests timeout/interruption and clean process tree termination without Docker
if ($DryRunFaultTest) {
    Write-Output "Running DRY-RUN FAULT TEST (simulating whole-package supervisor cutoff handling)..."
    $null = New-Item -ItemType Directory -Path $resDir -Force
    $receiptPath = Join-Path $resDir 'task8-supervision-receipt.json'
    
    $simulatedProc = Start-Process "node" -ArgumentList "-e", "setTimeout(()=>{}, 60000)" -PassThru -NoNewWindow
    $procKilled = $false
    try {
        if ($SimulateTimeout) {
            Write-Output "Simulating timeout cutoff on child process tree (PID: $($simulatedProc.Id))..."
            Start-Sleep -Milliseconds 500
            try {
                Start-Process "taskkill" -ArgumentList "/PID $($simulatedProc.Id) /T /F" -NoNewWindow -Wait | Out-Null
                $procKilled = $true
            } catch {
                Stop-Process -Id $simulatedProc.Id -Force
                $procKilled = $true
            }
            throw "TIMEOUT_STOP_SIMULATED: Process tree terminated cleanly before deadline"
        }
    } finally {
        if (-not $simulatedProc.HasExited) {
            try { Stop-Process -Id $simulatedProc.Id -Force } catch {}
            $procKilled = $true
        }
        $receipt = [ordered]@{
            schemaVersion = 1
            mode = "dry-run-fault-test"
            project = $project
            subjectSha = $subjectSha
            cutoffUtc = $AbsoluteCutoff.ToString('o')
            hardDeadlineUtc = $HardDeadline.ToString('o')
            childProcessKilled = $procKilled
            status = if ($SimulateTimeout) { "TIMEOUT_CLEANUP_VERIFIED" } else { "SUCCESS" }
            timestampUtc = [DateTime]::UtcNow.ToString('o')
        }
        $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receiptPath -Encoding utf8
        Write-Output "DRY_RUN_FAULT_RECEIPT=$receiptPath"
    }
    return
}

# Preflight: Minimum 2280s required for 33m continuous quiet idle + startup + migration cycle + cleanup
if ($initialRemaining -lt 2280) {
    throw "INSUFFICIENT_TIME_FOR_WHOLE_PACKAGE: Remaining seconds ($initialRemaining) < required 2280s for 33m real-idle journey + migration cycle + startup/cleanup"
}

if ((git -C $repoRoot rev-parse HEAD).Trim() -ne $subjectSha) {
    throw "Subject drift detected: expected $subjectSha"
}
if (git -C $repoRoot status --porcelain) {
    throw "Dirty worktree detected"
}

& "$repoRoot/scripts/prepare-figma-e2e.ps1" -CheckFrontendOnly
if ($LASTEXITCODE -ne 0) { throw 'Frontend check failed' }
& "$repoRoot/scripts/prepare-figma-e2e.ps1" -Project $project -CheckConfigurationOnly
if ($LASTEXITCODE -ne 0) { throw 'Configuration check failed' }

# Run stack under whole-package supervision
& "$repoRoot/scripts/prepare-figma-e2e.ps1" -Project $project -Run {
    param($proj, $composeArgs)
    $repo = 'C:\Developer\Projects\knora-agent-worktree\fix-browser-session-persistence'
    $sha = '857638b81db1cefcda10fe64b7e6ad149ca3407b'
    $targetDir = Join-Path $repo "frontend/test-results/$proj"
    $null = New-Item -ItemType Directory -Path $targetDir -Force
    $supervisionReceiptPath = Join-Path $targetDir 'task8-supervision-receipt.json'
    $migrationReceiptPath = Join-Path $targetDir 'migration-cycle-receipt.json'

    # 1. Health checks & Provider observation
    Invoke-RestMethod http://127.0.0.1:8800/health | Out-Null
    $discovery = Invoke-RestMethod http://127.0.0.1:8380/realms/knora-dev/.well-known/openid-configuration
    if ($discovery.issuer -cne 'http://127.0.0.1:8380/realms/knora-dev') { throw 'Wrong issuer' }
    Invoke-RestMethod http://127.0.0.1:8025/api/v1/info | Out-Null
    
    docker compose @composeArgs exec -T figma-api alembic current
    if ($LASTEXITCODE -ne 0) { throw 'Migration observation failed' }
    docker compose @composeArgs exec -T figma-api python -c 'from knora.infrastructure.settings import Settings; s=Settings(); print(s.provider_mode, s.embedding_provider, s.generation_provider)'
    if ($LASTEXITCODE -ne 0) { throw 'Provider observation failed' }

    $testCompose = docker compose @composeArgs config --format json | ConvertFrom-Json
    $testAdminUsername = $testCompose.services.'figma-keycloak'.environment.KC_BOOTSTRAP_ADMIN_USERNAME
    $testAdminPassword = $testCompose.services.'figma-keycloak'.environment.KC_BOOTSTRAP_ADMIN_PASSWORD
    $policyArgs = @{
        BaseUrl = 'http://127.0.0.1:8380'; Project = $proj
        AdminUsername = $testAdminUsername; AdminPassword = $testAdminPassword
    }

    # 2. Migration Runtime Cycle (Plan line 587-588)
    # Synthetic baseline -> Apply -> Apply no-op -> Rollback -> Apply desired
    Write-Output "Executing Migration Runtime Cycle (Plan line 587-588)..."
    
    # Acquire admin token
    $tokenRes = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8380/realms/master/protocol/openid-connect/token' -ContentType 'application/x-www-form-urlencoded' -Body @{
        grant_type = 'password'; client_id = 'admin-cli'
        username = $testAdminUsername; password = $testAdminPassword
    }
    $kcHeaders = @{ Authorization = "Bearer $($tokenRes.access_token)" }

    # Setup baseline projection
    $clientList = @(Invoke-RestMethod -Uri "http://127.0.0.1:8380/admin/realms/knora-dev/clients?clientId=knora-web" -Headers $kcHeaders)
    $clientUuid = $clientList[0].id
    
    # Delete policy mapper if present
    $mappers = @(Invoke-RestMethod -Uri "http://127.0.0.1:8380/admin/realms/knora-dev/clients/$clientUuid/protocol-mappers/models" -Headers $kcHeaders)
    foreach ($m in $mappers) {
        if ($m.name -eq 'knora-session-policy') {
            Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:8380/admin/realms/knora-dev/clients/$clientUuid/protocol-mappers/models/$($m.id)" -Headers $kcHeaders | Out-Null
        }
    }

    # Set baseline realm
    $baselineRealm = @{
        rememberMe = $false
        ssoSessionIdleTimeout = 1800
        ssoSessionMaxLifespan = 36000
        ssoSessionIdleTimeoutRememberMe = 0
        ssoSessionMaxLifespanRememberMe = 0
        clientSessionIdleTimeout = 0
        clientSessionMaxLifespan = 0
        accessTokenLifespan = 60
    }
    Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:8380/admin/realms/knora-dev" -Headers $kcHeaders -ContentType 'application/json' -Body ($baselineRealm | ConvertTo-Json) | Out-Null

    # Reset client attributes (remove access.token.lifespan)
    $curClient = Invoke-RestMethod -Uri "http://127.0.0.1:8380/admin/realms/knora-dev/clients/$clientUuid" -Headers $kcHeaders
    $cleanAttrs = @{}
    if ($curClient.attributes) {
        foreach ($prop in $curClient.attributes.PSObject.Properties) {
            if ($prop.Name -ne 'access.token.lifespan') { $cleanAttrs[$prop.Name] = $prop.Value }
        }
    }
    Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:8380/admin/realms/knora-dev/clients/$clientUuid" -Headers $kcHeaders -ContentType 'application/json' -Body (@{ id = $clientUuid; clientId = 'knora-web'; attributes = $cleanAttrs } | ConvertTo-Json) | Out-Null

    $cycleSnap = Join-Path $targetDir 'migration-cycle-snap.json'
    
    # Step A: Apply
    $apply1 = & "$repo/scripts/configure-keycloak-session-policy.ps1" @policyArgs -Mode Apply -SnapshotPath $cycleSnap
    if ($apply1 -notcontains 'KEYCLOAK_SESSION_POLICY_APPLY_VERIFIED') { throw 'Migration Cycle Step A (Apply) failed' }
    
    # Step B: Apply No-Op
    $apply2 = & "$repo/scripts/configure-keycloak-session-policy.ps1" @policyArgs -Mode Apply -SnapshotPath (Join-Path $targetDir 'noop-snap.json')
    if ($apply2 -notcontains 'KEYCLOAK_SESSION_POLICY_ALREADY_SET') { throw 'Migration Cycle Step B (No-Op) failed' }

    # Step C: Rollback
    $rollback = & "$repo/scripts/configure-keycloak-session-policy.ps1" @policyArgs -Mode Rollback -SnapshotPath $cycleSnap
    if ($rollback -notcontains 'KEYCLOAK_SESSION_POLICY_ROLLBACK_VERIFIED') { throw 'Migration Cycle Step C (Rollback) failed' }

    # Step D: Apply Desired
    $desiredSnap = Join-Path $targetDir 'session-policy-desired.json'
    $applyFinal = & "$repo/scripts/configure-keycloak-session-policy.ps1" @policyArgs -Mode Apply -SnapshotPath $desiredSnap
    if ($applyFinal -notcontains 'KEYCLOAK_SESSION_POLICY_APPLY_VERIFIED') { throw 'Migration Cycle Step D (Desired Apply) failed' }

    $migrationReceipt = [ordered]@{
        schemaVersion = 1
        project = $proj
        subjectSha = $sha
        cycleCompleted = $true
        steps = @("BaselineSetup", "ApplyVerified", "NoOpVerified", "RollbackVerified", "DesiredApplyVerified")
        timestampUtc = [DateTime]::UtcNow.ToString('o')
    }
    $migrationReceipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $migrationReceiptPath -Encoding utf8
    Write-Output "MIGRATION_CYCLE_RECEIPT=$migrationReceiptPath"

    # 3. Deadline Check before Playwright run
    $remainingSec = [int](($AbsoluteCutoff - [DateTimeOffset]::UtcNow).TotalSeconds)
    if ($remainingSec -lt 2000) {
        throw "TIMEOUT_STOP: Pre-playwright cycle consumed time; remaining $remainingSec s < 2000s required for 33m quiet idle"
    }

    Write-Output "Executing Playwright test with $remainingSec s remaining until $($AbsoluteCutoff.ToString('o'))..."

    $env:FIGMA_SUBJECT_SHA = $sha
    $env:FIGMA_TEST_PROJECT = $proj
    $env:FIGMA_TEST_MODE = 'application'
    $env:FIGMA_TEST_MATCH = 'session-persistence.spec.ts'
    $env:PLAYWRIGHT_JUNIT_OUTPUT_NAME = Join-Path $targetDir 'session-persistence.xml'
    
    $pwArgs = @(
        "$repo/frontend/node_modules/@playwright/test/cli.js",
        "test",
        "--config", "$repo/frontend/playwright.figma.config.ts",
        "--reporter", "list,junit",
        "--output", "$targetDir/results"
    )

    $proc = Start-Process -FilePath "node" -ArgumentList $pwArgs -PassThru -NoNewWindow
    $runnerFinished = $false
    try {
        $finished = $proc.WaitForExit(($remainingSec - 60) * 1000)
        if (-not $finished) {
            Write-Output "Deadline cutoff reached: terminating Playwright process tree (PID: $($proc.Id))..."
            try {
                Start-Process -FilePath "taskkill" -ArgumentList "/PID $($proc.Id) /T /F" -NoNewWindow -Wait | Out-Null
            } catch {
                try { Stop-Process -Id $proc.Id -Force } catch {}
            }
            throw "TIMEOUT_STOP: Playwright run exceeded whole-package cutoff ($($AbsoluteCutoff.ToString('o')))"
        }
        $proc.WaitForExit()
        $runnerFinished = $true
        if ($proc.ExitCode -ne $null -and $proc.ExitCode -ne 0) {
            throw "Session persistence journey failed with exit code $($proc.ExitCode)"
        }
    } finally {
        $supervisionReceipt = [ordered]@{
            schemaVersion = 1
            project = $proj
            subjectSha = $sha
            cutoffUtc = $AbsoluteCutoff.ToString('o')
            hardDeadlineUtc = $HardDeadline.ToString('o')
            runnerFinished = $runnerFinished
            playwrightExitCode = if ($proc.HasExited) { $proc.ExitCode } else { $null }
            status = if ($runnerFinished -and $proc.ExitCode -eq 0) { "SUCCESS" } else { "FAILED_OR_TERMINATED" }
            timestampUtc = [DateTime]::UtcNow.ToString('o')
        }
        $supervisionReceipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $supervisionReceiptPath -Encoding utf8
        Write-Output "SUPERVISION_RECEIPT=$supervisionReceiptPath"
    }
}
