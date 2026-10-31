param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Storage', 'Http')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$RunId,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceRoot,

    [Parameter(Mandatory = $true)]
    [string]$Collection,

    [Parameter(Mandatory = $true)]
    [scriptblock]$Run
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))

# 1. Parameter Normalization and Validation
try {
    $guid = [guid]::Parse($RunId)
} catch {
    throw "RETRIEVAL_TEST_RUN_ID_INVALID: RunId must be a valid Guid ($RunId)"
}
$runIdN = $guid.ToString('N').ToLowerInvariant()
$project = "knora-retrieval-test-$runIdN"
$expectedPgVolume = "${project}_verification-pgdata"
$expectedQdVolume = "${project}_verification-qdrantdata"
$expectedNet = "${project}_verification-isolated"

if ($Collection -notmatch '^[a-zA-Z0-9_-]+$') {
    throw "RETRIEVAL_TEST_COLLECTION_INVALID: collection name contains invalid characters ($Collection)"
}

# 2. Block ambient DOCKER_/COMPOSE_/KNORA_S2_ without printing secrets
foreach ($item in Get-ChildItem Env:) {
    if ($item.Name -match '^(DOCKER_|COMPOSE_|KNORA_S2_)' -and $item.Value.Trim()) {
        throw "RETRIEVAL_TEST_AMBIENT_OVERRIDE_REJECTED: $($item.Name)"
    }
}

# 3. Path Preflight Validation BEFORE Any Mutation
if (-not [System.IO.Path]::IsPathRooted($EvidenceRoot) -or (-not [System.IO.Path]::IsPathFullyQualified($EvidenceRoot))) {
    throw "RETRIEVAL_TEST_EVIDENCE_ROOT_INVALID: EvidenceRoot must be an absolute path ($EvidenceRoot)"
}

function Assert-NoReparsePoint($pathToCheck) {
    $curr = [System.IO.Path]::GetFullPath($pathToCheck)
    while ($curr) {
        if (Test-Path -LiteralPath $curr -ErrorAction Stop) {
            $item = Get-Item -LiteralPath $curr -Force -ErrorAction Stop
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                throw "RETRIEVAL_TEST_PATH_REJECTED: reparse point detected at $curr"
            }
        }
        $parent = [System.IO.Path]::GetDirectoryName($curr)
        if (-not $parent -or $parent -eq $curr) { break }
        $curr = $parent
    }
}

# Assert all repository and bind paths are non-reparse
Assert-NoReparsePoint $repositoryRoot
Assert-NoReparsePoint (Join-Path $repositoryRoot 'backend')
Assert-NoReparsePoint (Join-Path $repositoryRoot 'docker-compose.dev.yml')
$bindFixture = Join-Path $repositoryRoot 'evals/fixtures/pdf_retrieval_v3_s2'
if (Test-Path -LiteralPath $bindFixture) {
    Assert-NoReparsePoint $bindFixture
}

$evidenceRootFull = [System.IO.Path]::GetFullPath($EvidenceRoot)
Assert-NoReparsePoint $evidenceRootFull

if (-not (Test-Path -LiteralPath $evidenceRootFull)) {
    $null = New-Item -ItemType Directory -Force -Path $evidenceRootFull
}

$objectRoot = Join-Path $evidenceRootFull 'http-objects'
# Object root must be fresh and not pre-exist (even empty directory is refused)
if (Test-Path -LiteralPath $objectRoot) {
    throw "RETRIEVAL_TEST_OBJECT_ROOT_NOT_FRESH: object root must be fresh and not pre-exist ($objectRoot)"
}
$null = New-Item -ItemType Directory -Force -Path $objectRoot
Assert-NoReparsePoint $objectRoot

# 4. Exclusive Reservation Lock
$reservationPath = Join-Path ([IO.Path]::GetTempPath()) "knora-retrieval-reservation-$project.lock"
$reservation = $null
$startupAttempted = $false
$innerRunFailed = $false
$cleanupSucceeded = $false
$cleanupErrors = [System.Collections.Generic.List[string]]::new()

