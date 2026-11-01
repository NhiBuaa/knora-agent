param(
    [Parameter(Mandatory = $true)]
    [DateTimeOffset]$AbsoluteCutoff,
    [Parameter(Mandatory = $true)]
    [DateTimeOffset]$HardDeadline,
    [string]$SubjectSha = '',
    [string]$ProjectName = '',
    [ValidateSet('None', 'Success', 'HangStartup', 'HangRunner', 'HangCleanup', 'FailCleanup', 'FailPreflight')][string]$StubMode = 'None',
    [switch]$WorkerMode,
    [switch]$AllowDirty
)

$ErrorActionPreference = 'Stop'
$repoRoot = 'C:\Developer\Projects\knora-agent-worktree\fix-browser-session-persistence'
Set-Location $repoRoot

if ($HardDeadline -le $AbsoluteCutoff) {
    throw "INVALID_DEADLINES: HardDeadline ($($HardDeadline.ToString('o'))) must be strictly after AbsoluteCutoff ($($AbsoluteCutoff.ToString('o')))"
}

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
$pidsFilePath = Join-Path $resDir 'worker-pids.json'
$ownershipPath = Join-Path $resDir 'worker-ownership.json'

function Unwrap-Items($items) {
    if ($items -is [System.Collections.IEnumerable] -and $items -isnot [string] -and $items -isnot [System.Collections.IDictionary] -and $items -isnot [System.Management.Automation.PSCustomObject]) {
        foreach ($sub in $items) {
            if ($sub -is [System.Collections.IEnumerable] -and $sub -isnot [string] -and $sub -isnot [System.Collections.IDictionary] -and $sub -isnot [System.Management.Automation.PSCustomObject]) {
                foreach ($subsub in $sub) {
                    $subsub
                }
            } else {
                $sub
            }
        }
    } else {
        $items
    }
}

function Get-ProcessDescendantIds([int]$parentPid) {
    $descendants = [System.Collections.Generic.List[int]]::new()
    $queue = [System.Collections.Generic.Queue[int]]::new()
    $queue.Enqueue($parentPid)
    while ($queue.Count -gt 0) {
        $curr = $queue.Dequeue()
        try {
            $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $curr" -ErrorAction SilentlyContinue
            foreach ($ch in $children) {
                $chPid = [int]$ch.ProcessId
                if (-not $descendants.Contains($chPid)) {
                    $descendants.Add($chPid)
                    $queue.Enqueue($chPid)
                }
            }
        } catch {}
    }
    return $descendants
}

function Invoke-BoundedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory = $true)][int]$TimeoutMs,
        [switch]$CaptureOutput
    )
    $safeTimeout = [Math]::Max(100, $TimeoutMs)
    $pInfo = New-Object System.Diagnostics.ProcessStartInfo
    $pInfo.FileName = $FilePath
    if ($ArgumentList -and $ArgumentList.Count -gt 0) {
        $pInfo.Arguments = ($ArgumentList -join ' ')
    }
    $pInfo.UseShellExecute = $false
    $pInfo.CreateNoWindow = $true
    if ($CaptureOutput) {
        $pInfo.RedirectStandardOutput = $true
        $pInfo.RedirectStandardError = $true
    }
    $p = [System.Diagnostics.Process]::Start($pInfo)
    $null = $p.Handle
    $finished = $p.WaitForExit($safeTimeout)
    $timedOut = $false
    if (-not $finished) {
        $timedOut = $true
        try { Start-Process "taskkill" -ArgumentList "/PID $($p.Id) /T /F" -NoNewWindow -Wait } catch {}
    } else {
        $p.WaitForExit()
    }
    $out = if ($CaptureOutput -and -not $timedOut) { $p.StandardOutput.ReadToEnd() } else { '' }
    $err = if ($CaptureOutput -and -not $timedOut) { $p.StandardError.ReadToEnd() } else { '' }
    return [ordered]@{
        ExitCode = if ($timedOut) { -1 } else { $p.ExitCode }
        TimedOut = $timedOut
        StdOut = $out
        StdErr = $err
    }
}

