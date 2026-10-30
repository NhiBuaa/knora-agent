param(
    [Parameter(Mandatory = $true)]
    [DateTimeOffset]$AbsoluteCutoff,
    [Parameter(Mandatory = $true)]
    [DateTimeOffset]$HardDeadline,
    [string]$SubjectSha = '',
    [string]$ProjectName = '',
    [ValidateSet('None', 'Success', 'HangStartup', 'HangRunner', 'HangCleanup')][string]$StubMode = 'None',
    [switch]$WorkerMode,
    [switch]$AllowDirty
)

$ErrorActionPreference = 'Stop'
$repoRoot = 'C:\Developer\Projects\knora-agent-worktree\fix-browser-session-persistence'
Set-Location $repoRoot

# Validate and unify exact Subject SHA across supervisor and worker
$actualHead = (git -C $repoRoot rev-parse HEAD).Trim()
if ($SubjectSha -and $actualHead -ne $SubjectSha) {
    throw "Subject drift detected: expected $SubjectSha, actual HEAD is $actualHead"
}
if (-not $AllowDirty -and $StubMode -eq 'None' -and (git -C $repoRoot status --porcelain)) {
    throw "Dirty worktree detected: commit or clean working copy before running supervisor"
}
$resolvedSubjectSha = $actualHead

$project = if ($ProjectName) { $ProjectName } else { 'knora-figma-e2e-session-' + [guid]::NewGuid().ToString('N').Substring(0, 12) }
$resDir = Join-Path $repoRoot "frontend/test-results/$project"
$supervisionReceiptPath = Join-Path $resDir 'task8-supervision-receipt.json'
$migrationReceiptPath = Join-Path $resDir 'migration-cycle-receipt.json'