$ledger = [PSCustomObject]@{
    containers = [System.Collections.Generic.List[string]]::new()
    volumes = [System.Collections.Generic.List[string]]::new()
    networks = [System.Collections.Generic.List[string]]::new()
}
$leftovers = [PSCustomObject]@{
    containers = [System.Collections.Generic.List[string]]::new()
    volumes = [System.Collections.Generic.List[string]]::new()
    networks = [System.Collections.Generic.List[string]]::new()
}

$savedEnvironment = @{}
foreach ($name in @(
    'KNORA_S2_ISOLATED_TESTS',
    'KNORA_S2_RUN_ID',
    'KNORA_S2_PROJECT',
    'KNORA_S2_POSTGRES_VOLUME',
    'KNORA_S2_QDRANT_VOLUME',
    'KNORA_S2_EVIDENCE_ROOT',
    'KNORA_S2_OBJECT_STORE_ROOT',
    'KNORA_S2_APPLICATION_COLLECTION',
    'KNORA_S2_API_CREDENTIALS_JSON',
    'KNORA_S2_HTTP_WORKSPACE_ID',
    'KNORA_S2_HTTP_API_KEY',
    'KNORA_DATABASE_URL',
    'KNORA_LEXICAL_QDRANT_URL',
    'KNORA_PROVIDER_MODE',
    'KNORA_EMBEDDING_PROVIDER',
    'KNORA_GENERATION_PROVIDER',
    'KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID',
    'KNORA_RETRIEVAL_CONFIGURATION_ID',
    'KNORA_OBJECT_STORE_BACKEND',
    'KNORA_OBJECT_STORE_ROOT'
)) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$primaryFailure = $null
$containerIdentity = @{}
$volumeIdentity = @{}
$networkIdentity = @{}
$servicesToStart = if ($Mode -eq 'Http') { @('verification-postgres', 'verification-qdrant', 'verification-api') } else { @('verification-postgres', 'verification-qdrant') }