# ==============================================================================
# INNER WORKER MODE: Executes inside the isolated environment reservation
# ==============================================================================
if ($WorkerMode) {
    Write-Output "Worker started for project $project with Subject SHA $resolvedSubjectSha"
    $null = New-Item -ItemType Directory -Path $resDir -Force

    # Record worker PID
    $initialPids = [ordered]@{ workerPid = $PID; childPid = $null; grandchildPid = $null }
    [System.IO.File]::WriteAllText($pidsFilePath, ($initialPids | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))

    # STUB MODE (used for local fault tests without Docker)
    if ($StubMode -ne 'None') {
        Write-Output "Worker running in STUB MODE: $StubMode"

        if ($StubMode -eq 'FailPreflight') {
            $stubOwnership = [ordered]@{
                schemaVersion = 1
                project = $project
                workerPid = $PID
                acquired = $true
                startupAttempted = $false
                timestampUtc = [DateTime]::UtcNow.ToString('o')
            }
            [System.IO.File]::WriteAllText($ownershipPath, ($stubOwnership | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))
            throw "SIMULATED_PREFLIGHT_FAILURE: Port in use or project not fresh"
        }

        # In stub mode, simulate successful reservation acquisition and startup attempt
        $stubOwnership = [ordered]@{
            schemaVersion = 1
            project = $project
            workerPid = $PID
            acquired = $true
            startupAttempted = $true
            timestampUtc = [DateTime]::UtcNow.ToString('o')
        }
        [System.IO.File]::WriteAllText($ownershipPath, ($stubOwnership | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))

        if ($StubMode -eq 'HangStartup') {
            $cleanPidPath = $pidsFilePath.Replace('\', '/')
            $nodeScript = "const { spawn } = require('child_process'); const fs = require('fs'); const gc = spawn('node', ['-e', 'setTimeout(()=>{}, 600000)']); const pids = { workerPid: $PID, childPid: process.pid, grandchildPid: gc.pid }; fs.writeFileSync('$cleanPidPath', JSON.stringify(pids)); setTimeout(() => {}, 600000);"
            $child = Start-Process "node" -ArgumentList "-e", "`"$nodeScript`"" -PassThru -NoNewWindow
            $null = $child.Handle
            Start-Sleep -Seconds 600
        }
        if ($StubMode -eq 'HangRunner') {
            $migReceipt = [ordered]@{
                schemaVersion = 1
                project = $project
                subjectSha = $resolvedSubjectSha
                cycleCompleted = $true
                steps = @("BaselineSetup", "ApplyVerified", "NoOpVerified", "RollbackVerified", "DesiredApplyVerified")
                timestampUtc = [DateTime]::UtcNow.ToString('o')
            }
            [System.IO.File]::WriteAllText($migrationReceiptPath, ($migReceipt | ConvertTo-Json -Depth 5), [System.Text.UTF8Encoding]::new($false))

            $cleanPidPath = $pidsFilePath.Replace('\', '/')
            $nodeScript = "const { spawn } = require('child_process'); const fs = require('fs'); const gc = spawn('node', ['-e', 'setTimeout(()=>{}, 600000)']); const pids = { workerPid: $PID, childPid: process.pid, grandchildPid: gc.pid }; fs.writeFileSync('$cleanPidPath', JSON.stringify(pids)); setTimeout(() => {}, 600000);"
            $child = Start-Process "node" -ArgumentList "-e", "`"$nodeScript`"" -PassThru -NoNewWindow
            $null = $child.Handle
            Start-Sleep -Seconds 600
        }
        if ($StubMode -eq 'HangCleanup') {
            $migReceipt = [ordered]@{
                schemaVersion = 1
                project = $project
                subjectSha = $resolvedSubjectSha
                cycleCompleted = $true
                steps = @("BaselineSetup", "ApplyVerified", "NoOpVerified", "RollbackVerified", "DesiredApplyVerified")
                timestampUtc = [DateTime]::UtcNow.ToString('o')
            }
            [System.IO.File]::WriteAllText($migrationReceiptPath, ($migReceipt | ConvertTo-Json -Depth 5), [System.Text.UTF8Encoding]::new($false))

            $cleanPidPath = $pidsFilePath.Replace('\', '/')
            $nodeScript = "const { spawn } = require('child_process'); const fs = require('fs'); const gc = spawn('node', ['-e', 'setTimeout(()=>{}, 600000)']); const pids = { workerPid: $PID, childPid: process.pid, grandchildPid: gc.pid }; fs.writeFileSync('$cleanPidPath', JSON.stringify(pids)); setTimeout(() => {}, 600000);"
            $child = Start-Process "node" -ArgumentList "-e", "`"$nodeScript`"" -PassThru -NoNewWindow
            $null = $child.Handle
            Start-Sleep -Seconds 600
        }
        if ($StubMode -eq 'FailCleanup') {
            $migReceipt = [ordered]@{
                schemaVersion = 1
                project = $project
                subjectSha = $resolvedSubjectSha
                cycleCompleted = $true
                steps = @("BaselineSetup", "ApplyVerified", "NoOpVerified", "RollbackVerified", "DesiredApplyVerified")
                timestampUtc = [DateTime]::UtcNow.ToString('o')
            }
            [System.IO.File]::WriteAllText($migrationReceiptPath, ($migReceipt | ConvertTo-Json -Depth 5), [System.Text.UTF8Encoding]::new($false))

            $cleanPidPath = $pidsFilePath.Replace('\', '/')
            $nodeScript = "const { spawn } = require('child_process'); const fs = require('fs'); const gc = spawn('node', ['-e', 'setTimeout(()=>{}, 600000)']); const pids = { workerPid: $PID, childPid: process.pid, grandchildPid: gc.pid }; fs.writeFileSync('$cleanPidPath', JSON.stringify(pids)); setTimeout(() => {}, 600000);"
            $child = Start-Process "node" -ArgumentList "-e", "`"$nodeScript`"" -PassThru -NoNewWindow
            $null = $child.Handle
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
    & "$repoRoot/scripts/prepare-figma-e2e.ps1" -Project $project -OwnershipPath $ownershipPath -Run {
        param($proj, $composeArgs)
        $repo = 'C:\Developer\Projects\knora-agent-worktree\fix-browser-session-persistence'
        $targetDir = Join-Path $repo "frontend/test-results/$proj"

        # Record ownership receipt: This run successfully acquired harness reservation and started compose!
        $workerOwnership = [ordered]@{
            schemaVersion = 1
            project = $proj
            workerPid = $PID
            acquired = $true
            startupAttempted = $true
            timestampUtc = [DateTime]::UtcNow.ToString('o')
        }
        $ownershipPathWorker = Join-Path $targetDir 'worker-ownership.json'
        [System.IO.File]::WriteAllText($ownershipPathWorker, ($workerOwnership | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))

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
        $clientRaw = Invoke-RestMethod -Uri "http://127.0.0.1:8380/admin/realms/knora-dev/clients?clientId=knora-web" -Headers $kcHeaders
        $clientList = @(Unwrap-Items $clientRaw)
        if ($clientList.Count -ne 1 -or -not $clientList[0] -or [string]::IsNullOrWhiteSpace($clientList[0].id)) {
            throw "BASELINE_CLIENT_AMBIGUOUS_OR_MISSING: Expected exactly 1 client for clientId=knora-web, found $($clientList.Count)"
        }
        $clientUuid = $clientList[0].id

        # Delete policy mapper if present
        $mappersRaw = Invoke-RestMethod -Uri "http://127.0.0.1:8380/admin/realms/knora-dev/clients/$clientUuid/protocol-mappers/models" -Headers $kcHeaders
        $mappers = @(Unwrap-Items $mappersRaw)
        $targetMappers = @($mappers | Where-Object { $_ -and $_.name -eq 'knora-session-policy' })
        foreach ($m in $targetMappers) {
            if (-not $m -or [string]::IsNullOrWhiteSpace($m.id)) {
                throw "BASELINE_MAPPER_INVALID_ID: Target mapper has empty or missing id"
            }
            try {
                Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:8380/admin/realms/knora-dev/clients/$clientUuid/protocol-mappers/models/$($m.id)" -Headers $kcHeaders -ErrorAction Stop | Out-Null
            } catch {
                $is404 = $false
                if ($_.Exception -and $_.Exception.Response) {
                    try {
                        if ([int]$_.Exception.Response.StatusCode -eq 404) {
                            $is404 = $true
                        }
                    } catch {}
                }
                if (-not $is404) {
                    throw
                }
            }
        }

        # Readback confirming absence: verify no target mapper remains
        $verifyMappersRaw = Invoke-RestMethod -Uri "http://127.0.0.1:8380/admin/realms/knora-dev/clients/$clientUuid/protocol-mappers/models" -Headers $kcHeaders
        $remainingMappers = @(Unwrap-Items $verifyMappersRaw)
        $residual = @($remainingMappers | Where-Object { $_ -and $_.name -eq 'knora-session-policy' })
        if ($residual.Count -gt 0) {
            throw "BASELINE_MAPPER_RESIDUAL: Found $($residual.Count) residual 'knora-session-policy' mapper(s) after deletion"
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

# 1. VERIFY NO PREEXISTING CANONICAL HARNESS RESERVATION
$canonicalHarnessLockPath = Join-Path ([System.IO.Path]::GetTempPath()) "knora-figma-reservation-$project.lock"
if (Test-Path $canonicalHarnessLockPath) {
    throw "CANONICAL_HARNESS_PROJECT_RESERVED: Project $project is already reserved by preexisting harness lock ($canonicalHarnessLockPath)"
}

# 2. ACQUIRE OUTER SUPERVISOR RESERVATION ATOMICALLY
$supervisorReservationPath = Join-Path ([System.IO.Path]::GetTempPath()) "knora-session-supervisor-$project.lock"
if (Test-Path $supervisorReservationPath) {
    throw "FIGMA_SUPERVISOR_PROJECT_RESERVED: Project $project already has an active supervisor reservation ($supervisorReservationPath)"
}

$supervisorReservation = $null
try {
    $supervisorReservation = [System.IO.File]::Open(
        $supervisorReservationPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
    $resData = @{
        project = $project
        supervisorPid = $PID
        subjectSha = $resolvedSubjectSha
        cutoffUtc = $AbsoluteCutoff.ToString('o')
        hardDeadlineUtc = $HardDeadline.ToString('o')
        status = 'RESERVED'
        timestampUtc = [DateTime]::UtcNow.ToString('o')
    }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes(($resData | ConvertTo-Json))
    $supervisorReservation.Write($bytes, 0, $bytes.Length)
    $supervisorReservation.Flush()
    Write-Output "Supervisor reservation acquired: $supervisorReservationPath"
} catch [System.IO.IOException] {
    throw "FIGMA_SUPERVISOR_PROJECT_RESERVED: Project $project already has an active supervisor reservation ($supervisorReservationPath)"
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
$supervisorStartTime = [DateTime]::UtcNow
$workerProc = Start-Process -FilePath $psExe -ArgumentList $workerArgs -PassThru -NoNewWindow
$null = $workerProc.Handle

$workerFinishedCleanly = $false
$childProcessesKilled = $false
$failureReason = $null
$allTrackedPids = [System.Collections.Generic.List[int]]::new()
$allTrackedPids.Add([int]$workerProc.Id)

try {
    # Calculate timeout for the entire worker
    $remainingMs = [Math]::Max(100, [int](($AbsoluteCutoff - [DateTimeOffset]::UtcNow).TotalMilliseconds))
    $completedInTime = $workerProc.WaitForExit($remainingMs)

    if (-not $completedInTime) {
        $failureReason = "WHOLE_PACKAGE_TIMEOUT_CUTOFF: Worker exceeded AbsoluteCutoff ($($AbsoluteCutoff.ToString('o')))"
        Write-Output $failureReason
    } else {
        $workerProc.WaitForExit()
        if ($workerProc.ExitCode -eq 0) {
            $workerFinishedCleanly = $true
        } else {
            $failureReason = "Worker process exited with non-zero exit code: $($workerProc.ExitCode)"
        }
    }
} finally {
    # ==========================================================================
    # POSTCONDITION 1: TERMINATE ALL WORKER DESCENDANT PROCESSES & VERIFY IN OS TABLE
    # ==========================================================================
    Write-Output "Verifying process tree termination for worker PID $($workerProc.Id)..."

    # Read pids file if available
    if (Test-Path $pidsFilePath) {
        try {
            $writtenPids = Get-Content $pidsFilePath -Raw | ConvertFrom-Json
            if ($writtenPids.childPid) { $allTrackedPids.Add([int]$writtenPids.childPid) }
            if ($writtenPids.grandchildPid) { $allTrackedPids.Add([int]$writtenPids.grandchildPid) }
        } catch {}
    }

    # Discover any additional descendants
    $discoveredDescendants = Get-ProcessDescendantIds $workerProc.Id
    foreach ($dPid in $discoveredDescendants) {
        if (-not $allTrackedPids.Contains($dPid)) { $allTrackedPids.Add($dPid) }
    }

    # Terminate process tree via taskkill if still running (validate creation identity)
    if (-not $workerProc.HasExited) {
        try {
            $tkProc = Start-Process "taskkill" -ArgumentList "/PID $($workerProc.Id) /T /F" -PassThru -NoNewWindow -Wait
            $null = $tkProc.Handle
        } catch {
            try { Stop-Process -Id $workerProc.Id -Force } catch {}
        }
    }

    # Verify all tracked PIDs are dead in the OS process table
    $lingeringProcesses = [System.Collections.Generic.List[int]]::new()
    for ($checkIter = 0; $checkIter -lt 10; $checkIter++) {
        $lingeringProcesses.Clear()
        foreach ($pidToCheck in $allTrackedPids) {
            $procFound = Get-Process -Id $pidToCheck -ErrorAction SilentlyContinue
            if ($procFound) {
                # Guard against recycled PIDs started before supervisor
                if ($procFound.StartTime.ToUniversalTime() -ge $supervisorStartTime) {
                    $lingeringProcesses.Add($pidToCheck)
                    try { Stop-Process -Id $pidToCheck -Force } catch {}
                }
            }
        }
        if ($lingeringProcesses.Count -eq 0) { break }
        Start-Sleep -Milliseconds 200
    }

    if ($lingeringProcesses.Count -gt 0) {
        $childProcessesKilled = $false
        if (-not $failureReason) {
            $failureReason = "PROCESS_TERMINATION_FAILED: PIDs still alive in OS process table: $($lingeringProcesses -join ', ')"
        }
    } else {
        $childProcessesKilled = $true
    }

    # ==========================================================================
    # POSTCONDITION 2: CLEANUP BOUNDED BY HARDDEADLINE & PRESERVE FOREIGN RESOURCES
    # ==========================================================================
    $cleanupVerified = $false
    $nowCleanup = [DateTimeOffset]::UtcNow

    # Teardown must ONLY occur if this run actually acquired ownership and attempted startup!
    $workerAttemptedStartup = $false
    if (Test-Path $ownershipPath) {
        try {
            $ownerData = Get-Content $ownershipPath -Raw | ConvertFrom-Json
            if ($ownerData.startupAttempted -and $ownerData.workerPid -eq $workerProc.Id) {
                $workerAttemptedStartup = $true
            }
        } catch {}
    }

    if (-not $workerAttemptedStartup) {
        Write-Output "Startup was not attempted by worker PID $($workerProc.Id); skipping compose teardown to protect foreign resources."
        if (-not $failureReason) {
            $failureReason = "WORKER_STARTUP_NOT_ATTEMPTED: Worker did not acquire harness reservation or failed before startup"
        }
    } else {
        if ($nowCleanup -ge $HardDeadline) {
            if (-not $failureReason) {
                $failureReason = "HARD_DEADLINE_EXCEEDED_BEFORE_CLEANUP: Now=$($nowCleanup.ToString('o')) >= HardDeadline=$($HardDeadline.ToString('o'))"
            }
        } else {
            $remMs = [int](($HardDeadline - [DateTimeOffset]::UtcNow).TotalMilliseconds)
            if ($remMs -lt 1500) {
                if (-not $failureReason) {
                    $failureReason = "INSUFFICIENT_TIME_FOR_CLEANUP: Only $remMs ms remaining before HardDeadline"
                }
            } else {
                $downTimeoutMs = [Math]::Max(500, $remMs - 1000)

                if ($StubMode -eq 'HangCleanup') {
                    # Exercise real bounded process timeout
                    Write-Output "Executing Stub Cleanup (HangCleanup) bounded by timeout ${downTimeoutMs}ms..."
                    $downRes = Invoke-BoundedProcess -FilePath "node" -ArgumentList @("-e", "`"setTimeout(()=>{}, 600000)`"") -TimeoutMs $downTimeoutMs
                    if ($downRes.TimedOut) {
                        if (-not $failureReason) {
                            $failureReason = "CLEANUP_DOCKER_DOWN_TIMEOUT: Teardown command exceeded remaining HardDeadline"
                        }
                    }
                } elseif ($StubMode -eq 'FailCleanup') {
                    # Exercise real non-zero exit code failure
                    Write-Output "Executing Stub Cleanup (FailCleanup)..."
                    $downRes = Invoke-BoundedProcess -FilePath "node" -ArgumentList @("-e", "`"process.exit(42)`"") -TimeoutMs $downTimeoutMs
                    if ($downRes.ExitCode -ne 0) {
                        if (-not $failureReason) {
                            $failureReason = "CLEANUP_DOCKER_DOWN_FAILED: Teardown command returned exit code $($downRes.ExitCode)"
                        }
                    }
                } elseif ($StubMode -eq 'None') {
                    # Real Production Docker Teardown
                    $composeArgs = @(
                        '--project-name', $project,
                        '--project-directory', $repoRoot,
                        '-f', (Join-Path $repoRoot 'docker-compose.dev.yml'),
                        '--profile', 'figma'
                    )
                    Write-Output "Executing Docker Teardown for project $project bounded by ${downTimeoutMs}ms..."
                    $downRes = Invoke-BoundedProcess -FilePath "docker" -ArgumentList (@("compose") + $composeArgs + @("down", "--volumes", "--remove-orphans")) -TimeoutMs $downTimeoutMs
                    if ($downRes.TimedOut) {
                        if (-not $failureReason) {
                            $failureReason = "CLEANUP_DOCKER_DOWN_TIMEOUT: docker compose down exceeded HardDeadline"
                        }
                    } elseif ($downRes.ExitCode -ne 0) {
                        if (-not $failureReason) {
                            $failureReason = "CLEANUP_DOCKER_DOWN_FAILED: docker compose down returned exit code $($downRes.ExitCode)"
                        }
                    } else {
                        # Inspect postconditions: resources (bounded by remaining time)
                        $lingeringResource = $null
                        foreach ($resource in @(@('ps', '-a'), @('volume', 'ls'), @('network', 'ls'))) {
                            $qRemMs = [Math]::Max(500, [int](($HardDeadline - [DateTimeOffset]::UtcNow).TotalMilliseconds - 1000))
                            $qRes = Invoke-BoundedProcess -FilePath "docker" -ArgumentList (@($resource) + @("--filter", "label=com.docker.compose.project=$project", "--quiet")) -TimeoutMs $qRemMs -CaptureOutput
                            if ($qRes.TimedOut) {
                                $lingeringResource = "$resource query timed out"
                                break
                            } elseif ($qRes.ExitCode -ne 0 -or ($qRes.StdOut.Trim().Length -gt 0)) {
                                $lingeringResource = "$resource (output: $($qRes.StdOut.Trim()))"
                                break
                            }
                        }
                        if ($lingeringResource) {
                            if (-not $failureReason) {
                                $failureReason = "CLEANUP_POSTCONDITION_FAILED: Remaining $lingeringResource for project $project"
                            }
                        } else {
                            # Inspect postconditions: port listeners (each 150ms)
                            $activePort = $null
                            foreach ($port in 3300, 8800, 8380, 5543, 9900, 9901, 1025, 8025) {
                                $listener = New-Object Net.Sockets.TcpClient
                                try {
                                    $connected = $listener.ConnectAsync('127.0.0.1', $port).Wait(150)
                                    if ($connected -and $listener.Connected) {
                                        $activePort = $port
                                        break
                                    }
                                } catch [AggregateException] {
                                } finally { $listener.Dispose() }
                            }
                            if ($activePort) {
                                if (-not $failureReason) {
                                    $failureReason = "CLEANUP_PORT_LISTENER_ACTIVE: Port $activePort still has an active listener"
                                }
                            } else {
                                $cleanupVerified = $true
                            }
                        }
                    }
                } else {
                    # Other stub modes: Success, HangStartup, HangRunner
                    if ($workerFinishedCleanly -or $childProcessesKilled) {
                        $cleanupVerified = $true
                    }
                }

                # Only delete worker's canonical harness lock if verified AND this run owned it
                if ($cleanupVerified -and (Test-Path $canonicalHarnessLockPath)) {
                    Remove-Item -LiteralPath $canonicalHarnessLockPath -Force -ErrorAction SilentlyContinue
                }
            }
        }
    }

    # ==========================================================================
    # POSTCONDITION 3: RESERVATION DISPOSITION & FINAL TIMING AUDIT
    # ==========================================================================
    $reservationReleased = $false
    $completedAt = [DateTimeOffset]::UtcNow
    $withinHardDeadline = ($completedAt -le $HardDeadline)

    if (-not $withinHardDeadline) {
        if (-not $failureReason) {
            $failureReason = "HARD_DEADLINE_EXCEEDED: Completed at $($completedAt.ToString('o')) > HardDeadline $($HardDeadline.ToString('o'))"
        }
    }

    if ($cleanupVerified -and $withinHardDeadline -and $childProcessesKilled) {
        # Cleanup fully verified and within deadline: Release reservation!
        if ($supervisorReservation) {
            $supervisorReservation.Dispose()
            $supervisorReservation = $null
            if (Test-Path $supervisorReservationPath) {
                Remove-Item -LiteralPath $supervisorReservationPath -Force -ErrorAction SilentlyContinue
            }
        }
        $reservationReleased = $true
        Write-Output "Supervisor reservation released cleanly: $supervisorReservationPath"
    } else {
        # Cleanup failed, incomplete, or hard deadline exceeded:
        # RETAIN RESERVATION LOCK! Do NOT delete $supervisorReservationPath!
        Write-Output "WARNING: Cleanup could not be verified or HardDeadline exceeded. Retaining reservation lock at $supervisorReservationPath for inspection."
        if ($supervisorReservation) {
            try {
                $errData = @{
                    project = $project
                    supervisorPid = $PID
                    subjectSha = $resolvedSubjectSha
                    status = 'RESERVED_CLEANUP_FAILED'
                    failureReason = $failureReason
                    completedAtUtc = $completedAt.ToString('o')
                } | ConvertTo-Json
                $bytes = [System.Text.Encoding]::UTF8.GetBytes($errData)
                $supervisorReservation.Position = 0
                $supervisorReservation.Write($bytes, 0, $bytes.Length)
                $supervisorReservation.SetLength($bytes.Length)
                $supervisorReservation.Flush()
            } catch {}
            $supervisorReservation.Dispose()
            $supervisorReservation = $null
        }
        $reservationReleased = $false
    }

    # Determine final status
    $finalStatus = if ($workerFinishedCleanly -and $cleanupVerified -and $reservationReleased) {
        "SUCCESS"
    } elseif ($childProcessesKilled -and $cleanupVerified -and $reservationReleased -and ($failureReason -like "*TIMEOUT*")) {
        "TIMEOUT_CLEANUP_VERIFIED"
    } else {
        "CLEANUP_FAILED_OR_INCOMPLETE"
    }

    $receipt = [ordered]@{
        schemaVersion = 1
        project = $project
        subjectSha = $resolvedSubjectSha
        cutoffUtc = $AbsoluteCutoff.ToString('o')
        hardDeadlineUtc = $HardDeadline.ToString('o')
        completedAtUtc = $completedAt.ToString('o')
        withinHardDeadline = $withinHardDeadline
        workerPid = $workerProc.Id
        trackedPids = @($allTrackedPids)
        workerFinishedCleanly = $workerFinishedCleanly
        childProcessesKilled = $childProcessesKilled
        cleanupVerified = $cleanupVerified
        reservationReleased = $reservationReleased
        reservationPath = $supervisorReservationPath
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