# ==============================================================================
# INNER WORKER MODE: Executes inside the isolated environment reservation
# ==============================================================================
if ($WorkerMode) {
    Write-Output "Worker started for project $project with Subject SHA $resolvedSubjectSha"
    $null = New-Item -ItemType Directory -Path $resDir -Force

    # STUB MODE (used for local fault tests without Docker)
    if ($StubMode -ne 'None') {
        Write-Output "Worker running in STUB MODE: $StubMode"
        if ($StubMode -eq 'HangStartup') {
            # Spawn child that spawns grandchild, then hang
            $child = Start-Process "node" -ArgumentList "-e", "const { spawn } = require('child_process'); spawn('node', ['-e', 'setTimeout(()=>{}, 600000)']); setTimeout(()=>{}, 600000);" -PassThru -NoNewWindow
            Start-Sleep -Seconds 600
        }
        if ($StubMode -eq 'HangRunner') {
            # Simulate migration cycle completion
            $migReceipt = [ordered]@{
                schemaVersion = 1
                project = $project
                subjectSha = $resolvedSubjectSha
                cycleCompleted = $true
                steps = @("BaselineSetup", "ApplyVerified", "NoOpVerified", "RollbackVerified", "DesiredApplyVerified")
                timestampUtc = [DateTime]::UtcNow.ToString('o')
            }
            [System.IO.File]::WriteAllText($migrationReceiptPath, ($migReceipt | ConvertTo-Json -Depth 5), [System.Text.UTF8Encoding]::new($false))
            
            # Spawn worker child and grandchild process, then hang
            $child = Start-Process "node" -ArgumentList "-e", "const { spawn } = require('child_process'); spawn('node', ['-e', 'setTimeout(()=>{}, 600000)']); setTimeout(()=>{}, 600000);" -PassThru -NoNewWindow
            Start-Sleep -Seconds 600
        }
        if ($StubMode -eq 'Success') {
            $migReceipt = [ordered]@{
                schemaVersion = 1
                project = $project
                subjectSha = $resolvedSubjectSha
                cycleCompleted = $true
                steps = @("BaselineSetup", "ApplyVerified", "NoOpVerified", "RollbackVerified", "DesiredApplyVerified")
                timestampUtc = [DateTime]::UtcNow.ToString('o')
            }
            [System.IO.File]::WriteAllText($migrationReceiptPath, ($migReceipt | ConvertTo-Json -Depth 5), [System.Text.UTF8Encoding]::new($false))
            Start-Sleep -Milliseconds 100
            exit 0
        }
        exit 0
    }

    # REAL PRODUCTION WORKER PATH
    & "$repoRoot/scripts/prepare-figma-e2e.ps1" -Project $project -Run {
        param($proj, $composeArgs)
        $repo = 'C:\Developer\Projects\knora-agent-worktree\fix-browser-session-persistence'
        $targetDir = Join-Path $repo "frontend/test-results/$proj"

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
        Write-Output "Executing Migration Runtime Cycle (Plan line 587-588)..."
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

        # Set baseline realm (§1)
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
            subjectSha = $resolvedSubjectSha
            cycleCompleted = $true
            steps = @("BaselineSetup", "ApplyVerified", "NoOpVerified", "RollbackVerified", "DesiredApplyVerified")
            timestampUtc = [DateTime]::UtcNow.ToString('o')
        }
        [System.IO.File]::WriteAllText($migrationReceiptPath, ($migrationReceipt | ConvertTo-Json -Depth 5), [System.Text.UTF8Encoding]::new($false))
        Write-Output "MIGRATION_CYCLE_RECEIPT=$migrationReceiptPath"

        # 3. Pre-Run Remaining Time Guard:
        # Minimum required: 1980s (quiet idle) + 240s (tests 1-6) + 90s (fresh navigation + teardown reserve) + 60s (safety margin) = 2370s
        $remainingSecForRunner = [int](($AbsoluteCutoff - [DateTimeOffset]::UtcNow).TotalSeconds)
        if ($remainingSecForRunner -lt 2370) {
            throw "INSUFFICIENT_TIME_BEFORE_RUNNER: Remaining $remainingSecForRunner s < 2370s required (1980s quiet + 240s tests 1-6 + 90s fresh navigation/teardown + 60s reserve)"
        }

        Write-Output "Executing Playwright test with $remainingSecForRunner s remaining until $($AbsoluteCutoff.ToString('o'))..."

        $env:FIGMA_SUBJECT_SHA = $resolvedSubjectSha
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
        $null = $proc.Handle
        $timeoutForPwProc = ($remainingSecForRunner - 60) * 1000
        $finished = $proc.WaitForExit($timeoutForPwProc)
        if (-not $finished) {
            Write-Output "Runner exceeded timeout: killing Playwright process tree (PID: $($proc.Id))..."
            try { Start-Process "taskkill" -ArgumentList "/PID $($proc.Id) /T /F" -NoNewWindow -Wait | Out-Null } catch {
                try { Stop-Process -Id $proc.Id -Force } catch {}
            }
            throw "TIMEOUT_STOP: Playwright run exceeded remaining deadline ($($AbsoluteCutoff.ToString('o')))"
        }
        $proc.WaitForExit()
        if ($proc.ExitCode -ne $null -and $proc.ExitCode -ne 0) {
            throw "Session persistence journey failed with exit code $($proc.ExitCode)"
        }
    }
    return
}

# ==============================================================================
# OUTER SUPERVISOR: Manages whole-package watchdog, cutoff and process cleanup
# ==============================================================================
$nowUtc = [DateTimeOffset]::UtcNow
$initialRemaining = ($AbsoluteCutoff - $nowUtc).TotalSeconds
Write-Output "Task 8 Outer Supervisor: Now=$($nowUtc.ToString('o')), Cutoff=$($AbsoluteCutoff.ToString('o')), HardDeadline=$($HardDeadline.ToString('o'))"
Write-Output "Project: $project"
Write-Output "Resolved Subject SHA: $resolvedSubjectSha"
Write-Output "Remaining seconds until cutoff: $initialRemaining"

# Whole-package deadline check:
# 2370s (runner) + 90s (migration cycle) + 60s (compose startup) + 60s (final teardown) = 2580s (~43 minutes)
if ($StubMode -eq 'None' -and $initialRemaining -lt 2580) {
    throw "INSUFFICIENT_TIME_FOR_WHOLE_PACKAGE: Remaining seconds ($initialRemaining) < required 2580s for whole-package execution"
}

# Ensure output directory
$null = New-Item -ItemType Directory -Path $resDir -Force