$composeFile = Join-Path $repositoryRoot 'docker-compose.dev.yml'
$dockerHostArgs = if ($IsWindows) { @('--host', 'npipe:////./pipe/dockerDesktopLinuxEngine') } else { @() }

    # 9. Discover and Validate Proved Ownership of Resources
    function Test-OwnedContainer($cId) {
        try {
        $inspectJson = (& docker @dockerHostArgs inspect $cId | Out-String)
        if ($LASTEXITCODE -ne 0 -or -not $inspectJson.Trim()) { return $false }
        $cData = ($inspectJson | ConvertFrom-Json)[0]
        $labels = $cData.Config.Labels
        if ($labels.'com.docker.compose.project' -ne $project) { return $false }
        if ($labels.'com.docker.compose.service' -notin $servicesToStart) { return $false }
        $wDir = $labels.'com.docker.compose.project.working_dir'
        if (-not $wDir -or [IO.Path]::GetFullPath($wDir) -ne $repositoryRoot) { return $false }
        $cFile = $labels.'com.docker.compose.project.config_files'
        if (-not $cFile -or [IO.Path]::GetFullPath($cFile) -ne [IO.Path]::GetFullPath($composeFile)) { return $false }

        $mounts = @($cData.Mounts)
        $service = $labels.'com.docker.compose.service'
        if ($service -eq 'verification-api') {
            if ($mounts.Count -ne 2) { return $false }
            $objects = @($mounts | Where-Object Destination -eq '/s2-objects')
            $fixture = @($mounts | Where-Object Destination -eq '/app/evals/fixtures/pdf_retrieval_v3_s2')
            if ($objects.Count -ne 1 -or $fixture.Count -ne 1 -or
                $objects[0].Type -ne 'bind' -or $objects[0].Source -ne $objectRoot -or $objects[0].RW -ne $true -or
                $fixture[0].Type -ne 'bind' -or $fixture[0].Source -ne $bindFixture -or $fixture[0].RW -ne $false) { return $false }
        } else {
            $volume = if ($service -eq 'verification-postgres') { $expectedPgVolume } else { $expectedQdVolume }
            $destination = if ($service -eq 'verification-postgres') { '/var/lib/postgresql/data' } else { '/qdrant/storage' }
            if ($mounts.Count -ne 1 -or $mounts[0].Type -ne 'volume' -or
                $mounts[0].Name -ne $volume -or $mounts[0].Destination -ne $destination -or
                $mounts[0].RW -ne $true -or -not (Test-OwnedVolume $volume)) { return $false }
        }
        $networks = @($cData.NetworkSettings.Networks.PSObject.Properties)
        if ($networks.Count -ne 1 -or $networks[0].Name -ne $expectedNet -or
            -not (Test-OwnedNetwork $networks[0].Value.NetworkID)) { return $false }
        $networkIds = @($networks | ForEach-Object { "$($_.Name)=$($_.Value.NetworkID)" })
        $identity = @($cData.Id, $labels, @($mounts | Sort-Object Destination), $networkIds) | ConvertTo-Json -Depth 20 -Compress
        if ($cData.Id -ne $cId) { return $false }
        if ($containerIdentity.ContainsKey($cId) -and $containerIdentity[$cId] -ne $identity) { return $false }
        $containerIdentity[$cId] = $identity
        return $true
        } catch { return $false }
    }

    function Test-OwnedVolume($vName) {
        try {
        if ($vName -notin @($expectedPgVolume, $expectedQdVolume)) { return $false }
        $vInspect = (& docker @dockerHostArgs volume inspect $vName | Out-String)
        if ($LASTEXITCODE -ne 0 -or -not $vInspect.Trim()) { return $false }
        $vData = ($vInspect | ConvertFrom-Json)[0]
        if ($vData.Labels.'com.docker.compose.project' -ne $project) { return $false }
        if ($vData.Labels.'com.docker.compose.volume' -notin @('verification-pgdata', 'verification-qdrantdata')) { return $false }
        if (-not $vData.CreatedAt -or $vData.Driver -ne 'local' -or $vData.Name -ne $vName) { return $false }
        $identity = $vData | Select-Object Name, CreatedAt, Driver, Labels, Options, Scope, Mountpoint | ConvertTo-Json -Depth 20 -Compress
        if ($volumeIdentity.ContainsKey($vName) -and $volumeIdentity[$vName] -ne $identity) { return $false }
        $volumeIdentity[$vName] = $identity
        return $true
        } catch { return $false }
    }

    function Test-OwnedNetwork($nId) {
        try {
        $nInspect = (& docker @dockerHostArgs network inspect $nId | Out-String)
        if ($LASTEXITCODE -ne 0 -or -not $nInspect.Trim()) { return $false }
        $nData = ($nInspect | ConvertFrom-Json)[0]
        if ($nData.Labels.'com.docker.compose.project' -ne $project) { return $false }
        if ($nData.Labels.'com.docker.compose.network' -ne 'verification-isolated') { return $false }
        if ($nData.Id -ne $nId -or $nData.Name -ne $expectedNet) { return $false }
        $identity = $nData | Select-Object Id, Name, Created, Driver, Labels, Options, IPAM, Internal, Scope | ConvertTo-Json -Depth 20 -Compress
        if ($networkIdentity.ContainsKey($nId) -and $networkIdentity[$nId] -ne $identity) { return $false }
        $networkIdentity[$nId] = $identity
        return $true
        } catch { return $false }
    }


function Update-OwnedInventory {
    # Inspect all containers matching project
    $foundContainers = @(& docker @dockerHostArgs ps -a --no-trunc --filter "label=com.docker.compose.project=$project" --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0) { throw 'RETRIEVAL_TEST_INVENTORY_FAILED' }
    foreach ($cId in $foundContainers) {
        if (Test-OwnedContainer $cId) {
            if (-not $ledger.containers.Contains($cId)) { $ledger.containers.Add($cId) }
        } else {
            if (-not $leftovers.containers.Contains($cId)) { $leftovers.containers.Add($cId) }
        }
    }

    # Inspect all volumes matching project label or prefix
    $foundVolumes = @(& docker @dockerHostArgs volume ls --filter "label=com.docker.compose.project=$project" --format '{{.Name}}')
    if ($LASTEXITCODE -ne 0) { throw 'RETRIEVAL_TEST_INVENTORY_FAILED' }
    $allVolNames = @(& docker @dockerHostArgs volume ls --format '{{.Name}}')
    if ($LASTEXITCODE -ne 0) { throw 'RETRIEVAL_TEST_INVENTORY_FAILED' }
    foreach ($v in $allVolNames) {
        if ($v.StartsWith("${project}_") -and $v -notin $foundVolumes) {
            $foundVolumes += $v
        }
    }
    foreach ($vName in $foundVolumes) {
        if (Test-OwnedVolume $vName) {
            if (-not $ledger.volumes.Contains($vName)) { $ledger.volumes.Add($vName) }
        } else {
            if (-not $leftovers.volumes.Contains($vName)) { $leftovers.volumes.Add($vName) }
        }
    }

    # Inspect all networks matching project label
    $foundNetworks = @(& docker @dockerHostArgs network ls --no-trunc --filter "label=com.docker.compose.project=$project" --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0) { throw 'RETRIEVAL_TEST_INVENTORY_FAILED' }
    foreach ($nId in $foundNetworks) {
        if (Test-OwnedNetwork $nId) {
            if (-not $ledger.networks.Contains($nId)) { $ledger.networks.Add($nId) }
        } else {
            if (-not $leftovers.networks.Contains($nId)) { $leftovers.networks.Add($nId) }
        }
    }

}