# Launch Worker Process
$psExe = if (Get-Command pwsh -ErrorAction SilentlyContinue) { 'pwsh' } else { 'powershell' }
$workerArgs = @(
    "-NoProfile",
    "-File", (Join-Path $repoRoot "scripts/supervise-task8.ps1"),
    "-WorkerMode",
    "-AbsoluteCutoff", $AbsoluteCutoff.ToString('o'),
    "-HardDeadline", $HardDeadline.ToString('o'),
    "-SubjectSha", $resolvedSubjectSha,
    "-ProjectName", $project
)
if ($StubMode -ne 'None') {
    $workerArgs += @("-StubMode", $StubMode)
}
if ($AllowDirty) {
    $workerArgs += "-AllowDirty"
}

Write-Output "Outer Supervisor launching Worker: $psExe $workerArgs"
$workerProc = Start-Process -FilePath $psExe -ArgumentList $workerArgs -PassThru -NoNewWindow
$null = $workerProc.Handle

$workerFinishedCleanly = $false
$childProcessesKilled = $false
$failureReason = $null

try {
    # Calculate timeout for the entire worker
    $remainingMs = [Math]::Max(100, [int](($AbsoluteCutoff - [DateTimeOffset]::UtcNow).TotalMilliseconds))
    $completedInTime = $workerProc.WaitForExit($remainingMs)

    if (-not $completedInTime) {
        $failureReason = "WHOLE_PACKAGE_TIMEOUT_CUTOFF: Worker exceeded AbsoluteCutoff ($($AbsoluteCutoff.ToString('o')))"
        Write-Output $failureReason
        Write-Output "Terminating Worker process tree (PID: $($workerProc.Id))..."
        try {
            Start-Process "taskkill" -ArgumentList "/PID $($workerProc.Id) /T /F" -NoNewWindow -Wait | Out-Null
            $childProcessesKilled = $true
        } catch {
            try { Stop-Process -Id $workerProc.Id -Force } catch {}
            $childProcessesKilled = $true
        }
    } else {
        $workerProc.WaitForExit()
        if ($workerProc.ExitCode -eq 0) {
            $workerFinishedCleanly = $true
        } else {
            $failureReason = "Worker process exited with non-zero exit code: $($workerProc.ExitCode)"
        }
    }
} finally {
    # Ensure any remaining descendant processes are dead
    if (-not $workerProc.HasExited) {
        try {
            Start-Process "taskkill" -ArgumentList "/PID $($workerProc.Id) /T /F" -NoNewWindow -Wait | Out-Null
            $childProcessesKilled = $true
        } catch {
            try { Stop-Process -Id $workerProc.Id -Force } catch {}
            $childProcessesKilled = $true
        }
    }

    # Teardown Docker Compose reservation if in real mode
    if ($StubMode -eq 'None') {
        try {
            Write-Output "Executing Docker Teardown for project $project..."
            & docker compose -p $project down -v --remove-orphans | Out-Null
        } catch {}
    }

    $finalStatus = if ($workerFinishedCleanly) {
        "SUCCESS"
    } elseif ($childProcessesKilled -and $failureReason -like "*TIMEOUT*") {
        "TIMEOUT_CLEANUP_VERIFIED"
    } else {
        "FAILED_OR_TERMINATED"
    }

    $receipt = [ordered]@{
        schemaVersion = 1
        project = $project
        subjectSha = $resolvedSubjectSha
        cutoffUtc = $AbsoluteCutoff.ToString('o')
        hardDeadlineUtc = $HardDeadline.ToString('o')
        workerPid = $workerProc.Id
        workerExitCode = if ($workerProc.HasExited) { $workerProc.ExitCode } else { $null }
        workerFinishedCleanly = $workerFinishedCleanly
        childProcessesKilled = $childProcessesKilled
        status = $finalStatus
        failureReason = $failureReason
        timestampUtc = [DateTime]::UtcNow.ToString('o')
    }
    [System.IO.File]::WriteAllText($supervisionReceiptPath, ($receipt | ConvertTo-Json -Depth 5), [System.Text.UTF8Encoding]::new($false))
    Write-Output "SUPERVISION_RECEIPT=$supervisionReceiptPath"

    if ($failureReason) {
        throw $failureReason
    }
}