try {
    try {
        $reservation = [IO.File]::Open($reservationPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    } catch [IO.IOException] {
        throw "RETRIEVAL_TEST_PROJECT_RESERVED: $reservationPath"
    }

    # Pipeline cancellation can suppress finally commands; retain a durable recovery identity.
    $reservationIdentity = @{ project = $project; run_id = $runIdN; compose_file = $composeFile; repository = $repositoryRoot; evidence_root = $evidenceRootFull; services = $servicesToStart; volumes = @($expectedPgVolume, $expectedQdVolume); network = $expectedNet }
    $identityBytes = [Text.Encoding]::UTF8.GetBytes(($reservationIdentity | ConvertTo-Json -Depth 5))
    $reservation.Write($identityBytes, 0, $identityBytes.Length)
    $reservation.Flush($true)

    # 5. Verify Freshness: Reject existing retained resources
    foreach ($resource in @(@('ps', '-a'), @('volume', 'ls'), @('network', 'ls'))) {
        $existing = @(& docker @dockerHostArgs @resource --filter "label=com.docker.compose.project=$project" --quiet)
        if ($LASTEXITCODE -ne 0) { throw 'RETRIEVAL_TEST_INSPECTION_FAILED' }
        if ($existing.Count -gt 0) { throw 'RETRIEVAL_TEST_PROJECT_NOT_FRESH' }
    }
    foreach ($resource in 'volume', 'network') {
        $names = @(& docker @dockerHostArgs $resource ls --format '{{.Name}}')
        if ($LASTEXITCODE -ne 0) { throw 'RETRIEVAL_TEST_INSPECTION_FAILED' }
        if ($names | Where-Object { $_.StartsWith("${project}_") }) { throw 'RETRIEVAL_TEST_PROJECT_NOT_FRESH' }
    }

    # 6. Port Collision Check
    $targetPorts = if ($Mode -eq 'Http') { @(15433, 16433, 18053) } else { @(15433, 16433) }
    $runningIds = @(& docker @dockerHostArgs ps --no-trunc --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0) { throw 'RETRIEVAL_TEST_INSPECTION_FAILED' }
    foreach ($id in $runningIds) {
        $inspectedRaw = (& docker @dockerHostArgs inspect $id | Out-String)
        if ($LASTEXITCODE -ne 0 -or -not $inspectedRaw.Trim()) { throw 'RETRIEVAL_TEST_INSPECTION_FAILED' }
        if ($inspectedRaw.Trim()) {
            $containerInfo = ($inspectedRaw | ConvertFrom-Json)[0]
            if ($containerInfo.NetworkSettings.Ports) {
                foreach ($prop in $containerInfo.NetworkSettings.Ports.PSObject.Properties) {
                    foreach ($mapping in @($prop.Value)) {
                        if ($mapping -and $mapping.HostPort -and ([int]$mapping.HostPort -in $targetPorts)) {
                            if ($containerInfo.Config.Labels.'com.docker.compose.project' -ne $project) {
                                throw "RETRIEVAL_TEST_PORT_IN_USE: $($mapping.HostPort)"
                            }
                        }
                    }
                }
            }
        }
    }
    foreach ($port in $targetPorts) {
        $listener = New-Object Net.Sockets.TcpClient
        try {
            $connected = $listener.ConnectAsync('127.0.0.1', $port).Wait(150)
            if ($connected -and $listener.Connected) {
                throw "RETRIEVAL_TEST_PORT_IN_USE: $port"
            }
        } catch [AggregateException] {
        } finally {
            $listener.Dispose()
        }
    }

    # 7. Compose Command Setup and Provisioning
    $profile = if ($Mode -eq 'Http') { 'retrieval-http-test' } else { 'retrieval-test' }
    $composeArgs = @(
        '--project-name', $project,
        '--project-directory', $repositoryRoot,
        '-f', $composeFile,
        '--profile', $profile
    )


    # Environment variables for Compose interpolation and child scope
    $env:KNORA_S2_ISOLATED_TESTS = '1'
    $env:KNORA_S2_RUN_ID = $runIdN
    $env:KNORA_S2_PROJECT = $project
    $env:KNORA_S2_POSTGRES_VOLUME = $expectedPgVolume
    $env:KNORA_S2_QDRANT_VOLUME = $expectedQdVolume
    $env:KNORA_S2_EVIDENCE_ROOT = $evidenceRootFull
    $env:KNORA_S2_OBJECT_STORE_ROOT = $objectRoot
    $env:KNORA_S2_APPLICATION_COLLECTION = $Collection

    if ($Mode -eq 'Http') {
        # Provision fresh workspace UUID and credentials matching backend/src/knora/access/api_keys.py
        $childWorkspaceId = [guid]::NewGuid().ToString()
        $rawKeyBytes = New-Object byte[] 32
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($rawKeyBytes)
        $childApiKey = -join ($rawKeyBytes | ForEach-Object { '{0:x2}' -f $_ })

        $sha = [System.Security.Cryptography.SHA256]::Create()
        $keyHashBytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($childApiKey))
        $keyHashHex = -join ($keyHashBytes | ForEach-Object { '{0:x2}' -f $_ })
        $keyHash = "sha256:$keyHashHex"

        $credentialsJson = "[{`"key_id`":`"k-retrieval-test`",`"key_hash`":`"$keyHash`",`"workspace_id`":`"$childWorkspaceId`",`"enabled`":true}]"
        $env:KNORA_S2_API_CREDENTIALS_JSON = $credentialsJson
        $env:KNORA_S2_HTTP_WORKSPACE_ID = $childWorkspaceId
        $env:KNORA_S2_HTTP_API_KEY = $childApiKey

    }

        $env:KNORA_DATABASE_URL = 'postgresql+psycopg://knora_s2:isolated_s2@127.0.0.1:15433/knora_153_s2?connect_timeout=3'
        $env:KNORA_LEXICAL_QDRANT_URL = 'http://127.0.0.1:16433'
        $env:KNORA_PROVIDER_MODE = 'deterministic-local'
        $env:KNORA_EMBEDDING_PROVIDER = 'deterministic-local'
        $env:KNORA_GENERATION_PROVIDER = 'deterministic-local'
        $env:KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID = 'embedding-local-m1-v2'
        $env:KNORA_RETRIEVAL_CONFIGURATION_ID = 'retrieval-bm25-upload-fixture-top8-v1'
        $env:KNORA_OBJECT_STORE_BACKEND = 'filesystem'
        $env:KNORA_OBJECT_STORE_ROOT = $objectRoot

    # 8. Start Containers
    $startupAttempted = $true
    $upExit = 0
    try {
        & docker @dockerHostArgs compose @composeArgs up -d --build @servicesToStart
        $upExit = $LASTEXITCODE
    } catch {
        $upExit = 1
    }

    Update-OwnedInventory
    if ($leftovers.containers.Count -or $leftovers.volumes.Count -or $leftovers.networks.Count) {
        throw 'RETRIEVAL_TEST_OWNERSHIP_REJECTED'
    }

    if ($upExit -ne 0) {
        throw "RETRIEVAL_TEST_START_FAILED: docker compose up failed ($upExit)"
    }

    # 10. Health & Admission Inspection BEFORE -Run
    $storageContainers = @("${project}-verification-postgres-1", "${project}-verification-qdrant-1")
    $containersToInspect = if ($Mode -eq 'Http') {
        @("${project}-verification-api-1") + $storageContainers
    } else {
        $storageContainers
    }

    $rawInspect = (& docker @dockerHostArgs inspect @containersToInspect | Out-String)
    if ($LASTEXITCODE -ne 0 -or -not $rawInspect.Trim()) {
        throw "RETRIEVAL_TEST_ADMISSION_INSPECTION_FAILED"
    }

    $tempInput = New-TemporaryFile
    Set-Content -LiteralPath $tempInput -Value $rawInspect -Encoding utf8
    if ($Mode -eq 'Http') {
        $pyScript = "from backend.runtime_test.s2_runtime_guard import require_owned_s2_application_rows; import json, sys; from pathlib import Path; rows = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')); require_owned_s2_application_rows(rows, Path(sys.argv[2]))"
    } else {
        $pyScript = "from backend.runtime_test.s2_runtime_guard import require_owned_s2_storage; import json, sys; from pathlib import Path; rows = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')); require_owned_s2_storage(rows, Path(sys.argv[2]))"
    }
    $admissionOutput = (& python -c $pyScript "$tempInput" "$repositoryRoot" 2>&1)
    $pyExit = $LASTEXITCODE
    Remove-Item -LiteralPath $tempInput -Force -ErrorAction SilentlyContinue
    if ($pyExit -ne 0) {
        throw "RETRIEVAL_TEST_ADMISSION_FAILED: $admissionOutput"
    }

    # 11. Execute -Run ScriptBlock
    Write-Output "RETRIEVAL_TEST_PREPARED: $project"
    try {
        & $Run $project $composeArgs
        if ($LASTEXITCODE -ne 0) {
            $innerRunFailed = $true
            throw "RETRIEVAL_TEST_RUN_FAILED: command exited with $LASTEXITCODE"
        }
    } catch {
        $innerRunFailed = $true
        throw
    }

} catch {
    $primaryFailure = $_
    throw
} finally {
    # 12. Cleanup of Proved-Owned IDs Only
    try {
        if ($startupAttempted) {
            try { Update-OwnedInventory } catch { $cleanupErrors.Add('FAILED_RECOVERY_INVENTORY') }
            # Stop and remove proved-owned containers
            foreach ($cId in $ledger.containers) {
                if (-not (Test-OwnedContainer $cId)) {
                    if (-not $leftovers.containers.Contains($cId)) { $leftovers.containers.Add($cId) }
                    continue
                }
                & docker @dockerHostArgs stop $cId 2>$null | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    $cleanupErrors.Add("FAILED_STOP_CONTAINER: $cId")
                }
                if (-not (Test-OwnedContainer $cId)) {
                    if (-not $leftovers.containers.Contains($cId)) { $leftovers.containers.Add($cId) }
                    continue
                }
                & docker @dockerHostArgs rm -v $cId 2>$null | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    $cleanupErrors.Add("FAILED_RM_CONTAINER: $cId")
                }
            }
            # Remove proved-owned networks
            foreach ($nId in $ledger.networks) {
                $networkSafe = Test-OwnedNetwork $nId
                $networkRaw = (& docker @dockerHostArgs network inspect $nId | Out-String)
                if ($LASTEXITCODE -ne 0 -or -not $networkRaw.Trim()) { $networkSafe = $false }
                elseif (@((($networkRaw | ConvertFrom-Json)[0]).Containers.PSObject.Properties).Count -gt 0) { $networkSafe = $false }
                if (-not $networkSafe) {
                    if (-not $leftovers.networks.Contains($nId)) { $leftovers.networks.Add($nId) }
                    continue
                }
                & docker @dockerHostArgs network rm $nId 2>$null | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    $cleanupErrors.Add("FAILED_RM_NETWORK: $nId")
                }
            }
            # Remove proved-owned volumes
            foreach ($vName in $ledger.volumes) {
                $volumeSafe = Test-OwnedVolume $vName
                $attached = @(& docker @dockerHostArgs ps -a --no-trunc --filter "volume=$vName" --quiet)
                if ($LASTEXITCODE -ne 0 -or $attached.Count -gt 0) { $volumeSafe = $false }
                if (-not $volumeSafe) {
                    if (-not $leftovers.volumes.Contains($vName)) { $leftovers.volumes.Add($vName) }
                    continue
                }
                & docker @dockerHostArgs volume rm $vName 2>$null | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    $cleanupErrors.Add("FAILED_RM_VOLUME: $vName")
                }
            }

            # Verify no leftovers remain for this project
            $remContainers = @(& docker @dockerHostArgs ps -a --no-trunc --filter "label=com.docker.compose.project=$project" --quiet)
            if ($LASTEXITCODE -ne 0) {
                $cleanupErrors.Add("FAILED_INSPECT_REMAINING_CONTAINERS")
            }
            $remVolumes = @(& docker @dockerHostArgs volume ls --filter "label=com.docker.compose.project=$project" --quiet)
            if ($LASTEXITCODE -ne 0) {
                $cleanupErrors.Add("FAILED_INSPECT_REMAINING_VOLUMES")
            }
            $remNetworks = @(& docker @dockerHostArgs network ls --no-trunc --filter "label=com.docker.compose.project=$project" --quiet)
            if ($LASTEXITCODE -ne 0) {
                $cleanupErrors.Add("FAILED_INSPECT_REMAINING_NETWORKS")
            }

            $isClean = ($cleanupErrors.Count -eq 0) -and
                       ($remContainers.Count -eq 0) -and
                       ($remVolumes.Count -eq 0) -and
                       ($remNetworks.Count -eq 0) -and
                       ($leftovers.containers.Count -eq 0) -and
                       ($leftovers.volumes.Count -eq 0) -and
                       ($leftovers.networks.Count -eq 0)

            # Write sanitized durable receipt to EvidenceRoot
            $receiptPath = Join-Path $evidenceRootFull 'cleanup-receipt.json'
            $receipt = [PSCustomObject]@{
                project = $project
                cleanup_succeeded = $isClean
                inventory = $ledger
                errors = $cleanupErrors
                leftovers = [PSCustomObject]@{
                    containers = $leftovers.containers
                    volumes = $leftovers.volumes
                    networks = $leftovers.networks
                }
                remaining = [PSCustomObject]@{
                    containers = $remContainers
                    volumes = $remVolumes
                    networks = $remNetworks
                }
            }
            $receiptSaved = $false
            if (Test-Path -LiteralPath $evidenceRootFull) {
                try {
                    $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receiptPath -Encoding utf8
                    $receiptSaved = $true
                } catch {
                    $receiptSaved = $false
                }
            }

            if (-not $receiptSaved) {
                $isClean = $false
                Write-Error 'RETRIEVAL_TEST_RECEIPT_FAILED: evidence root unavailable or receipt persistence failed' -ErrorAction Continue
            }

            if ($isClean) {
                $cleanupSucceeded = $true
                Write-Output "RETRIEVAL_TEST_CLEANED: $project"
            } elseif (-not $primaryFailure) {
                if (-not $receiptSaved) {
                    throw 'RETRIEVAL_TEST_RECEIPT_FAILED: evidence root unavailable or receipt persistence failed; reservation retained'
                }
                throw 'RETRIEVAL_TEST_CLEANUP_INCOMPLETE: see cleanup-receipt.json; reservation retained'
            }
        }
    } finally {
        foreach ($name in $savedEnvironment.Keys) {
            [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
        }

        if ($reservation) {
            $reservation.Dispose()
            $reservation = $null
            if (-not $startupAttempted -or $cleanupSucceeded) {
                [IO.File]::Delete($reservationPath)
            }
        }
    }
}
